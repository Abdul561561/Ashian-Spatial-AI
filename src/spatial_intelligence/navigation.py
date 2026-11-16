from typing import Dict, List, Optional, Tuple, Any
import networkx as nx
import numpy as np

class IndoorNavigator:
    """Computes navigation routes, shortest paths, and turn-by-turn guidance."""

    def __init__(self):
        pass

    def navigate(
        self,
        G: nx.Graph,
        source_room_idx: int,
        target_room_idx: int
    ) -> Dict[str, Any]:
        """
        Computes the shortest topological path between source and target rooms.
        Never invents connections when door connectivity is unavailable.
        Returns a standardized dictionary structure across all outcomes.
        """
        if not G.has_node(source_room_idx):
            err = f"Source Room {source_room_idx} does not exist in floor plan."
            return {
                "success": False,
                "path": [],
                "path_indices": [],
                "path_rooms": [],
                "num_steps": 0,
                "total_distance": 0.0,
                "total_distance_px": 0.0,
                "instructions": [],
                "waypoints": [],
                "connected_rooms": [],
                "message": err,
                "error": err,
            }

        if not G.has_node(target_room_idx):
            err = f"Target Room {target_room_idx} does not exist in floor plan."
            return {
                "success": False,
                "path": [],
                "path_indices": [],
                "path_rooms": [],
                "num_steps": 0,
                "total_distance": 0.0,
                "total_distance_px": 0.0,
                "instructions": [],
                "waypoints": [],
                "connected_rooms": [],
                "message": err,
                "error": err,
            }

        # Source is target (same room)
        if source_room_idx == target_room_idx:
            node = G.nodes[source_room_idx]
            clean_type = str(node.get("room_type", "Room")).replace(" [Heuristic]", "").replace(" [Service]", "").replace(" [Outdoor]", "").replace(" [Circulation]", "")
            room_name = node.get("room_name", f"Room {source_room_idx}")
            centroid = node.get("centroid", (node.get("centroid_x", 0), node.get("centroid_y", 0)))
            msg = f"Source and destination are both {room_name}. No movement required."
            return {
                "success": True,
                "path": [source_room_idx],
                "path_indices": [source_room_idx],
                "path_rooms": [{"index": source_room_idx, "name": room_name, "type": clean_type}],
                "num_steps": 0,
                "total_distance": 0.0,
                "total_distance_px": 0.0,
                "instructions": [f"You are currently at {room_name} ({clean_type}). No movement required."],
                "waypoints": [centroid],
                "connected_rooms": [source_room_idx],
                "message": msg,
                "error": None,
            }

        # Check connectivity
        if not nx.has_path(G, source_room_idx, target_room_idx):
            src_node = G.nodes[source_room_idx]
            tgt_node = G.nodes[target_room_idx]
            src_name = src_node.get("room_name", f"Room {source_room_idx}")
            src_type = str(src_node.get("room_type", "Room")).replace(" [Heuristic]", "").replace(" [Service]", "").replace(" [Outdoor]", "").replace(" [Circulation]", "")
            tgt_name = tgt_node.get("room_name", f"Room {target_room_idx}")
            tgt_type = str(tgt_node.get("room_type", "Room")).replace(" [Heuristic]", "").replace(" [Service]", "").replace(" [Outdoor]", "").replace(" [Circulation]", "")
            err = f"No continuous door connection exists between {src_name} ({src_type}) and {tgt_name} ({tgt_type}). These areas are located in isolated or disconnected spatial sectors."
            return {
                "success": False,
                "path": [],
                "path_indices": [],
                "path_rooms": [],
                "num_steps": 0,
                "total_distance": 0.0,
                "total_distance_px": 0.0,
                "instructions": [],
                "waypoints": [],
                "connected_rooms": [],
                "message": err,
                "error": err,
            }

        # Compute shortest path weighted by Euclidean centroid distance
        path = nx.shortest_path(G, source=source_room_idx, target=target_room_idx, weight="weight")
        total_dist = nx.shortest_path_length(G, source=source_room_idx, target=target_room_idx, weight="weight")

        # Generate step-by-step turn guidance and waypoints
        waypoints = []
        instructions = []
        path_rooms = []

        start_node = G.nodes[path[0]]
        waypoints.append(start_node["centroid"])
        start_type = str(start_node.get("room_type", "Room")).replace(" [Heuristic]", "").replace(" [Service]", "").replace(" [Outdoor]", "").replace(" [Circulation]", "")
        start_name = start_node.get("room_name", f"Room {path[0]}")
        path_rooms.append({
            "index": path[0],
            "name": start_name,
            "type": start_type,
        })
        instructions.append(f"Start at {start_name} ({start_type}).")

        for i in range(len(path) - 1):
            curr_id = path[i]
            next_id = path[i + 1]
            curr_node = G.nodes[curr_id]
            next_node = G.nodes[next_id]
            edge_data = G.get_edge_data(curr_id, next_id) or {}

            door_idx = edge_data.get("door_index", 0)
            step_dist = edge_data.get("distance_px", 0.0)
            curr_name = curr_node.get("room_name", f"Room {curr_id}")
            next_name = next_node.get("room_name", f"Room {next_id}")
            clean_type = str(next_node.get("room_type", "Room")).replace(" [Heuristic]", "").replace(" [Service]", "").replace(" [Outdoor]", "").replace(" [Circulation]", "")

            waypoints.append(next_node["centroid"])
            path_rooms.append({
                "index": next_id,
                "name": next_name,
                "type": clean_type,
            })

            if door_idx and door_idx != 0:
                instructions.append(
                    f"Step {i + 1}: Pass through Door {door_idx} from {curr_name} into {next_name} ({clean_type}) [~{int(step_dist)} px]."
                )
            else:
                instructions.append(
                    f"Step {i + 1}: Walk through the open archway from {curr_name} into {next_name} ({clean_type}) [~{int(step_dist)} px]."
                )

        goal_node = G.nodes[path[-1]]
        goal_name = goal_node.get("room_name", f"Room {path[-1]}")
        goal_type = str(goal_node.get("room_type", "Room")).replace(" [Heuristic]", "").replace(" [Service]", "").replace(" [Outdoor]", "").replace(" [Circulation]", "")
        instructions.append(f"Goal reached: You have arrived at {goal_name} ({goal_type}).")

        num_steps = len(path) - 1
        rounded_dist = round(float(total_dist), 1)
        msg = f"Route calculated: {num_steps} step{'s' if num_steps != 1 else ''} ({rounded_dist} px)."

        return {
            "success": True,
            "path": path,
            "path_indices": path,
            "path_rooms": path_rooms,
            "num_steps": num_steps,
            "total_distance": rounded_dist,
            "total_distance_px": rounded_dist,
            "instructions": instructions,
            "waypoints": waypoints,
            "connected_rooms": list(path),
            "message": msg,
            "error": None,
        }

    def navigate_from_entrance(self, G: nx.Graph, target_room_idx: int) -> Dict[str, Any]:
        """Navigates from the designated building entrance room to a target room."""
        entrance_rooms = [node for node, data in G.nodes(data=True) if data.get("is_entrance", False)]
        
        if not entrance_rooms:
            # Fallback to Room 1 as default entry zone if no explicit entrance door is flagged
            entrance_rooms = [1] if G.has_node(1) else (list(G.nodes)[0] if len(G.nodes) > 0 else [])

        if not entrance_rooms:
            err = "No rooms available in the floor plan."
            return {
                "success": False,
                "path": [],
                "path_indices": [],
                "path_rooms": [],
                "num_steps": 0,
                "total_distance": 0.0,
                "total_distance_px": 0.0,
                "instructions": [],
                "waypoints": [],
                "connected_rooms": [],
                "message": err,
                "error": err,
            }

        # Try entrance rooms in order, finding the one with a path to target
        best_result = None
        min_distance = float("inf")

        for ent_idx in entrance_rooms:
            result = self.navigate(G, ent_idx, target_room_idx)
            if result.get("success", False) and result.get("total_distance_px", float("inf")) < min_distance:
                min_distance = result["total_distance_px"]
                best_result = result

        if best_result:
            return best_result

        err = f"No accessible path found from any identified entrance room ({entrance_rooms}) to Room {target_room_idx}."
        return {
            "success": False,
            "path": [],
            "path_indices": [],
            "path_rooms": [],
            "num_steps": 0,
            "total_distance": 0.0,
            "total_distance_px": 0.0,
            "instructions": [],
            "waypoints": [],
            "connected_rooms": [],
            "message": err,
            "error": err,
        }
