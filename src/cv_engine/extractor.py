import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple
from src.cv_engine.mask_inspector import MaskInspector

class FloorPlanExtractor:
    """Extracts architectural entities: rooms, doors, windows, walls, and topological connections."""

    def __init__(self, inspector: Optional[MaskInspector] = None, min_room_area: int = 500, min_door_area: int = 40):
        self.inspector = inspector if inspector else MaskInspector()
        self.min_room_area = min_room_area
        self.min_door_area = min_door_area

    def extract_all(self, mask_rgb: np.ndarray, plan_id: str = "unknown") -> Dict[str, any]:
        """
        Executes complete structural extraction on a segmentation mask.
        """
        inspection = self.inspector.inspect_mask(mask_rgb)
        h, w, _ = mask_rgb.shape

        # 1. Extract Rooms
        raw_rooms = self._extract_rooms(mask_rgb)

        # 2. Extract Doors
        doors = self._extract_doors(mask_rgb)

        # 3. Extract Windows and associate with adjacent rooms
        windows, rooms = self._extract_windows(mask_rgb, raw_rooms)

        # 4. Extract Walls
        walls, wall_pixel_area = self._extract_walls(mask_rgb)

        # 5. Connect Rooms via Doors (Spatial Proximity)
        connections, updated_doors = self._compute_room_connections(rooms, doors, mask_rgb.shape, mask_rgb=mask_rgb)

        # 6. Generate Validation Report & Confidence Score
        validation = self._generate_validation_report(
            rooms=rooms,
            doors=updated_doors,
            windows=windows,
            connections=connections,
            total_pixels=h * w,
            indoor_pixels=inspection["indoor_pixels"]
        )

        return {
            "plan_id": plan_id,
            "dimensions": {"width": w, "height": h},
            "inspection": inspection,
            "rooms": rooms,
            "doors": updated_doors,
            "windows": windows,
            "walls": walls,
            "wall_pixel_area": wall_pixel_area,
            "connections": connections,
            "validation": validation,
        }

    def _extract_rooms(self, mask_rgb: np.ndarray) -> List[Dict[str, any]]:
        """Extracts individual room components and classifies them by spatial properties."""
        rooms = []
        room_counter = 1

        # We extract from 'room', 'service_room', and 'balcony'
        room_classes = [
            ("room", "General Room"),
            ("service_room", "Bathroom / Restroom"),
            ("balcony", "Balcony / Terrace"),
        ]

        # First collect all candidate contours
        candidates = []
        for cls_name, default_label in room_classes:
            binary = self.inspector.get_binary_mask_for_class(mask_rgb, cls_name)
            
            # Morphological cleanup to close tiny pinholes
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

            contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area >= self.min_room_area:
                    candidates.append({
                        "contour": cnt,
                        "area": area,
                        "raw_class": cls_name,
                        "default_label": default_label,
                    })

        # Sort candidates descending by area
        candidates.sort(key=lambda c: -c["area"])

        total_candidates = len(candidates)
        primary_rooms = [c for c in candidates if c["raw_class"] == "room"]
        max_room_area = primary_rooms[0]["area"] if primary_rooms else 1.0

        for cand in candidates:
            cnt = cand["contour"]
            area = float(cand["area"])
            bx, by, bw, bh = cv2.boundingRect(cnt)
            
            # Centroid
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
            else:
                cx = bx + bw // 2
                cy = by + bh // 2

            aspect_ratio = round(max(bw, bh) / (min(bw, bh) + 1e-5), 2)
            
            # Solidity (Area / Convex Hull Area)
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = round(area / (hull_area + 1e-5), 3)

            # Explicit separation of Detected Semantic Class vs Inferred Typology
            if cand["raw_class"] == "service_room":
                semantic_class = "Service Room / Sanitation"
                spatial_category = "Service / Sanitation"
                is_habitable = False
                inferred_type = "Bathroom / WC (Heuristic)"
                room_type = "Bathroom / WC"
            elif cand["raw_class"] == "balcony":
                semantic_class = "Balcony / Outdoor Area"
                spatial_category = "Balcony / Outdoor Area"
                is_habitable = False
                inferred_type = "Balcony / Terrace (Heuristic)"
                room_type = "Balcony / Terrace"
            else:
                semantic_class = "Primary Enclosed Room"
                # Classify based on relative area rank & morphology (strictly labeled as heuristic)
                rel_size = area / max_room_area
                if aspect_ratio > 3.0:
                    spatial_category = "Circulation / Corridor"
                    is_habitable = True
                    inferred_type = "Hallway / Corridor (Elongation Heuristic)"
                    room_type = "Hallway / Corridor"
                elif rel_size >= 0.70:
                    spatial_category = "Habitable Room"
                    is_habitable = True
                    inferred_type = "Living / Main Space (Area-Ranked Heuristic)"
                    room_type = "Living Room"
                elif rel_size >= 0.45:
                    spatial_category = "Habitable Room"
                    is_habitable = True
                    inferred_type = "Master Bedroom Area (Area-Ranked Heuristic)"
                    room_type = "Master Bedroom"
                elif rel_size >= 0.25:
                    spatial_category = "Habitable Room"
                    is_habitable = True
                    inferred_type = "Secondary Bedroom Area (Area-Ranked Heuristic)"
                    room_type = "Bedroom"
                elif rel_size >= 0.12:
                    spatial_category = "Habitable Room"
                    is_habitable = True
                    inferred_type = "Kitchen / Dining Area (Area-Ranked Heuristic)"
                    room_type = "Kitchen / Dining"
                else:
                    spatial_category = "Habitable Room"
                    is_habitable = True
                    inferred_type = "Utility / Study Room (Area-Ranked Heuristic)"
                    room_type = "Utility / Study"

            # Confidence score based on solidity, convexity, and sensible area
            confidence = min(1.0, max(0.5, round(solidity * 0.7 + (1.0 if area > 2000 else 0.8) * 0.3, 2)))

            rooms.append({
                "room_index": room_counter,
                "room_name": f"Room {room_counter}",
                "room_type": room_type,
                "raw_class": cand["raw_class"],
                "semantic_class": semantic_class,
                "spatial_category": spatial_category,
                "is_habitable_room": is_habitable,
                "inferred_type": inferred_type,
                "window_count": 0,
                "adjacent_windows": [],
                "bbox_x": int(bx),
                "bbox_y": int(by),
                "bbox_w": int(bw),
                "bbox_h": int(bh),
                "centroid_x": int(cx),
                "centroid_y": int(cy),
                "pixel_area": int(area),
                "aspect_ratio": aspect_ratio,
                "solidity": solidity,
                "confidence": confidence,
                "contour": cnt,
            })
            room_counter += 1

        return rooms

    def _extract_doors(self, mask_rgb: np.ndarray) -> List[Dict[str, any]]:
        """Extracts individual door openings from the segmentation mask."""
        doors = []
        binary = self.inspector.get_binary_mask_for_class(mask_rgb, "door")
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        door_counter = 1
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area >= self.min_door_area:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                cx = int(bx + bw / 2)
                cy = int(by + bh / 2)
                orientation = "horizontal" if bw >= bh else "vertical"

                doors.append({
                    "door_index": door_counter,
                    "door_name": f"Door {door_counter}",
                    "bbox_x": int(bx),
                    "bbox_y": int(by),
                    "bbox_w": int(bw),
                    "bbox_h": int(bh),
                    "centroid_x": int(cx),
                    "centroid_y": int(cy),
                    "pixel_area": int(area),
                    "orientation": orientation,
                    "contour": cnt,
                    "connected_rooms": [],
                    "is_entrance": False,
                })
                door_counter += 1

        return doors

    def _extract_windows(self, mask_rgb: np.ndarray, rooms: List[Dict[str, any]]) -> Tuple[List[Dict[str, any]], List[Dict[str, any]]]:
        """Extracts window openings and identifies adjacent room association via morphological proximity."""
        h, w = mask_rgb.shape[:2]
        windows = []
        binary = self.inspector.get_binary_mask_for_class(mask_rgb, "window")
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Room label map for spatial intersection
        room_label_map = np.zeros((h, w), dtype=np.int32)
        for r in rooms:
            cv2.drawContours(room_label_map, [r["contour"]], -1, r["room_index"], thickness=cv2.FILLED)

        # Dilation kernel for window-to-room wall crossing
        win_dilation = max(26, int(max(h, w) * 0.014))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (win_dilation, win_dilation))

        win_counter = 1
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area >= 30:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                cx = int(bx + bw / 2)
                cy = int(by + bh / 2)
                orientation = "horizontal" if bw >= bh else "vertical"

                # Detect adjacent room by dilating window opening into room boundary
                win_mask = np.zeros((h, w), dtype=np.uint8)
                cv2.drawContours(win_mask, [cnt], -1, 255, thickness=cv2.FILLED)
                dilated_win = cv2.dilate(win_mask, kernel)
                touching_rids = np.unique(room_label_map[dilated_win > 0])
                touching_rids = [int(rid) for rid in touching_rids if rid > 0]
                connected_rid = touching_rids[0] if touching_rids else None

                windows.append({
                    "window_index": win_counter,
                    "window_name": f"Window {win_counter}",
                    "bbox_x": int(bx),
                    "bbox_y": int(by),
                    "bbox_w": int(bw),
                    "bbox_h": int(bh),
                    "centroid_x": int(cx),
                    "centroid_y": int(cy),
                    "pixel_area": int(area),
                    "orientation": orientation,
                    "contour": cnt,
                    "connected_room_index": connected_rid,
                })
                win_counter += 1

        # Correlate window counts back to individual rooms
        for r in rooms:
            r_wins = [win["window_index"] for win in windows if win.get("connected_room_index") == r["room_index"]]
            r["window_count"] = len(r_wins)
            r["adjacent_windows"] = r_wins

        return windows, rooms

    def _extract_walls(self, mask_rgb: np.ndarray) -> Tuple[List[Dict[str, any]], int]:
        """Extracts structural wall elements."""
        walls = []
        binary = self.inspector.get_binary_mask_for_class(mask_rgb, "wall")
        total_wall_area = int(np.sum(binary > 0))

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        wall_counter = 1
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area >= 100:
                bx, by, bw, bh = cv2.boundingRect(cnt)
                walls.append({
                    "wall_index": wall_counter,
                    "bbox_x": int(bx),
                    "bbox_y": int(by),
                    "bbox_w": int(bw),
                    "bbox_h": int(bh),
                    "pixel_area": int(area),
                })
                wall_counter += 1

        return walls, total_wall_area

    def _compute_room_connections(
        self,
        rooms: List[Dict],
        doors: List[Dict],
        shape: Tuple[int, int, int],
        mask_rgb: Optional[np.ndarray] = None
    ) -> Tuple[List[Dict[str, any]], List[Dict]]:
        """
        Determines topological room-to-room connectivity via doors and physical passages using morphological dilation.
        Never invents connections if spaces do not physically connect.
        """
        h, w = shape[:2]
        connections = []

        # Create labeled room map where pixel value = room_index
        room_label_map = np.zeros((h, w), dtype=np.int32)
        for r in rooms:
            cv2.drawContours(room_label_map, [r["contour"]], -1, r["room_index"], thickness=cv2.FILLED)

        # 1. Door-based connections with resolution-adaptive dilation
        dilation_radius = max(34, int(max(h, w) * 0.016))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation_radius, dilation_radius))

        connection_counter = 1
        seen_pairs = set()

        for door in doors:
            door_mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(door_mask, [door["contour"]], -1, 255, thickness=cv2.FILLED)

            dilated_door = cv2.dilate(door_mask, kernel, iterations=1)

            touching_room_ids = np.unique(room_label_map[dilated_door > 0])
            touching_room_ids = sorted([int(rid) for rid in touching_room_ids if rid > 0])
            door["connected_rooms"] = touching_room_ids

            if len(touching_room_ids) >= 2:
                for i in range(len(touching_room_ids)):
                    for j in range(i + 1, len(touching_room_ids)):
                        r1_id = touching_room_ids[i]
                        r2_id = touching_room_ids[j]
                        pair_key = (min(r1_id, r2_id), max(r1_id, r2_id))
                        if pair_key in seen_pairs:
                            continue
                        seen_pairs.add(pair_key)

                        r1 = next(r for r in rooms if r["room_index"] == r1_id)
                        r2 = next(r for r in rooms if r["room_index"] == r2_id)
                        dist_px = round(float(np.sqrt((r1["centroid_x"] - r2["centroid_x"])**2 + (r1["centroid_y"] - r2["centroid_y"])**2)), 1)

                        connections.append({
                            "connection_index": connection_counter,
                            "door_index": door["door_index"],
                            "room_1_index": r1_id,
                            "room_2_index": r2_id,
                            "room_1_name": r1["room_name"],
                            "room_2_name": r2["room_name"],
                            "distance_px": dist_px,
                            "connection_type": "door",
                        })
                        connection_counter += 1
            elif len(touching_room_ids) == 1:
                door["is_entrance"] = True

        # 2. Open architectural passage / corridor threshold detection for plans with verified door annotations
        if mask_rgb is not None and len(doors) > 1:
            walls_bin = self.inspector.get_binary_mask_for_class(mask_rgb, "wall")
            kernel_pass = cv2.getStructuringElement(cv2.MORPH_RECT, (16, 16))
            for r1 in rooms:
                m1 = (room_label_map == r1["room_index"]).astype(np.uint8)
                dil1 = cv2.dilate(m1, kernel_pass)
                touching = [int(x) for x in np.unique(room_label_map[dil1 > 0]) if x > r1["room_index"]]
                for t in touching:
                    pair_key = (min(r1["room_index"], t), max(r1["room_index"], t))
                    if pair_key in seen_pairs:
                        continue
                    m2 = (room_label_map == t).astype(np.uint8)
                    dil2 = cv2.dilate(m2, kernel_pass)
                    overlap = (dil1 > 0) & (dil2 > 0)
                    wall_overlap = np.sum((overlap > 0) & (walls_bin > 0))
                    total_overlap = np.sum(overlap > 0)
                    wall_ratio = wall_overlap / (total_overlap + 1e-5)
                    if total_overlap >= 150 and wall_ratio < 0.50:
                        seen_pairs.add(pair_key)
                        r2 = next(r for r in rooms if r["room_index"] == t)
                        dist_px = round(float(np.sqrt((r1["centroid_x"] - r2["centroid_x"])**2 + (r1["centroid_y"] - r2["centroid_y"])**2)), 1)
                        connections.append({
                            "connection_index": connection_counter,
                            "door_index": 0,
                            "room_1_index": r1["room_index"],
                            "room_2_index": t,
                            "room_1_name": r1["room_name"],
                            "room_2_name": r2["room_name"],
                            "distance_px": dist_px,
                            "connection_type": "open_passage",
                        })
                        connection_counter += 1

        return connections, doors

    def _generate_validation_report(self, rooms: List[Dict], doors: List[Dict], windows: List[Dict], connections: List[Dict], total_pixels: int, indoor_pixels: int) -> Dict[str, any]:
        """Generates extraction quality metrics and confidence report."""
        num_rooms = len(rooms)
        num_doors = len(doors)
        num_windows = len(windows)
        num_connections = len(connections)

        primary_rooms = [r for r in rooms if r.get("raw_class") == "room"]
        corridors = [r for r in primary_rooms if r.get("spatial_category") == "Circulation / Corridor"]
        habitable_rooms = [r for r in primary_rooms if r.get("spatial_category") != "Circulation / Corridor"]
        service_rooms = [r for r in rooms if r.get("raw_class") == "service_room"]
        balconies = [r for r in rooms if r.get("raw_class") == "balcony"]

        num_habitable = len(habitable_rooms)
        num_corridors = len(corridors)
        num_service = len(service_rooms)
        num_balconies = len(balconies)
        total_detected = len(rooms)
        
        breakdown_str = (
            f"{len(primary_rooms)} Primary Rooms ({num_habitable} Habitable, {num_corridors} Corridors) | "
            f"{num_service} Service | {num_balconies} Balconies ({total_detected} Total Detected Regions)"
        )

        total_room_area = sum(r["pixel_area"] for r in rooms)
        room_indoor_ratio = round((total_room_area / (indoor_pixels + 1e-5)) * 100, 1)

        # Connected rooms coverage
        connected_room_indices = set()
        for c in connections:
            connected_room_indices.add(c["room_1_index"])
            connected_room_indices.add(c["room_2_index"])

        connectivity_ratio = round((len(connected_room_indices) / (num_rooms + 1e-5)) * 100, 1) if num_rooms > 0 else 0.0

        # Calculate overall extraction confidence
        score = 0.0
        if num_rooms > 0:
            score += 40.0  # Successfully extracted rooms
            avg_room_conf = np.mean([r["confidence"] for r in rooms])
            score += avg_room_conf * 25.0
        if num_doors > 0:
            score += 15.0
        if num_connections > 0:
            score += min(20.0, (connectivity_ratio / 100.0) * 20.0)

        confidence_score = round(min(100.0, score), 1)

        status = "VALIDATED" if confidence_score >= 70.0 else ("WARNING" if confidence_score >= 45.0 else "DEFICIENT")

        limitations = [
            "Scale calibration not present in Kaggle annotation files; all spatial areas and distances are measured strictly in pixels.",
            "Room functional typologies (Living Room, Bedroom, etc.) are estimated heuristically using relative room sizes and CVC-FP semantic masks.",
            "Door-room passages are topologically derived from pixel dilation and contour proximity. Hidden or non-annotated portals cannot be inferred.",
            "CVC-FP semantic masks include exterior balconies, facade sill strips, and wall dividers under spatial classes; distinct from conventional habitable room counts.",
        ]

        return {
            "num_rooms": num_rooms,
            "total_detected_regions": total_detected,
            "num_habitable_rooms": num_habitable,
            "num_primary_rooms": len(primary_rooms),
            "num_service_rooms": num_service,
            "num_balconies": num_balconies,
            "num_corridors": num_corridors,
            "room_count_breakdown": breakdown_str,
            "num_doors": num_doors,
            "num_windows": num_windows,
            "num_connections": num_connections,
            "total_room_area_px": total_room_area,
            "room_indoor_coverage_pct": room_indoor_ratio,
            "connected_rooms_count": len(connected_room_indices),
            "connectivity_ratio_pct": connectivity_ratio,
            "extraction_confidence_score": confidence_score,
            "validation_status": status,
            "limitations": limitations,
        }
