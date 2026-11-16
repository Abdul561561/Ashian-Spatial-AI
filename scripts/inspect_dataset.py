import os
import re
import cv2
import numpy as np
from PIL import Image
from collections import Counter
import sys

def rgb_to_hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}".upper()

def find_matching_mask(x_filename, y_filenames):
    name_no_ext = os.path.splitext(x_filename)[0]
    if x_filename in y_filenames:
        return x_filename
    
    target1 = f"{name_no_ext} (2).png"
    if target1 in y_filenames:
        return target1
        
    match = re.match(r"^(\d+)", name_no_ext)
    if match:
        prefix = match.group(1)
        for yf in y_filenames:
            y_base = os.path.splitext(yf)[0]
            if y_base == prefix or y_base.startswith(f"{prefix} (") or y_base.startswith(f"{prefix}_"):
                return yf
    return None

def main():
    x_dir = os.path.join("data", "raw", "X")
    y_dir = os.path.join("data", "raw", "Y")
    
    x_files = sorted(os.listdir(x_dir), key=lambda x: int(os.path.splitext(x)[0]) if os.path.splitext(x)[0].isdigit() else 9999)
    y_files = os.listdir(y_dir)
    
    print(f"Total X images: {len(x_files)}", flush=True)
    print(f"Total Y masks: {len(y_files)}", flush=True)
    
    matched = []
    unmatched_x = []
    for xf in x_files:
        yf = find_matching_mask(xf, y_files)
        if yf:
            matched.append((xf, yf))
        else:
            unmatched_x.append(xf)
            
    print(f"Matched pairs: {len(matched)} / {len(x_files)}", flush=True)
    if unmatched_x:
        print(f"Unmatched: {unmatched_x[:5]}", flush=True)
        
    print("\n--- Inspecting first 5 samples ---", flush=True)
    global_colors = Counter()
    
    for i, (xf, yf) in enumerate(matched[:5]):
        x_path = os.path.join(x_dir, xf)
        y_path = os.path.join(y_dir, yf)
        
        im_x = Image.open(x_path)
        im_y = Image.open(y_path)
        
        print(f"\nSample {i+1}: X='{xf}' ({im_x.size}, {im_x.mode}) | Y='{yf}' ({im_y.size}, {im_y.mode})", flush=True)
        
        arr_y = np.array(im_y.convert("RGB"), dtype=np.uint32)
        # 24-bit encoded integer
        encoded = (arr_y[:, :, 0] << 16) | (arr_y[:, :, 1] << 8) | arr_y[:, :, 2]
        unq, counts = np.unique(encoded, return_counts=True)
        
        order = np.argsort(-counts)
        total_px = encoded.size
        print(f"  Unique colors: {len(unq)}", flush=True)
        for idx in order[:10]:
            code = unq[idx]
            r = int((code >> 16) & 0xFF)
            g = int((code >> 8) & 0xFF)
            b = int(code & 0xFF)
            cnt = int(counts[idx])
            pct = (cnt / total_px) * 100
            global_colors[(r, g, b)] += cnt
            print(f"    RGB ({r:3d}, {g:3d}, {b:3d}) | Hex {rgb_to_hex(r,g,b)} | Pixels: {cnt:7d} ({pct:5.2f}%)", flush=True)

    print("\n--- Summary of colors across first 30 images ---", flush=True)
    for i, (xf, yf) in enumerate(matched[5:30]):
        y_path = os.path.join(y_dir, yf)
        im_y = Image.open(y_path)
        arr_y = np.array(im_y.convert("RGB"), dtype=np.uint32)
        encoded = (arr_y[:, :, 0] << 16) | (arr_y[:, :, 1] << 8) | arr_y[:, :, 2]
        unq, counts = np.unique(encoded, return_counts=True)
        for code, cnt in zip(unq, counts):
            r = int((code >> 16) & 0xFF)
            g = int((code >> 8) & 0xFF)
            b = int(code & 0xFF)
            global_colors[(r, g, b)] += int(cnt)

    print("\nTop 20 most frequent RGB colors across 30 masks:", flush=True)
    for (r, g, b), cnt in global_colors.most_common(20):
        print(f"  RGB: ({r:3d}, {g:3d}, {b:3d}) | Hex: {rgb_to_hex(r,g,b)} | Total Pixels: {cnt}", flush=True)

if __name__ == "__main__":
    main()
