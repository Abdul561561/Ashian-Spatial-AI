import pytest
from src.database.db_manager import DatabaseManager
from src.ai_assistant.assistant import AshianSpatialAssistant
from src.spatial_intelligence.graph_builder import SpatialGraphBuilder
from src.spatial_intelligence.navigation import IndoorNavigator

@pytest.fixture(scope="module")
def db():
    return DatabaseManager()

@pytest.fixture(scope="module")
def assistant(db):
    return AshianSpatialAssistant(db_manager=db)

# -------------------------------------------------------------
# 1. Window Extraction & Adjacency Tests
# -------------------------------------------------------------
def test_window_extraction_and_schema(db):
    """Verify that rooms have semantic_class, inferred_type, and window_count, and windows have connected_room_index."""
    rooms_df = db.get_rooms_df("1")
    assert not rooms_df.empty, "Plan 1 rooms should exist"
    assert "semantic_class" in rooms_df.columns
    assert "inferred_type" in rooms_df.columns
    assert "window_count" in rooms_df.columns
    
    # Check window correlation
    windows_df = db.get_windows_df("1")
    assert not windows_df.empty, "Plan 1 windows should exist"
    assert "connected_room_index" in windows_df.columns
    
    # Check Plan 4 rooms with 0 windows
    rooms_p4 = db.get_rooms_df("4")
    zero_window_rooms = rooms_p4[rooms_p4["window_count"] == 0]
    assert len(zero_window_rooms) > 0, "Plan 4 must have identifiable rooms without windows"

# -------------------------------------------------------------
# 2. Assignment Questions Verification
# -------------------------------------------------------------
def test_assignment_q1_rooms_in_plan_12(assistant):
    """Assignment Q1: How many rooms does plan 12 have?"""
    resp = assistant.ask("How many rooms does plan 12 have?")
    assert resp["success"] is True
    assert "14" in resp["answer"] or (resp.get("records") and resp["records"][0].get("num_rooms") == 14)

def test_assignment_q2_largest_room_in_plan_7(assistant):
    """Assignment Q2: What is the largest room in plan 7?"""
    resp = assistant.ask("What is the largest room in plan 7?")
    assert resp["success"] is True
    assert "Room" in resp["answer"]
    assert resp.get("records") and len(resp["records"]) > 0

def test_assignment_q3_plans_with_more_than_3_doors(assistant):
    """Assignment Q3: Which plans have more than 3 doors?"""
    resp = assistant.ask("Which plans have more than 3 doors?")
    assert resp["success"] is True
    assert resp.get("record_count", 0) > 0

def test_assignment_q4_room_in_plan_4_no_windows(assistant):
    """Assignment Q4: Which room in plan 4 has no windows?"""
    resp = assistant.ask("Which room in plan 4 has no windows?")
    assert resp["success"] is True
    assert "Room" in resp["answer"]
    assert resp.get("record_count", 0) > 0

def test_assignment_q5_average_rooms_across_all_plans(assistant):
    """Assignment Q5: What is the average number of rooms across all plans?"""
    resp = assistant.ask("What is the average number of rooms across all plans?")
    assert resp["success"] is True
    assert "average" in resp["answer"].lower() or resp.get("records")

# -------------------------------------------------------------
# 3. Unsupported Questions Guardrail Tests
# -------------------------------------------------------------
@pytest.mark.parametrize("unsupported_q", [
    "Who was the architect of this building?",
    "What was the total construction cost in dollars?",
    "What building materials and concrete grade were used?",
    "What HVAC and ventilation system is installed?",
    "What is the property zoning classification and market value?",
])
def test_unsupported_questions_declined(assistant, unsupported_q):
    """Ensure AI assistant cleanly declines out-of-scope architectural metadata without hallucinating."""
    resp = assistant.ask(unsupported_q, active_plan_id="1")
    assert resp["confidence"] == "UNSUPPORTED_QUESTION"
    assert "unsupported question declined" in resp["answer"].lower()
    assert "[DECLINED" in resp.get("generated_sql", "")

# -------------------------------------------------------------
# 4. Zero-Fabrication Indoor Navigation Tests (Plan 20)
# -------------------------------------------------------------
def test_plan_20_zero_fabrication(db):
    """Plan 20 has 36 rooms and 0 interior door passages; verify no paths are fabricated."""
    rooms_df = db.get_rooms_df("20")
    conns_df = db.get_connections_df("20")
    doors_df = db.get_doors_df("20")
    
    gb = SpatialGraphBuilder()
    G = gb.build_graph(rooms_df, conns_df, doors_df)
    
    metrics = gb.get_graph_metrics(G)
    assert metrics["num_rooms"] == 36
    assert metrics["num_connections"] == 0
    assert metrics["is_fully_connected"] is False
    
    nav = IndoorNavigator()
    route = nav.navigate(G, source_room_idx=1, target_room_idx=2)
    assert route["success"] is False
    assert route["path_indices"] == []
    assert "No continuous door connection exists" in route["error"]
