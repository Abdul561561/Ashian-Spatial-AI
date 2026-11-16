from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from src.config import CLASS_PALETTE

class MaskInspector:
    """Inspects segmentation masks, identifies classes, and calculates class area distributions."""

    def __init__(self, palette: Dict = None):
        self.palette = palette if palette is not None else CLASS_PALETTE

    def inspect_mask(self, mask_rgb: np.ndarray) -> Dict[str, any]:
        """
        Analyzes pixel distribution in the segmentation mask.
        
        Returns:
            Dictionary containing:
                - total_pixels: int
                - class_breakdown: list of dicts with class metrics
                - dominant_class: str
                - indoor_pixels: int (total excluding background)
                - detected_classes: list of str
        """
        h, w, c = mask_rgb.shape
        total_pixels = h * w

        # Fast color extraction by encoding to 24-bit uint32
        arr_uint32 = (mask_rgb[:, :, 0].astype(np.uint32) << 16) | \
                     (mask_rgb[:, :, 1].astype(np.uint32) << 8) | \
                     (mask_rgb[:, :, 2].astype(np.uint32))

        unique_codes, counts = np.unique(arr_uint32, return_counts=True)
        
        # Aggregate counts by mapped semantic class
        class_pixel_counts = {cls_name: 0 for cls_name in self.palette}
        unclassified_pixels = 0

        for code, count in zip(unique_codes, counts):
            r = int((code >> 16) & 0xFF)
            g = int((code >> 8) & 0xFF)
            b = int(code & 0xFF)
            matched_class = self._match_color_to_class(r, g, b)
            
            if matched_class:
                class_pixel_counts[matched_class] += int(count)
            else:
                unclassified_pixels += int(count)

        # Build detailed class breakdown
        breakdown = []
        indoor_pixels = 0

        for cls_name, info in self.palette.items():
            px_count = class_pixel_counts[cls_name]
            pct = round((px_count / total_pixels) * 100, 2)
            
            if cls_name != "background":
                indoor_pixels += px_count

            breakdown.append({
                "class_name": cls_name,
                "hex_color": info["hex"],
                "rgb": info["rgb"],
                "description": info["description"],
                "pixel_count": px_count,
                "percentage_total": pct,
                "is_present": px_count > 0,
            })

        if unclassified_pixels > 0:
            breakdown.append({
                "class_name": "unclassified_noise",
                "hex_color": "#808080",
                "rgb": (128, 128, 128),
                "description": "Boundary anti-aliasing / interpolation noise",
                "pixel_count": unclassified_pixels,
                "percentage_total": round((unclassified_pixels / total_pixels) * 100, 2),
                "is_present": True,
            })

        detected = [item["class_name"] for item in breakdown if item["is_present"] and item["class_name"] != "background"]
        indoor_pct = round((indoor_pixels / total_pixels) * 100, 2)

        return {
            "total_pixels": total_pixels,
            "indoor_pixels": indoor_pixels,
            "indoor_percentage": indoor_pct,
            "detected_classes": detected,
            "class_breakdown": breakdown,
            "summary_df": pd.DataFrame(breakdown),
        }

    def _match_color_to_class(self, r: int, g: int, b: int) -> str | None:
        """Finds closest class based on Euclidean RGB distance within tolerance."""
        best_class = None
        min_dist = float("inf")

        for cls_name, info in self.palette.items():
            target_r, target_g, target_b = info["rgb"]
            dist = np.sqrt((r - target_r) ** 2 + (g - target_g) ** 2 + (b - target_b) ** 2)
            
            if dist <= info["color_tolerance"] and dist < min_dist:
                min_dist = dist
                best_class = cls_name

        return best_class

    def get_binary_mask_for_class(self, mask_rgb: np.ndarray, class_name: str) -> np.ndarray:
        """Generates a binary uint8 mask (0 or 255) for a given class."""
        if class_name not in self.palette:
            raise ValueError(f"Unknown class name: {class_name}")

        info = self.palette[class_name]
        target = np.array(info["rgb"], dtype=np.float32)
        diff = np.sqrt(np.sum((mask_rgb.astype(np.float32) - target) ** 2, axis=-1))
        binary = (diff <= info["color_tolerance"]).astype(np.uint8) * 255
        return binary
