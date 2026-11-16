import pytest
import numpy as np
from src.database.db_manager import DatabaseManager
from src.ai_assistant.assistant import AshianSpatialAssistant

@pytest.fixture(scope="module")
def db():
    return DatabaseManager()

@pytest.fixture(scope="module")
def assistant(db):
    return AshianSpatialAssistant(db_manager=db)

# -------------------------------------------------------------
# 1. Plan 20 Room Accounting Verification
# -------------------------------------------------------------
def test_plan_20_habitable_vs_detected_regions(db):
    """
    Floor Plan #20 has 36 detected spatial regions, but contains 15-16 primary enclosed rooms.
    The remaining 20 regions are 17 exterior balcony/sill strips and 3 service spaces.
    Verify that the system separates actual room counts from detected regions.
    """
    meta = db.get_metadata("20")
    assert meta is not None, "Plan 20 metadata must exist"
    assert meta["num_rooms"] == 36, "Total detected spatial regions in CVC-FP mask is 36"
    assert meta["total_detected_regions"] == 36
    assert meta["num_habitable_rooms"] >= 14 and meta["num_habitable_rooms"] <= 16
    assert meta["num_balconies"] == 17
    assert meta["num_service_rooms"] == 3
    assert "Primary Rooms" in meta["room_count_breakdown"]

    rooms_df = db.get_rooms_df("20")
    assert len(rooms_df) == 36
    habitable = rooms_df[rooms_df["is_habitable_room"] == True]
    assert len(habitable) == 16, "Plan 20 has exactly 16 primary room entities"
    
    balconies = rooms_df[rooms_df["raw_class"] == "balcony"]
    assert len(balconies) == 17
    assert all(b == False for b in balconies["is_habitable_room"])

# -------------------------------------------------------------
# 2. Plan 1 Composition Verification
# -------------------------------------------------------------
def test_plan_1_composition(db):
    """Plan 1 has 14 detected regions: 12 primary rooms (11 habitable, 1 corridor), 1 service, 1 balcony."""
    meta = db.get_metadata("1")
    assert meta is not None
    assert meta["total_detected_regions"] == 14
    assert meta["num_habitable_rooms"] == 11
    assert meta["num_corridors"] == 1
    assert meta["num_service_rooms"] == 1
    assert meta["num_balconies"] == 1

# -------------------------------------------------------------
# 3. Plan 5 Facade Balcony Fragmentation Check
# -------------------------------------------------------------
def test_plan_5_balcony_fragmentation(db):
    """Plan 5 has 25 total regions, but only 11 habitable rooms; 11 are exterior balcony/sill strips."""
    meta = db.get_metadata("5")
    assert meta is not None
    assert meta["total_detected_regions"] == 25
    assert meta["num_habitable_rooms"] == 11
    assert meta["num_balconies"] == 11
    assert meta["num_service_rooms"] == 3

# -------------------------------------------------------------
# 4. Duplicate Detection & Centroid Proximity Verification
# -------------------------------------------------------------
@pytest.mark.parametrize("pid", ["1", "5", "10", "12", "20"])
def test_no_duplicate_room_centroids(db, pid):
    """Verify that the extractor does not produce duplicate room centroids within 15px."""
    rooms_df = db.get_rooms_df(pid)
    assert not rooms_df.empty
    
    centroids = list(zip(rooms_df["centroid_x"], rooms_df["centroid_y"]))
    for i in range(len(centroids)):
        for j in range(i + 1, len(centroids)):
            dist = np.hypot(centroids[i][0] - centroids[j][0], centroids[i][1] - centroids[j][1])
            assert dist > 15.0, f"Plan {pid}: Duplicate centroid found between index {i+1} and {j+1} (dist={dist:.1f}px)"

# -------------------------------------------------------------
# 5. Room Fragmentation & Non-Overlapping Bounding Boxes
# -------------------------------------------------------------
@pytest.mark.parametrize("pid", ["1", "5", "12", "20"])
def test_primary_room_bounding_box_disjointness(db, pid):
    """Ensure primary rooms are genuinely separate and not redundant nested duplicates."""
    rooms_df = db.get_rooms_df(pid)
    primary = rooms_df[rooms_df["raw_class"] == "room"]
    
    # Calculate pairwise Intersection over Union (IoU) of bounding boxes
    for i, r1 in primary.iterrows():
        box1 = (r1["bbox_x"], r1["bbox_y"], r1["bbox_x"] + r1["bbox_w"], r1["bbox_y"] + r1["bbox_h"])
        for j, r2 in primary.iterrows():
            if r1["room_index"] >= r2["room_index"]:
                continue
            box2 = (r2["bbox_x"], r2["bbox_y"], r2["bbox_x"] + r2["bbox_w"], r2["bbox_y"] + r2["bbox_h"])
            
            # Intersection
            ix1 = max(box1[0], box2[0])
            iy1 = max(box1[1], box2[1])
            ix2 = min(box1[2], box2[2])
            iy2 = min(box1[3], box2[3])
            
            if ix2 > ix1 and iy2 > iy1:
                inter_area = (ix2 - ix1) * (iy2 - iy1)
                area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
                area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
                iou = inter_area / float(area1 + area2 - inter_area)
                assert iou < 0.90, f"Plan {pid}: Excessive bounding box overlap (IoU={iou:.2f}) between Room {r1['room_index']} and Room {r2['room_index']}"

# -------------------------------------------------------------
# 6. AI Question Answering Room Accounting Verification
# -------------------------------------------------------------
def test_ai_reports_transparent_room_accounting(assistant):
    """Ensure AI assistant reports both total detected regions and primary enclosed habitable rooms."""
    resp = assistant.ask("How many rooms does plan 20 have?", active_plan_id="20")
    assert resp["success"] is True
    ans = resp["answer"].lower()
    assert "36" in ans or "36" in str(resp.get("records"))
    assert "habitable" in ans or "primary" in ans
