#!/usr/bin/env python3
import csv
import math

manifest = {}
with open("batch_manifest.csv") as f:
    for row in csv.DictReader(f):
        manifest[int(row["number"])] = row

results = []
with open("full_batch_results.csv") as f:
    for row in csv.DictReader(f):
        results.append(row)


def to_signed32(v):
    v = int(v)
    return v - (1 << 32) if v >= (1 << 31) else v


def to_signed24(v):
    v = int(v) & 0xFFFFFF
    return v - (1 << 24) if v >= (1 << 23) else v


rows_out = []
for r in results:
    if "TIMEOUT" in (r.get("x") or "") or r.get("x") in (None, ""):
        rows_out.append({**r, "status": "TIMEOUT_OR_MISSING"})
        continue
    num = int(r["number"])
    m = manifest.get(num, {})
    x = to_signed32(r["x"]) / 65536.0
    y = to_signed32(r["y"]) / 65536.0
    w = to_signed32(r["w"]) / 65536.0
    h = to_signed32(r["h"]) / 65536.0
    conf_raw = int(r["confidence"]) & 0xFFFFFFFF
    conf = (conf_raw & 0x1FFFF) / 65536.0  # ap_uint<17>
    obj_raw = int(r["raw_objectness"]) & 0xFFFFFFFF
    obj = to_signed24(obj_raw) / 16384.0
    valid_raw = int(r["valid_bit"]) & 0xFFFFFFFF
    valid = (valid_raw >> 16) & 1

    gt_dist = ""
    if m.get("gt_cx"):
        gcx, gcy = float(m["gt_cx"]), float(m["gt_cy"])
        gt_dist = round(math.hypot(x - gcx, y - gcy), 1)

    rows_out.append({
        "number": num, "pass": r["pass"], "file": m.get("file", ""),
        "class": m.get("class", ""), "outcome": m.get("outcome", ""),
        "cnn_ms": r["cnn_ms"], "dec_ms": r["dec_ms"],
        "x": round(x, 1), "y": round(y, 1), "w": round(w, 1), "h": round(h, 1),
        "confidence": round(conf, 5), "raw_objectness": round(obj, 3), "valid": valid,
        "gt_cx": m.get("gt_cx", ""), "gt_cy": m.get("gt_cy", ""),
        "dist_to_gt_px": gt_dist,
        "status": "OK",
    })

with open("analyzed_results.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
    w.writeheader()
    w.writerows(rows_out)

ok_rows = [r for r in rows_out if r["status"] == "OK"]
print(f"Total result rows: {len(rows_out)}  OK: {len(ok_rows)}  Timeouts/missing: {len(rows_out)-len(ok_rows)}")

# Repeatability check: pass1 vs pass2 per image
by_image = {}
for r in ok_rows:
    by_image.setdefault(r["number"], []).append(r)
mismatches = 0
for num, rs in by_image.items():
    if len(rs) == 2:
        a, b = rs
        if (a["x"], a["y"], a["w"], a["h"], a["confidence"]) != (b["x"], b["y"], b["w"], b["h"], b["confidence"]):
            mismatches += 1
            print(f"  REPEATABILITY MISMATCH on image {num}: {a} vs {b}")
print(f"Repeatability: {len(by_image) - mismatches}/{len(by_image)} images gave identical results on both passes")

# Confidence by class (pass 1 only, to not double-count)
pass1 = [r for r in ok_rows if r["pass"] == "1"]
by_class = {}
for r in pass1:
    by_class.setdefault(r["class"], []).append(r["confidence"])
print("\nConfidence by class (pass 1 only):")
for cls, confs in sorted(by_class.items()):
    avg = sum(confs) / len(confs)
    print(f"  {cls:25s} n={len(confs):3d}  mean_conf={avg:.5f}  min={min(confs):.5f}  max={max(confs):.5f}")

# GT distance for drone images with ground truth
gt_rows = [r for r in pass1 if r["class"] == "drone" and r["dist_to_gt_px"] != ""]
if gt_rows:
    dists = [float(r["dist_to_gt_px"]) for r in gt_rows]
    print(f"\nDrone images with detected ground-truth box: n={len(gt_rows)}")
    print(f"  mean distance to GT: {sum(dists)/len(dists):.1f}px  median: {sorted(dists)[len(dists)//2]:.1f}px")
    close = sum(1 for d in dists if d < 30)
    print(f"  within 30px of GT center: {close}/{len(dists)} ({100*close/len(dists):.0f}%)")
