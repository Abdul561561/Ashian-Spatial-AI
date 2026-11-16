import numpy as np
import pytest
from src.cv_engine.loader import FloorPlanLoader
from src.cv_engine.mask_inspector import MaskInspector
from src.cv_engine.extractor import FloorPlanExtractor
from src.cv_engine.visualizer import FloorPlanVisualizer

@pytest.fixture
def plan_1_data():
    loader = FloorPlanLoader()
    img_rgb, mask_rgb, meta = loader.load_pair("1")
    return img_rgb, mask_rgb, meta

def test_mask_inspector(plan_1_data):
    _, mask_rgb, _ = plan_1_data
    inspector = MaskInspector()
    report = inspector.inspect_mask(mask_rgb)

    assert report["total_pixels"] > 0
    assert report["indoor_pixels"] > 0
    assert report["indoor_percentage"] > 0
    assert len(report["detected_classes"]) > 0
    assert "room" in report["detected_classes"]

def test_room_and_door_extraction(plan_1_data):
    _, mask_rgb, meta = plan_1_data
    extractor = FloorPlanExtractor()
    extracted = extractor.extract_all(mask_rgb, plan_id="1")

    assert extracted["plan_id"] == "1"
    rooms = extracted["rooms"]
    doors = extracted["doors"]
    windows = extracted["windows"]
    connections = extracted["connections"]

    assert len(rooms) >= 5, "Plan 1 should yield multiple rooms"
    assert len(doors) > 0, "Plan 1 should have doors"
    assert len(windows) > 0, "Plan 1 should have windows"
    assert len(connections) > 0, "Plan 1 should have room-to-room connections"

    # Verify room geometric properties
    for r in rooms:
        assert r["pixel_area"] > 0
        assert r["bbox_w"] > 0 and r["bbox_h"] > 0
        assert 0 <= r["centroid_x"] <= meta["width"]
        assert 0 <= r["centroid_y"] <= meta["height"]
        assert 0.0 <= r["confidence"] <= 1.0

    # Verify door properties
    for d in doors:
        assert d["pixel_area"] > 0
        assert d["orientation"] in ("horizontal", "vertical")

def test_visual_overlay_generation(plan_1_data):
    img_rgb, mask_rgb, _ = plan_1_data
    extractor = FloorPlanExtractor()
    extracted = extractor.extract_all(mask_rgb, plan_id="1")

    visualizer = FloorPlanVisualizer()
    overlay = visualizer.create_overlay(img_rgb, extracted)

    assert overlay.shape == img_rgb.shape
    assert overlay.dtype == np.uint8
    # Ensure overlay is not blank
    assert np.mean(overlay) > 10
