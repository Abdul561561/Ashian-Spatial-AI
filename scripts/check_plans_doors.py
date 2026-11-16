import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cv_engine.loader import FloorPlanLoader
from src.cv_engine.mask_inspector import MaskInspector
import numpy as np
import cv2

loader = FloorPlanLoader()
inspector = MaskInspector()

for pid in ["1", "5", "7", "12", "20", "2", "3"]:
    img, mask, meta = loader.load_pair(pid)
    door_bin = inspector.get_binary_mask_for_class(mask, 'door')
    room_bin = inspector.get_binary_mask_for_class(mask, 'room')
    door_cnts, _ = cv2.findContours(door_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    room_cnts, _ = cv2.findContours(room_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"Plan {pid:2s}: Size={meta['width']}x{meta['height']}, Door Contours={len(door_cnts):2d}, Door Pixels={np.count_nonzero(door_bin):6d}, Room Contours={len(room_cnts):2d}")
