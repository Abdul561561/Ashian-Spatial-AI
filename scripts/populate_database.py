import sys
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cv_engine.loader import FloorPlanLoader
from src.cv_engine.extractor import FloorPlanExtractor
from src.cv_engine.visualizer import FloorPlanVisualizer
from src.database.db_manager import DatabaseManager

def populate(limit: int = 25, generate_overlays: bool = True, reset_db: bool = True):
    print(f"=== Populating Ashian Spatial AI Database (limit={limit}, reset={reset_db}) ===", flush=True)
    loader = FloorPlanLoader()
    extractor = FloorPlanExtractor()
    db = DatabaseManager()
    visualizer = FloorPlanVisualizer()

    if reset_db:
        print("Recreating database tables with updated schema...", flush=True)
        from src.database.models import Base
        Base.metadata.drop_all(db.engine)
        Base.metadata.create_all(db.engine)

    plans = loader.list_floor_plans()
    print(f"Total available floor plans in dataset: {len(plans)}", flush=True)

    if limit > 0:
        plans = plans[:limit]

    success_count = 0
    total_rooms = 0
    total_doors = 0

    for i, p in enumerate(plans, start=1):
        pid = p["plan_id"]
        try:
            img_rgb, mask_rgb, meta = loader.load_pair(pid)
            extracted = extractor.extract_all(mask_rgb, plan_id=pid)
            db_id = db.save_extraction_result(meta, extracted)

            r_count = len(extracted["rooms"])
            d_count = len(extracted["doors"])
            w_count = len(extracted["windows"])
            c_count = len(extracted["connections"])
            conf = extracted["validation"]["extraction_confidence_score"]

            total_rooms += r_count
            total_doors += d_count
            success_count += 1

            print(
                f"[{i:02d}/{len(plans)}] Plan {pid:>3s} (DB ID {db_id}): "
                f"{r_count} rooms, {d_count} doors, {w_count} windows, {c_count} connections | "
                f"Conf: {conf}% [{extracted['validation']['validation_status']}]",
                flush=True
            )

            # Generate overlay for first 5 plans
            if generate_overlays and i <= 5:
                overlay = visualizer.create_overlay(img_rgb, extracted)
                from PIL import Image
                out_p = visualizer.output_dir / f"overlay_floorplan_{pid}.png"
                Image.fromarray(overlay).save(out_p)

        except Exception as e:
            print(f"[{i:02d}/{len(plans)}] Plan {pid}: Failed to process - {e}", flush=True)

    print("\n=== Population Summary ===", flush=True)
    print(f"Successfully populated: {success_count} floor plans", flush=True)
    print(f"Total rooms stored: {total_rooms}", flush=True)
    print(f"Total doors stored: {total_doors}", flush=True)
    print("Database ready at data/spatial_ai.db", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25, help="Number of plans to populate (default: 25)")
    parser.add_argument("--all", action="store_true", help="Populate all floor plans")
    args = parser.parse_args()

    lim = 0 if args.all else args.limit
    populate(limit=lim)
