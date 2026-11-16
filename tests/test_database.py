import pytest
from src.database.db_manager import DatabaseManager
from src.cv_engine.loader import FloorPlanLoader
from src.cv_engine.extractor import FloorPlanExtractor

@pytest.fixture
def test_db(tmp_path):
    test_db_path = tmp_path / "test_spatial.db"
    return DatabaseManager(db_url=f"sqlite:///{test_db_path}")

def test_database_population_and_query(test_db):
    loader = FloorPlanLoader()
    extractor = FloorPlanExtractor()

    img_rgb, mask_rgb, meta = loader.load_pair("1")
    extracted = extractor.extract_all(mask_rgb, plan_id="1")

    fp_id = test_db.save_extraction_result(meta, extracted)
    assert fp_id > 0

    # Query floor plan
    fp = test_db.get_floor_plan("1")
    assert fp is not None
    assert fp["plan_id"] == "1"
    assert fp["width"] == meta["width"]

    # Query rooms
    rooms_df = test_db.get_rooms_df("1")
    assert len(rooms_df) == len(extracted["rooms"])
    assert "room_index" in rooms_df.columns
    assert "pixel_area" in rooms_df.columns

    # Query doors and connections
    doors_df = test_db.get_doors_df("1")
    assert len(doors_df) == len(extracted["doors"])

    conns_df = test_db.get_connections_df("1")
    assert len(conns_df) == len(extracted["connections"])

    # Query metadata
    meta_rec = test_db.get_metadata("1")
    assert meta_rec is not None
    assert meta_rec["extraction_confidence_score"] > 50.0

def test_read_only_sql_execution(test_db):
    # Insert test plan
    loader = FloorPlanLoader()
    extractor = FloorPlanExtractor()
    img_rgb, mask_rgb, meta = loader.load_pair("1")
    extracted = extractor.extract_all(mask_rgb, plan_id="1")
    test_db.save_extraction_result(meta, extracted)

    # Valid SELECT query
    records, cols = test_db.execute_read_only_sql("SELECT room_name, room_type, pixel_area FROM rooms WHERE room_index = 1")
    assert len(records) == 1
    assert "room_name" in cols
    assert records[0]["room_name"] == "Room 1"
