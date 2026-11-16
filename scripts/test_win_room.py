import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cv_engine.loader import FloorPlanLoader
from src.cv_engine.extractor import FloorPlanExtractor
import cv2
import numpy as np

loader = FloorPlanLoader()
extractor = FloorPlanExtractor()
img4, mask4, _ = loader.load_pair('4')
res4 = extractor.extract_all(mask4, plan_id='4')
rooms = res4['rooms']
windows = res4['windows']
h, w = mask4.shape[:2]

room_label_map = np.zeros((h, w), dtype=np.int32)
for r in rooms:
    cv2.drawContours(room_label_map, [r['contour']], -1, r['room_index'], thickness=cv2.FILLED)

kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (35, 35))
for win in windows:
    win_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(win_mask, [win['contour']], -1, 255, thickness=cv2.FILLED)
    dilated_win = cv2.dilate(win_mask, kernel)
    touching_rids = np.unique(room_label_map[dilated_win > 0])
    touching_rids = [int(rid) for rid in touching_rids if rid > 0]
    win['connected_room'] = touching_rids

print(f"Plan 4 has {len(rooms)} rooms and {len(windows)} windows:")
no_window_rooms = []
for r in rooms:
    r_wins = [w['window_name'] for w in windows if r['room_index'] in w.get('connected_room', [])]
    count = len(r_wins)
    print(f"  Room {r['room_index']:2d} ({r['room_type']}): {count} windows -> {r_wins}")
    if count == 0:
        no_window_rooms.append(f"Room {r['room_index']}")

print(f"\nRooms in Plan 4 with NO windows: {no_window_rooms}")
