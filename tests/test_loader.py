import pytest
from pathlib import Path
from src.cv_engine.loader import FloorPlanLoader

def test_loader_indexing():
    loader = FloorPlanLoader()
    plans = loader.list_floor_plans()
    assert len(plans) > 0, "Loader should find floor plans in data/raw"
    
    first_plan = plans[0]
    assert "plan_id" in first_plan
    assert "image_path" in first_plan
    assert "mask_path" in first_plan
    assert Path(first_plan["image_path"]).exists()
    assert Path(first_plan["mask_path"]).exists()

def test_loader_load_pair():
    loader = FloorPlanLoader()
    img_rgb, mask_rgb, meta = loader.load_pair("1")
    
    assert img_rgb is not None
    assert mask_rgb is not None
    assert img_rgb.ndim == 3 and img_rgb.shape[2] == 3
    assert mask_rgb.ndim == 3 and mask_rgb.shape[2] == 3
    assert img_rgb.shape[:2] == mask_rgb.shape[:2]
    
    assert meta["width"] == img_rgb.shape[1]
    assert meta["height"] == img_rgb.shape[0]
    assert meta["total_pixels"] == meta["width"] * meta["height"]
    assert meta["aspect_ratio"] > 0

def test_loader_nonexistent_plan():
    loader = FloorPlanLoader()
    with pytest.raises(FileNotFoundError):
        loader.load_pair("non_existent_id_99999")
