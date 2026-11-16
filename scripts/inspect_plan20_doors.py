import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cv_engine.loader import FloorPlanLoader
from src.cv_engine.mask_inspector import MaskInspector
from src.cv_engine.extractor import FloorPlanExtractor
import cv2
import numpy as np

loader = FloorPlanLoader()
inspector = MaskInspector()
extractor = FloorPlanExtractor()

img20, mask20, _ = loader.load_pair('20')
binary_door = inspector.get_binary_mask_for_class(mask20, 'door')
contours, _ = cv2.findContours(binary_door, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
print(f"Total door contours found: {len(contours)}")
for i, cnt in enumerate(contours):
    area = cv2.contourArea(cnt)
    bx, by, bw, bh = cv2.boundingRect(cnt)
    print(f"  Contour {i}: area={area}, bbox=({bx}, {by}, {bw}, {bh})")

# Let's inspect other plans: which plans have doors and connections?
for pid in ["1", "2", "3", "4", "5", "7", "12", "20"]:
    _, mask, _ = loader.load_pair(pid)
    ext = extractor.extract_all(mask, plan_id=pid)
    print(f"Plan {pid:2s}: rooms={len(ext['rooms']):2d}, doors={len(ext['doors']):2d}, connections={len(ext['connections']):2d}, windows={len(ext['windows']):2d}")
