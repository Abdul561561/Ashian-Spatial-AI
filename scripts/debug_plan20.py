import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cv_engine.loader import FloorPlanLoader
from src.cv_engine.mask_inspector import MaskInspector
from src.cv_engine.extractor import FloorPlanExtractor
from src.database.db_manager import DatabaseManager
import cv2
import numpy as np

loader = FloorPlanLoader()
inspector = MaskInspector()
extractor = FloorPlanExtractor()
db = DatabaseManager()

img20, mask20, meta20 = loader.load_pair('20')
report20 = inspector.inspect_mask(mask20)
print('Plan 20 Mask Report keys:', report20.keys())
print('Plan 20 Class breakdown:')
print(report20['summary_df'])

ext20 = extractor.extract_all(mask20, plan_id='20')
print('\nExtracted counts for Plan 20:')
print(f"  Rooms: {len(ext20['rooms'])}")
print(f"  Doors: {len(ext20['doors'])}")
print(f"  Windows: {len(ext20['windows'])}")
print(f"  Connections: {len(ext20['connections'])}")

# Check door dimensions and locations
print('\nDoor details in Plan 20:')
for d in ext20['doors'][:10]:
    print(f"  Door {d['door_id']}: bbox=({d['bbox_x']}, {d['bbox_y']}, {d['bbox_w']}, {d['bbox_h']}), area={d['pixel_area']}")

# Let's inspect connection extraction logic on Plan 20
door_mask = extractor.extract_binary_mask(mask20, 'door')
print(f"\nTotal door pixels in mask: {np.count_nonzero(door_mask)}")

room_mask = extractor.extract_binary_mask(mask20, 'room')
service_mask = extractor.extract_binary_mask(mask20, 'service_room')
balcony_mask = extractor.extract_binary_mask(mask20, 'balcony')
all_rooms_mask = cv2.bitwise_or(room_mask, cv2.bitwise_or(service_mask, balcony_mask))
print(f"Total all rooms pixels: {np.count_nonzero(all_rooms_mask)}")

# Check distance between doors and rooms
# Let's see what happens with dilation of doors
for dilation_r in [15, 22, 30, 40, 50]:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation_r * 2 + 1, dilation_r * 2 + 1))
    dilated_doors = cv2.dilate(door_mask, kernel)
    intersection = cv2.bitwise_and(dilated_doors, all_rooms_mask)
    print(f"Dilation r={dilation_r}px: intersecting pixels with rooms = {np.count_nonzero(intersection)}")
