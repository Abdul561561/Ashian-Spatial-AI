import pytest
import numpy as np
from src.spatial_intelligence.graph_builder import SpatialGraphBuilder
from src.spatial_intelligence.navigation import IndoorNavigator
from src.database.db_manager import DatabaseManager
from src.cv_engine.visualizer import FloorPlanVisualizer

REQUIRED_NAVIGATION_KEYS = {
    "success",
    "path",
    "path_indices",
    "path_rooms",
    "num_steps",
    "total_distance",
    "total_distance_px",
    "instructions",
    "waypoints",
    "connected_rooms",
    "message",
    "error",
}

@pytest.fixture
def synthetic_graph():
    rooms_data = [
        {"room_index": 1, "room_name": "Living Room", "room_type": "Living Room", "centroid_x": 100, "centroid_y": 100, "pixel_area": 50000, "bbox_x": 50, "bbox_y": 50, "bbox_w": 100, "bbox_h": 100},
        {"room_index": 2, "room_name": "Hallway", "room_type": "Hallway", "centroid_x": 200, "centroid_y": 100, "pixel_area": 20000, "bbox_x": 150, "bbox_y": 50, "bbox_w": 100, "bbox_h": 100},
        {"room_index": 3, "room_name": "Bedroom 1", "room_type": "Bedroom", "centroid_x": 300, "centroid_y": 100, "pixel_area": 35000, "bbox_x": 250, "bbox_y": 50, "bbox_w": 100, "bbox_h": 100},
        {"room_index": 4, "room_name": "Isolated Storage", "room_type": "Storage", "centroid_x": 500, "centroid_y": 500, "pixel_area": 10000, "bbox_x": 450, "bbox_y": 450, "bbox_w": 100, "bbox_h": 100},
    ]

    connections_data = [
        {"room_1_index": 1, "room_2_index": 2, "door_index": 1, "distance_px": 100.0},
        {"room_1_index": 2, "room_2_index": 3, "door_index": 2, "distance_px": 100.0},
    ]

    doors_data = [
        {"door_index": 1, "is_entrance": True, "connected_room_indices": "1,2"},
        {"door_index": 2, "is_entrance": False, "connected_room_indices": "2,3"},
    ]

    builder = SpatialGraphBuilder()
    return builder.build_graph(rooms_data, connections_data, doors_data)


def test_standardized_response_keys_contract(synthetic_graph):
    """Verifies that every navigation outcome returns the exact standardized dictionary contract."""
    navigator = IndoorNavigator()
    G = synthetic_graph

    # 1. Successful multi-step route
    res_success = navigator.navigate(G, 1, 3)
    assert REQUIRED_NAVIGATION_KEYS.issubset(res_success.keys())
    assert isinstance(res_success["num_steps"], int)
    assert res_success["num_steps"] == 2
    assert res_success["path"] == [1, 2, 3]
    assert res_success["path_indices"] == [1, 2, 3]
    assert res_success["connected_rooms"] == [1, 2, 3]
    assert res_success["error"] is None
    assert res_success["total_distance"] == 200.0

    # 2. Same-room route (source == target)
    res_same = navigator.navigate(G, 1, 1)
    assert REQUIRED_NAVIGATION_KEYS.issubset(res_same.keys())
    assert res_same["success"] is True
    assert res_same["num_steps"] == 0
    assert res_same["total_distance"] == 0.0
    assert res_same["total_distance_px"] == 0.0
    assert res_same["path"] == [1]
    assert res_same["path_indices"] == [1]
    assert res_same["connected_rooms"] == [1]
    assert res_same["error"] is None
    assert "No movement required" in res_same["message"]

    # 3. Disconnected rooms
    res_disc = navigator.navigate(G, 1, 4)
    assert REQUIRED_NAVIGATION_KEYS.issubset(res_disc.keys())
    assert res_disc["success"] is False
    assert res_disc["num_steps"] == 0
    assert res_disc["total_distance"] == 0.0
    assert res_disc["path"] == []
    assert res_disc["path_indices"] == []
    assert res_disc["connected_rooms"] == []
    assert res_disc["error"] is not None

    # 4. Invalid source room
    res_inv_src = navigator.navigate(G, 999, 1)
    assert REQUIRED_NAVIGATION_KEYS.issubset(res_inv_src.keys())
    assert res_inv_src["success"] is False
    assert res_inv_src["num_steps"] == 0
    assert "Source Room 999 does not exist" in res_inv_src["error"]

    # 5. Invalid target room
    res_inv_tgt = navigator.navigate(G, 1, 999)
    assert REQUIRED_NAVIGATION_KEYS.issubset(res_inv_tgt.keys())
    assert res_inv_tgt["success"] is False
    assert res_inv_tgt["num_steps"] == 0
    assert "Target Room 999 does not exist" in res_inv_tgt["error"]

    # 6. Entrance navigation
    res_ent = navigator.navigate_from_entrance(G, 3)
    assert REQUIRED_NAVIGATION_KEYS.issubset(res_ent.keys())
    assert res_ent["success"] is True
    assert res_ent["path"][-1] == 3


def test_real_plan_1_navigation_scenarios():
    """Tests navigation scenarios on Plan 1 from the indexed SQLite database."""
    db = DatabaseManager()
    gb = SpatialGraphBuilder()
    nav = IndoorNavigator()

    rooms = db.get_rooms_df("1")
    conns = db.get_connections_df("1")
    doors = db.get_doors_df("1")
    G = gb.build_graph(rooms, conns, doors)

    # Room 1 -> Room 4 (Legitimate continuous door connection)
    res_1_4 = nav.navigate(G, 1, 4)
    assert res_1_4["success"] is True
    assert res_1_4["num_steps"] == 1
    assert res_1_4["path"] == [1, 4]
    assert res_1_4["total_distance_px"] > 0
    assert len(res_1_4["instructions"]) >= 3

    # Room 1 -> Room 2 (Disconnected rooms in Plan 1)
    res_1_2 = nav.navigate(G, 1, 2)
    assert res_1_2["success"] is False
    assert res_1_2["num_steps"] == 0
    assert res_1_2["path"] == []
    assert "No continuous door connection exists" in res_1_2["error"]

    # Room 2 -> Room 10 (Disconnected: Room 2 is isolated)
    res_2_10 = nav.navigate(G, 2, 10)
    assert res_2_10["success"] is False
    assert res_2_10["num_steps"] == 0
    assert "No continuous door connection exists" in res_2_10["error"]

    # Room 1 -> Room 1 (Same room)
    res_1_1 = nav.navigate(G, 1, 1)
    assert res_1_1["success"] is True
    assert res_1_1["num_steps"] == 0
    assert res_1_1["total_distance_px"] == 0.0
    assert res_1_1["path"] == [1]

    # Room 3 -> Room 7 (Multi-step path through hallway sector: 3 -> 9 -> 10 -> 7)
    res_3_7 = nav.navigate(G, 3, 7)
    assert res_3_7["success"] is True
    assert res_3_7["num_steps"] == 3
    assert res_3_7["path"] == [3, 9, 10, 7]


def test_real_plan_20_zero_fabrication():
    """Tests Plan 20 navigation: zero interior doors must result in zero fabricated routes."""
    db = DatabaseManager()
    gb = SpatialGraphBuilder()
    nav = IndoorNavigator()

    rooms = db.get_rooms_df("20")
    conns = db.get_connections_df("20")
    doors = db.get_doors_df("20")
    G = gb.build_graph(rooms, conns, doors)

    metrics = gb.get_graph_metrics(G)
    assert metrics["num_connections"] == 0

    # Route between distinct rooms must fail gracefully without KeyError
    res = nav.navigate(G, 1, 2)
    assert res["success"] is False
    assert res["num_steps"] == 0
    assert res["total_distance_px"] == 0.0
    assert res["path"] == []
    assert "No continuous door connection exists" in res["error"]

    # Same room navigation still succeeds with 0 steps
    res_same = nav.navigate(G, 1, 1)
    assert res_same["success"] is True
    assert res_same["num_steps"] == 0
    assert res_same["total_distance_px"] == 0.0
    assert res_same["path"] == [1]


def test_visualizer_navigation_overlay_modes():
    """Verifies that the route visualizer handles empty, single-room, and multi-step waypoints."""
    viz = FloorPlanVisualizer()
    dummy_img = np.zeros((400, 400, 3), dtype=np.uint8)

    # Empty waypoints
    out_empty = viz.draw_navigation_route(dummy_img, [], [])
    assert out_empty.shape == dummy_img.shape

    # Single-room waypoint (source == target)
    out_single = viz.draw_navigation_route(dummy_img, [(200, 200)], ["Room 1"])
    assert out_single.shape == dummy_img.shape
    # Check that pixel values were modified (drawing performed)
    assert not np.array_equal(out_single, dummy_img)

    # Multi-step path
    out_multi = viz.draw_navigation_route(dummy_img, [(100, 100), (200, 200), (300, 300)], ["Room 1", "Room 2", "Room 3"])
    assert out_multi.shape == dummy_img.shape
    assert not np.array_equal(out_multi, dummy_img)
