import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cv_engine.loader import FloorPlanLoader
from src.cv_engine.extractor import FloorPlanExtractor
from src.cv_engine.visualizer import FloorPlanVisualizer

def main():
    loader = FloorPlanLoader()
    plans = loader.list_floor_plans()
    print(f"Total indexed floor plans: {len(plans)}", flush=True)
    if not plans:
        print("No plans found!", flush=True)
        return

    sample = plans[0]
    print(f"Testing on sample plan: {sample['plan_id']}", flush=True)

    img_rgb, mask_rgb, meta = loader.load_pair(sample["plan_id"])
    print(f"Loaded image: {img_rgb.shape}, mask: {mask_rgb.shape}", flush=True)

    extractor = FloorPlanExtractor()
    data = extractor.extract_all(mask_rgb, plan_id=sample["plan_id"])

    print(f"Extracted {len(data['rooms'])} rooms", flush=True)
    for r in data["rooms"][:4]:
        print(f"  {r['room_name']}: {r['room_type']}, Area={r['pixel_area']} px, Center=({r['centroid_x']},{r['centroid_y']})", flush=True)

    print(f"Extracted {len(data['doors'])} doors", flush=True)
    print(f"Extracted {len(data['windows'])} windows", flush=True)
    print(f"Extracted {len(data['connections'])} room-to-room door connections", flush=True)
    for c in data["connections"][:4]:
        print(f"  {c['room_1_name']} <---> {c['room_2_name']} (Door {c['door_index']}, Distance {c['distance_px']} px)", flush=True)

    print(f"Validation: Confidence={data['validation']['extraction_confidence_score']}%, Status={data['validation']['validation_status']}", flush=True)

    # Save visual overlays for 3 plans (1, 2, 3)
    visualizer = FloorPlanVisualizer()
    saved = visualizer.save_sample_overlays(loader, extractor, ["1", "2", "3"])
    print(f"Saved {len(saved)} visual overlay files:", flush=True)
    for p in saved:
        print(f"  {p}", flush=True)

if __name__ == "__main__":
    main()
