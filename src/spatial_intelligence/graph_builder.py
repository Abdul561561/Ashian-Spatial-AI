from typing import Dict, List, Optional, Tuple, Any
import networkx as nx
import pandas as pd

class SpatialGraphBuilder:
    """Constructs and manages NetworkX topological room-connectivity graphs."""

    def __init__(self):
        pass

    def build_graph(
        self,
        rooms_data: List[Dict[str, Any]] | pd.DataFrame,
        connections_data: List[Dict[str, Any]] | pd.DataFrame,
        doors_data: Optional[List[Dict[str, Any]] | pd.DataFrame] = None
    ) -> nx.Graph:
        """
        Builds a NetworkX graph where nodes represent rooms and edges represent doors.
        Never invents connections when door connectivity is unavailable.
        """
        G = nx.Graph()

        # Normalize rooms data to list of dicts
        rooms_list = rooms_data.to_dict(orient="records") if isinstance(rooms_data, pd.DataFrame) else rooms_data
        conns_list = connections_data.to_dict(orient="records") if isinstance(connections_data, pd.DataFrame) else connections_data
        doors_list = (doors_data.to_dict(orient="records") if isinstance(doors_data, pd.DataFrame) else doors_data) if doors_data is not None else []

        # Find which rooms are entrance rooms
        entrance_room_indices = set()
        for d in doors_list:
            if d.get("is_entrance", False):
                # Check connected rooms string or list
                conn_str = str(d.get("connected_room_indices", ""))
                for part in conn_str.split(","):
                    part = part.strip()
                    if part.isdigit():
                        entrance_room_indices.add(int(part))

        # Add Nodes (Rooms)
        for r in rooms_list:
            rid = int(r["room_index"])
            is_entrance = (rid in entrance_room_indices) or (r.get("raw_class") == "balcony")
            clean_type = str(r.get("room_type", "Unknown")).replace(" [Heuristic]", "").replace(" [Service]", "").replace(" [Outdoor]", "").replace(" [Circulation]", "")
            G.add_node(
                rid,
                room_index=rid,
                room_name=r.get("room_name", f"Room {rid}"),
                room_type=clean_type,
                centroid=(int(r["centroid_x"]), int(r["centroid_y"])),
                centroid_x=int(r["centroid_x"]),
                centroid_y=int(r["centroid_y"]),
                pixel_area=int(r["pixel_area"]),
                bbox=(int(r["bbox_x"]), int(r["bbox_y"]), int(r["bbox_w"]), int(r["bbox_h"])),
                is_entrance=is_entrance,
            )

        # Add Edges (Physical Door Connections)
        for c in conns_list:
            u = int(c["room_1_index"])
            v = int(c["room_2_index"])
            dist = float(c.get("distance_px", 1.0))
            door_idx = int(c.get("door_index", 0))

            if G.has_node(u) and G.has_node(v):
                G.add_edge(
                    u, v,
                    door_index=door_idx,
                    weight=dist,
                    distance_px=dist,
                )

        return G

    def get_room_neighbors(self, G: nx.Graph, room_index: int) -> List[Dict[str, Any]]:
        """Returns adjacent rooms reachable via a direct door."""
        if not G.has_node(room_index):
            return []

        neighbors = []
        for nbr in G.neighbors(room_index):
            edge_data = G.get_edge_data(room_index, nbr)
            nbr_node = G.nodes[nbr]
            neighbors.append({
                "room_index": nbr,
                "room_name": nbr_node["room_name"],
                "room_type": nbr_node["room_type"],
                "door_index": edge_data.get("door_index"),
                "distance_px": edge_data.get("distance_px"),
            })
        return neighbors

    def get_entrance_rooms(self, G: nx.Graph) -> List[int]:
        """Returns room indices that serve as building entrances."""
        return [node for node, data in G.nodes(data=True) if data.get("is_entrance", False)]

    def get_graph_metrics(self, G: nx.Graph) -> Dict[str, Any]:
        """Calculates topological intelligence metrics."""
        num_nodes = G.number_of_nodes()
        num_edges = G.number_of_edges()

        if num_nodes == 0:
            return {
                "num_rooms": 0,
                "num_connections": 0,
                "is_fully_connected": False,
                "num_subgraphs": 0,
                "density": 0.0,
            }

        is_connected = nx.is_connected(G)
        subgraphs = list(nx.connected_components(G))
        density = round(nx.density(G), 3)

        return {
            "num_rooms": num_nodes,
            "num_connections": num_edges,
            "is_fully_connected": is_connected,
            "num_subgraphs": len(subgraphs),
            "density": density,
            "largest_subgraph_size": max(len(c) for c in subgraphs) if subgraphs else 0,
        }
