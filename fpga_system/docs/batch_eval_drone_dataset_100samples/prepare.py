#!/usr/bin/env python3
"""Extract 10 valid-ground-truth frames per video (10 videos = 100 frames),
pack each into cnn_engine's feature format, and compute ground truth in the
256x192 canvas space for later error scoring."""
import sys
import os
import csv

sys.path.insert(0, "/home/nikowarren7/fpga/genesys2-cv-model/scripts")
import cv2
import numpy as np
from pack_image_to_hex import sized, pack, to_lane32_lines
from mcos_decoder import load_groundtruth

VIDEOS = ["001", "012", "023", "034", "045", "056", "067", "078", "089", "100"]
OUTDIR = "/tmp/claude-1000/-home-nikowarren7/8b58bd10-abdc-465b-ac9c-244e40be675c/scratchpad/drone_video_batch"
FRAMES_DIR = os.path.join(OUTDIR, "frames")
HEX_DIR = os.path.join(OUTDIR, "hex")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(HEX_DIR, exist_ok=True)

manifest_rows = []
image_list_lines = []
sample_num = 0

for vid in VIDEOS:
    mp4 = os.path.join(OUTDIR, f"V_DRONE_{vid}.mp4")
    mat = os.path.join(OUTDIR, f"V_DRONE_{vid}_LABELS.mat")
    bboxes = load_groundtruth(mat)
    n_frames = len(bboxes)

    valid_idx = [i for i, b in enumerate(bboxes) if b is not None]
    if not valid_idx:
        print(f"V_DRONE_{vid}: NO valid ground-truth frames, skipping")
        continue
    # 10 frames spread across the valid-frame range (not just the first 10)
    picks = sorted(set(valid_idx[int(i * (len(valid_idx) - 1) / 9)] for i in range(min(10, len(valid_idx)))))
    while len(picks) < 10 and len(picks) < len(valid_idx):
        for i in valid_idx:
            if i not in picks:
                picks.append(i)
                break
    picks = sorted(picks)[:10]

    cap = cv2.VideoCapture(mp4)
    native_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    native_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    # letterbox transform params (matches sized() exactly for this source size)
    scale = min(256 / native_w, 192 / native_h)
    nw, nh = round(native_w * scale), round(native_h * scale)
    px, py = (256 - nw) // 2, (192 - nh) // 2

    for frame_idx in picks:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            print(f"V_DRONE_{vid} frame {frame_idx}: read FAILED, skipping")
            continue
        sample_num += 1
        img_path = os.path.join(FRAMES_DIR, f"{sample_num:03d}_V_DRONE_{vid}_f{frame_idx}.jpg")
        cv2.imwrite(img_path, frame)

        words = pack(img_path, rows=192, row_offset=0)
        lines = to_lane32_lines(words)
        hex_path = os.path.join(HEX_DIR, f"{sample_num:03d}.hex")
        with open(hex_path, "w") as f:
            f.write("\n".join(lines) + "\n")

        gt_cx, gt_cy, gt_w, gt_h = bboxes[frame_idx]
        canvas_gt_cx = gt_cx * scale + px
        canvas_gt_cy = gt_cy * scale + py
        canvas_gt_w = gt_w * scale
        canvas_gt_h = gt_h * scale

        manifest_rows.append({
            "number": sample_num, "video": f"V_DRONE_{vid}", "frame_idx": frame_idx,
            "native_w": native_w, "native_h": native_h,
            "gt_cx_native": gt_cx, "gt_cy_native": gt_cy, "gt_w_native": gt_w, "gt_h_native": gt_h,
            "gt_cx_canvas": canvas_gt_cx, "gt_cy_canvas": canvas_gt_cy,
            "gt_w_canvas": canvas_gt_w, "gt_h_canvas": canvas_gt_h,
            "hex_path": hex_path,
        })
        image_list_lines.append(f"{sample_num} {hex_path}")
    cap.release()
    print(f"V_DRONE_{vid}: {native_w}x{native_h}, {n_frames} frames, {len(valid_idx)} with GT, picked {len(picks)}")

with open(os.path.join(OUTDIR, "manifest.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(manifest_rows[0].keys()))
    w.writeheader()
    w.writerows(manifest_rows)

with open(os.path.join(OUTDIR, "image_list.txt"), "w") as f:
    f.write("\n".join(image_list_lines) + "\n")

print(f"\nTotal samples prepared: {sample_num}")
