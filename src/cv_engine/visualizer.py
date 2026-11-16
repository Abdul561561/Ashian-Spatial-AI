import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.config import OUTPUT_DIR

# Modern architectural palette for rooms (distinct soft pastels)
ROOM_COLOR_PALETTE = [
    (56, 128, 255),   # Cobalt Blue
    (46, 213, 115),   # Emerald Green
    (255, 159, 26),   # Tangerine Orange
    (155, 89, 182),   # Amethyst Purple
    (235, 77, 75),    # Crimson Red
    (26, 188, 156),   # Turquoise
    (241, 196, 15),   # Warm Yellow
    (52, 152, 219),   # Sky Blue
    (230, 126, 34),   # Ochre
    (149, 165, 166),  # Slate Silver
    (243, 104, 224),  # Pink Lavender
    (34, 112, 147),   # Deep Teal
    (179, 55, 113),   # Berry
    (30, 144, 255),   # Dodger Blue
    (255, 107, 129),  # Coral
]

class FloorPlanVisualizer:
    """Renders overlays, annotations, room highlights, and navigation routes on floor plans."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir) if output_dir else OUTPUT_DIR / "overlays"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create_overlay(
        self,
        original_img: np.ndarray,
        extraction_data: Dict[str, any],
        alpha: float = 0.35,
        highlight_room_id: Optional[int] = None,
        highlight_door_id: Optional[int] = None,
        show_doors: bool = True,
        show_windows: bool = True,
        show_labels: bool = True,
    ) -> np.ndarray:
        """
        Creates a high-clarity overlay on the original floor plan image.
        """
        # Ensure working on a 3-channel RGB image
        overlay = original_img.copy()
        if len(overlay.shape) == 2:
            overlay = cv2.cvtColor(overlay, cv2.COLOR_GRAY2RGB)
        elif overlay.shape[2] == 4:
            overlay = cv2.cvtColor(overlay, cv2.COLOR_RGBA2RGB)

        h, w = overlay.shape[:2]
        colored_mask = np.zeros_like(overlay)

        rooms = extraction_data.get("rooms", [])
        doors = extraction_data.get("doors", [])
        windows = extraction_data.get("windows", [])

        # 1. Fill room contours
        for i, room in enumerate(rooms):
            rid = room["room_index"]
            color = ROOM_COLOR_PALETTE[(rid - 1) % len(ROOM_COLOR_PALETTE)]
            
            # If a specific room is highlighted, make others dimmer
            if highlight_room_id is not None:
                if rid == highlight_room_id:
                    color = (0, 255, 200)  # Bright neon cyan/green
                else:
                    color = tuple(int(c * 0.4) for c in color)

            cnt = room.get("contour")
            if cnt is not None:
                cv2.drawContours(colored_mask, [cnt], -1, color, thickness=cv2.FILLED)

        # Blend room colors onto floor plan
        cv2.addWeighted(colored_mask, alpha, overlay, 1.0, 0, overlay)

        # 2. Draw room outlines and labels
        for room in rooms:
            rid = room["room_index"]
            cnt = room.get("contour")
            is_hl = (highlight_room_id == rid)

            line_color = (0, 255, 180) if is_hl else (20, 20, 20)
            thickness = 3 if is_hl else 2

            if cnt is not None:
                cv2.drawContours(overlay, [cnt], -1, line_color, thickness=thickness)

            if show_labels:
                cx = room["centroid_x"]
                cy = room["centroid_y"]
                label = f"R{rid}: {room['room_type']}"
                self._draw_label_badge(overlay, label, cx, cy, is_highlighted=is_hl)

        # 3. Draw Doors
        if show_doors:
            for door in doors:
                did = door["door_index"]
                is_hl_d = (highlight_door_id == did)
                door_color = (0, 255, 255) if is_hl_d else (255, 140, 20)  # Vibrant orange
                
                bx, by, bw, bh = door["bbox_x"], door["bbox_y"], door["bbox_w"], door["bbox_h"]
                cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), door_color, thickness=-1)
                cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), (0, 0, 0), thickness=1)

                if show_labels and is_hl_d:
                    self._draw_label_badge(overlay, f"Door {did}", bx + bw // 2, by - 10, is_highlighted=True)

        # 4. Draw Windows
        if show_windows:
            for win in windows:
                bx, by, bw, bh = win["bbox_x"], win["bbox_y"], win["bbox_w"], win["bbox_h"]
                cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), (255, 215, 0), thickness=-1) # Gold
                cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), (40, 40, 40), thickness=1)

        return overlay

    def _draw_label_badge(self, img: np.ndarray, text: str, cx: int, cy: int, is_highlighted: bool = False):
        """Draws a clean pill-shaped label badge at coordinate (cx, cy)."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.50
        thickness = 1
        (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)

        pad_x, pad_y = 6, 4
        x1 = max(0, cx - tw // 2 - pad_x)
        y1 = max(0, cy - th // 2 - pad_y)
        x2 = min(img.shape[1], x1 + tw + pad_x * 2)
        y2 = min(img.shape[0], y1 + th + pad_y * 2)

        bg_color = (0, 200, 160) if is_highlighted else (25, 30, 40)
        text_color = (0, 0, 0) if is_highlighted else (255, 255, 255)

        # Badge background
        cv2.rectangle(img, (x1, y1), (x2, y2), bg_color, thickness=-1)
        cv2.rectangle(img, (x1, y1), (x2, y2), (200, 200, 200), thickness=1)
        
        # Badge text
        text_x = x1 + pad_x
        text_y = y1 + th + pad_y - 2
        cv2.putText(img, text, (text_x, text_y), font, font_scale, text_color, thickness, cv2.LINE_AA)

    def draw_navigation_route(
        self,
        base_overlay: np.ndarray,
        waypoints: List[Tuple[int, int]],
        room_names: List[str],
    ) -> np.ndarray:
        """
        Draws animated-style dashed navigation path between room centroids.
        Handles single-room waypoints (source == destination) and multi-step paths.
        """
        result = base_overlay.copy()

        if not waypoints or len(waypoints) < 1:
            return result

        if len(waypoints) == 1:
            # Single-room waypoint (source == target)
            pt = (int(waypoints[0][0]), int(waypoints[0][1]))
            cv2.circle(result, pt, 14, (0, 215, 255), thickness=-1)  # Gold
            cv2.circle(result, pt, 17, (255, 255, 255), thickness=2)
            cv2.putText(result, "HERE", (pt[0] - 22, pt[1] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 180, 255), 2)
            return result

        # Draw glowing path line
        for i in range(len(waypoints) - 1):
            pt1 = (int(waypoints[i][0]), int(waypoints[i][1]))
            pt2 = (int(waypoints[i + 1][0]), int(waypoints[i + 1][1]))

            # Glow aura (neon cyan)
            cv2.line(result, pt1, pt2, (0, 255, 220), thickness=7, lineType=cv2.LINE_AA)
            # Center bright white line
            cv2.line(result, pt1, pt2, (255, 255, 255), thickness=3, lineType=cv2.LINE_AA)

            # Arrow indicating direction
            mid_x = (pt1[0] + pt2[0]) // 2
            mid_y = (pt1[1] + pt2[1]) // 2
            cv2.arrowedLine(result, pt1, (mid_x, mid_y), (0, 200, 255), thickness=3, tipLength=0.35)

        # Draw Start Marker
        start_pt = (int(waypoints[0][0]), int(waypoints[0][1]))
        cv2.circle(result, start_pt, 12, (46, 213, 115), thickness=-1)  # Green
        cv2.circle(result, start_pt, 14, (255, 255, 255), thickness=2)
        cv2.putText(result, "START", (start_pt[0] - 25, start_pt[1] - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 180, 50), 2)

        # Draw End Marker
        end_pt = (int(waypoints[-1][0]), int(waypoints[-1][1]))
        cv2.circle(result, end_pt, 12, (235, 77, 75), thickness=-1)  # Red
        cv2.circle(result, end_pt, 14, (255, 255, 255), thickness=2)
        cv2.putText(result, "GOAL", (end_pt[0] - 22, end_pt[1] - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 20, 20), 2)

        return result

    def save_sample_overlays(self, loader, extractor, plan_ids: List[str] = ("1", "2", "3")) -> List[str]:
        """Generates and saves visual overlays for specified floor plans."""
        saved_paths = []
        for pid in plan_ids:
            try:
                img_rgb, mask_rgb, _ = loader.load_pair(pid)
                extracted = extractor.extract_all(mask_rgb, plan_id=pid)
                overlay = self.create_overlay(img_rgb, extracted)
                
                out_path = self.output_dir / f"overlay_floorplan_{pid}.png"
                Image.fromarray(overlay).save(out_path)
                saved_paths.append(str(out_path))
            except Exception as e:
                print(f"Error saving overlay for plan {pid}: {e}")

        return saved_paths
