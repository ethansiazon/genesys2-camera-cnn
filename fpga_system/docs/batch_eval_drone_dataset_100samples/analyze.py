#!/usr/bin/env python3
import csv
import math

OUTDIR = "/tmp/claude-1000/-home-nikowarren7/8b58bd10-abdc-465b-ac9c-244e40be675c/scratchpad/drone_video_batch"


def to_signed32(v):
    return v - (1 << 32) if v >= (1 << 31) else v


def to_signed24(v):
    v = v & 0xFFFFFF
    return v - (1 << 24) if v >= (1 << 23) else v


manifest = {int(r["number"]): r for r in csv.DictReader(open(f"{OUTDIR}/manifest.csv"))}
results = list(csv.DictReader(open(f"{OUTDIR}/results.csv")))

rows = []
for r in results:
    num = int(r["number"])
    m = manifest[num]
    x = to_signed32(int(r["x"])) / 65536.0
    y = to_signed32(int(r["y"])) / 65536.0
    w = to_signed32(int(r["w"])) / 65536.0
    h = to_signed32(int(r["h"])) / 65536.0
    conf_raw = int(r["confidence"]) & 0x1FFFF
    confidence = conf_raw / 65536.0
    raw_obj = to_signed24(int(r["raw_objectness"])) / 16384.0
    valid_word = int(r["valid_bit"])
    valid = (valid_word >> 16) & 1

    gt_cx = float(m["gt_cx_canvas"])
    gt_cy = float(m["gt_cy_canvas"])
    dist = math.hypot(x - gt_cx, y - gt_cy)

    rows.append({
        "number": num, "video": m["video"], "frame_idx": m["frame_idx"],
        "x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2),
        "confidence": round(confidence, 5), "raw_objectness": round(raw_obj, 4),
        "valid": valid,
        "gt_cx": round(gt_cx, 2), "gt_cy": round(gt_cy, 2),
        "gt_w": round(float(m["gt_w_canvas"]), 2), "gt_h": round(float(m["gt_h_canvas"]), 2),
        "dist_px": round(dist, 2),
        "cnn_ms": r["cnn_ms"], "dec_ms": r["dec_ms"],
    })

with open(f"{OUTDIR}/analyzed_results.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

# --- aggregate stats ---
W, H = 256.0, 192.0
diag = math.hypot(W, H)
thresh10 = 0.10 * diag

dists = [r["dist_px"] for r in rows]
confs = [r["confidence"] for r in rows]

print(f"n = {len(rows)}")
print(f"mean dist = {sum(dists)/len(dists):.2f}px, median = {sorted(dists)[len(dists)//2]:.2f}px")
print(f"mean confidence = {sum(confs)/len(confs)*100:.2f}%")
under10 = sum(1 for d in dists if d <= thresh10)
print(f"under 10% of diagonal ({thresh10:.1f}px): {under10}/{len(rows)} = {100*under10/len(rows):.1f}%")

print("\nper-video breakdown:")
by_video = {}
for r in rows:
    by_video.setdefault(r["video"], []).append(r)
for vid, vrows in sorted(by_video.items()):
    d = [r["dist_px"] for r in vrows]
    c = [r["confidence"] for r in vrows]
    u = sum(1 for x in d if x <= thresh10)
    print(f"  {vid}: n={len(vrows)} mean_dist={sum(d)/len(d):.1f}px median_dist={sorted(d)[len(d)//2]:.1f}px "
          f"mean_conf={sum(c)/len(c)*100:.1f}% under10%={u}/{len(vrows)}")

print("\nsorted distances (px):", [round(d, 1) for d in sorted(dists)])
print("\nsorted confidences (%):", [round(c*100, 1) for c in sorted(confs)])
