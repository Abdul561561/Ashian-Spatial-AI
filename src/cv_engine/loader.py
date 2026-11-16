import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image

from src.config import DATASET_X_DIR, DATASET_Y_DIR

class FloorPlanLoader:
    """Loads and manages floor plans and corresponding segmentation masks."""

    def __init__(self, x_dir: Optional[Path] = None, y_dir: Optional[Path] = None):
        self.x_dir = Path(x_dir) if x_dir else DATASET_X_DIR
        self.y_dir = Path(y_dir) if y_dir else DATASET_Y_DIR
        self._matched_pairs: List[Dict[str, str]] = []
        self._indexed = False
        self._index_dataset()

    def _index_dataset(self) -> None:
        """Indexes and pairs original floor plans with their segmentation masks."""
        if not self.x_dir.exists() or not self.y_dir.exists():
            self._matched_pairs = []
            self._indexed = True
            return

        x_files = [f for f in os.listdir(self.x_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        y_files = [f for f in os.listdir(self.y_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        def sort_key(name: str):
            base = os.path.splitext(name)[0]
            digits = re.findall(r"\d+", base)
            return int(digits[0]) if digits else 999999

        x_files.sort(key=sort_key)
        y_files_set = set(y_files)

        matched = []
        for xf in x_files:
            yf = self._find_matching_mask(xf, y_files_set, y_files)
            if yf:
                plan_id = os.path.splitext(xf)[0]
                matched.append({
                    "plan_id": plan_id,
                    "image_file": xf,
                    "mask_file": yf,
                    "image_path": str(self.x_dir / xf),
                    "mask_path": str(self.y_dir / yf),
                })

        self._matched_pairs = matched
        self._indexed = True

    @staticmethod
    def _find_matching_mask(x_filename: str, y_set: set, y_list: List[str]) -> Optional[str]:
        """Finds matching mask filename based on dataset naming patterns."""
        base = os.path.splitext(x_filename)[0]

        # Exact match
        if x_filename in y_set:
            return x_filename

        # Pattern: "X (2).png"
        cand1 = f"{base} (2).png"
        if cand1 in y_set:
            return cand1

        cand1_jpg = f"{base} (2).jpg"
        if cand1_jpg in y_set:
            return cand1_jpg

        # Pattern: leading integer match
        match = re.match(r"^(\d+)", base)
        if match:
            prefix = match.group(1)
            for yf in y_list:
                y_base = os.path.splitext(yf)[0]
                if (y_base == prefix or 
                    y_base.startswith(f"{prefix} (") or 
                    y_base.startswith(f"{prefix}_")):
                    return yf
        return None

    def list_floor_plans(self) -> List[Dict[str, str]]:
        """Returns list of all available matched floor plan pairs."""
        if not self._indexed:
            self._index_dataset()
        return self._matched_pairs

    def get_plan_by_id(self, plan_id: str) -> Optional[Dict[str, str]]:
        """Retrieves a specific floor plan by its plan_id (e.g. '1', '10')."""
        for item in self.list_floor_plans():
            if item["plan_id"] == str(plan_id):
                return item
        return None

    def load_pair(self, plan_id: str) -> Tuple[np.ndarray, np.ndarray, Dict[str, any]]:
        """
        Loads the floor plan original image and segmentation mask in RGB format.
        
        Returns:
            (image_rgb, mask_rgb, metadata_dict)
        """
        plan_meta = self.get_plan_by_id(plan_id)
        if not plan_meta:
            raise FileNotFoundError(f"Floor plan '{plan_id}' not found in dataset.")

        image_path = plan_meta["image_path"]
        mask_path = plan_meta["mask_path"]

        # Read images using PIL to guarantee clean RGB color space
        pil_img = Image.open(image_path).convert("RGB")
        pil_mask = Image.open(mask_path).convert("RGB")

        # Verify dimensions match
        if pil_img.size != pil_mask.size:
            # Resize mask to match original image if needed
            pil_mask = pil_mask.resize(pil_img.size, Image.NEAREST)

        img_np = np.array(pil_img)
        mask_np = np.array(pil_mask)

        metadata = {
            "plan_id": plan_id,
            "image_file": plan_meta["image_file"],
            "mask_file": plan_meta["mask_file"],
            "width": img_np.shape[1],
            "height": img_np.shape[0],
            "channels": img_np.shape[2],
            "total_pixels": img_np.shape[0] * img_np.shape[1],
            "aspect_ratio": round(img_np.shape[1] / img_np.shape[0], 3),
            "image_size_kb": round(os.path.getsize(image_path) / 1024, 2),
            "mask_size_kb": round(os.path.getsize(mask_path) / 1024, 2),
        }

        return img_np, mask_np, metadata
