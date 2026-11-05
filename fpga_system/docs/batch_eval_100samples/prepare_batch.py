#!/usr/bin/env python3
"""Prepare all 50 real photos for a hardware batch run: crop the gallery
composite to just the real photo, detect the green (labeled ground-truth)
box directly via color thresholding (MANIFEST.json only has numeric boxes
for the 20 training examples, not the 30 success/miss examples -- but all
50 images visually draw the same green box, confirmed by inspection), map
it into the 256x192 canvas via the same crop+letterbox the packer uses,
and pack each image to a full-frame lanes32 hex file.
"""
import sys, os, glob, json, csv
sys.path.insert(0, os.path.expanduser("~/fpga/genesys2-cv-model/scripts"))
import cv2
import numpy as np
import pack_image_to_hex as pk

BASE = "extracted/Genesys2_Teammate_Handoff_20261028/cv_model/examples/photo_examples_50"
CROP = (190, 88, 1090, 807)
OUT_HEX = "hex"
os.makedirs(OUT_HEX, exist_ok=True)

manifest = json.load(open(f"{BASE}/MANIFEST.json"))
by_number = {r["number"]: r for r in manifest["images"]}


def detect_green_box(crop_img):
    hsv = cv2.cvtColor(crop_img, cv2.COLOR_BGR2HSV)
    # Pure green (0,255,0)-ish overlay lines: high saturation/value, hue ~60
    lower = np.array([45, 150, 150])
    upper = np.array([75, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    ys, xs = np.where(mask > 0)
    if len(xs) < 10:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def classify(number, filename, row):
    sr = (row or {}).get("source_row") or {}
    outcome = (row or {}).get("outcome")
    group = sr.get("group")
    category = sr.get("category")
    fn = filename.upper()
    if "AIRPLANE" in fn:
        cls = "airplane"
    elif "BIRD" in fn:
        cls = "bird"
    elif "SKY" in fn or "ADE20K" in fn:
        cls = "negative_background"
    elif group == "drone" or "DRONE" in fn or outcome in ("success", "missed_drone", "wrong_location", "poor_box_fit"):
        cls = "drone"
    else:
        cls = "unknown"
    return cls, outcome, group, category


def main():
    rows_out = []
    files = sorted(glob.glob(f"{BASE}/*/*.jpg"))
    for f in files:
        fname = os.path.basename(f)
        number = int(fname.split("_", 1)[0])
        row = by_number.get(number)
        cls, outcome, group, category = classify(number, fname, row)

        img = cv2.imread(f)
        l, t, r, b = CROP
        crop_img = img[t:b, l:r]
        ch, cw = crop_img.shape[:2]

        gbox = detect_green_box(crop_img)
        gt_canvas = None
        if gbox is not None:
            gx0, gy0, gx1, gy1 = gbox
            # Map crop-local pixel box through the same letterbox scale
            # pack_image_to_hex.sized() will apply (scale=min(256/cw,192/ch), centered).
            scale = min(pk.WIDTH / cw, pk.HEIGHT / ch)
            px = (pk.WIDTH - round(cw * scale)) // 2
            py = (pk.HEIGHT - round(ch * scale)) // 2
            cx = ((gx0 + gx1) / 2) * scale + px
            cy = ((gy0 + gy1) / 2) * scale + py
            bw = (gx1 - gx0) * scale
            bh = (gy1 - gy0) * scale
            gt_canvas = (cx, cy, bw, bh)

        hexfile = f"{OUT_HEX}/{number:02d}.hex"
        words = pk.pack(f, rows=pk.HEIGHT, crop=CROP, row_offset=0)
        lines = pk.to_lane32_lines(words)
        with open(hexfile, "w") as out:
            out.write("\n".join(lines) + "\n")

        rows_out.append({
            "number": number, "file": fname, "class": cls, "outcome": outcome,
            "group": group, "category": category,
            "gt_cx": gt_canvas[0] if gt_canvas else "",
            "gt_cy": gt_canvas[1] if gt_canvas else "",
            "gt_w": gt_canvas[2] if gt_canvas else "",
            "gt_h": gt_canvas[3] if gt_canvas else "",
            "hexfile": hexfile,
        })
        print(f"{number:02d} {fname:55s} class={cls:10s} gt={'yes' if gt_canvas else 'no'}")

    with open("batch_manifest.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)
    print(f"\nWrote {len(rows_out)} entries to batch_manifest.csv")


if __name__ == "__main__":
    main()
