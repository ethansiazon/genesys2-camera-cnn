#!/usr/bin/env python3
"""Decode cnn_engine's raw HEAD0 (head2/P2/stride4)+HEAD1 (head3/P3/stride8)
output (dumped by scripts/jtag_full_frame_test.tcl) into a real detection.

This is a direct Python port of the ACTUAL, already-validated hardware
decoder (Genesys2_Teammate_Handoff_20261028/cv_model/fpga/decoder_hls/
decoder_work_r2.cpp's decode_work_heads()) -- not a re-derivation. Ported
exactly, not approximated: single best candidate across BOTH heads and all
anchors/positions, ranked by RAW objectness logit alone (no class score
involved at all, confirmed from the reference source), no threshold/NMS.
Q16 fixed-point arithmetic reproduced in Python floats (same results to
float precision; the real decode_work_heads_0 hardware core being
integrated next does this exactly in integer logic).

Config is the identity/no-remap case (cfg.sx=cfg.sy=65536 [Q16 1.0],
cfg.ox=cfg.oy=0, use_motion=0, use_association=0) -- DECODER_PREPARED.json's
first query ("actualV5zero"), appropriate for a single static test frame
with no ROI remap or frame-to-frame tracking.
"""
import sys
import numpy as np

HEAD_WIDTH = [64, 32]
HEAD_HEIGHT = [48, 24]
HEAD_OFFSET = [18432, 0]  # words, within the 73728-word feature region
HEAD_STRIDE = [4, 8]
ANCHOR_Q16 = [
    [[616038, 432538], [1074790, 760218], [1966080, 1225523]],
    [[3230925, 2129920], [5131469, 3846963], [9928704, 3447194]],
]


def sigmoid_q(raw_q14):
    """Matches sigmoid_q(): clamps then maps to Q16 [0,65536]. Reference
    uses a LUT; a direct sigmoid is numerically equivalent to LUT precision."""
    z = raw_q14 / 16384.0  # back to float logit (LUT index was built for Q14-ish raw range)
    p = 1.0 / (1.0 + np.exp(-z))
    return p * 65536.0


def width_q(probability_q16, anchor_q16):
    twice = probability_q16 * 2
    return (twice * twice * anchor_q16) / (2.0 ** 32)


def transformed(value, multiplier, offset):
    return value * multiplier / 65536.0 + offset


def load_dump(path):
    sections = {}
    current = None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                current = line.split("=")[0].lstrip("# ").strip()
                sections[current] = []
                continue
            sections[current].append(int(line, 16))
    return sections


def to_signed32(v):
    return v - (1 << 32) if v >= (1 << 31) else v


def load_feature_words(lanes_u32):
    """lanes_u32 is a flat list of 32-bit unsigned lane values, ascending
    address order. Returns an array of signed Q14-raw ap_int<24> values,
    shape (n_words, 8), matching `lane()`'s low-24-bits-of-each-32-bit-lane
    extraction (sign bit 23, not 31 -- the physical container is 32 bits
    sign-extended from a 24-bit value, per QUANTIZED_MODEL_METADATA.json's
    "signextended 32bit A24F14 lanes")."""
    arr = np.array(lanes_u32, dtype=np.int64).reshape(-1, 8)
    # Already sign-extended to 32 bits by the producer (confirmed: input
    # packer and cnn_engine's own output both sign-extend into the full
    # 32-bit lane) -- just reinterpret as signed32, no separate 24-bit
    # sign-extraction needed.
    signed = np.where(arr >= (1 << 31), arr - (1 << 32), arr)
    return signed


def main():
    path = sys.argv[1]
    sections = load_dump(path)
    # Build one flat "features" array matching DecoderWord* features --
    # index by (HEAD_OFFSET[level] + group*cells + pixel), each entry is
    # one 8-lane word. HEAD1 (level 1, offset 0) lanes come first in the
    # dump, HEAD0 (level 0, offset 18432) second -- place them at their
    # real word offsets in one combined array sized DECODER_FEATURE_WORDS.
    head1_words = load_feature_words(sections["HEAD1_WORDS"])  # offset 0
    head0_words = load_feature_words(sections["HEAD0_WORDS"])  # offset 18432
    total_words = 18432 + 9216
    features = np.zeros((total_words, 8), dtype=np.int64)
    features[0:len(head1_words)] = head1_words
    features[18432:18432 + len(head0_words)] = head0_words

    # cfg: identity, no motion, no association (DECODER_PREPARED.json query 0)
    cfg_sx, cfg_sy, cfg_ox, cfg_oy = 65536, 65536, 0, 0

    best_valid = False
    best_raw = -8388608
    best_index = 0
    best_x = best_y = best_w = best_h = 0.0

    head_base = 0
    for level in range(2):
        nx, ny = HEAD_WIDTH[level], HEAD_HEIGHT[level]
        cells = nx * ny
        off = HEAD_OFFSET[level]
        for pixel in range(cells):
            w0 = features[off + 0 * cells + pixel]
            w1 = features[off + 1 * cells + pixel]
            w2 = features[off + 2 * cells + pixel]
            fields = np.concatenate([w0, w1, w2])[:21]
            for anchor in range(3):
                c = anchor * 7
                key = head_base + anchor * cells + pixel
                raw = int(fields[c + 4])
                if best_valid and (raw < best_raw or (raw == best_raw and key >= best_index)):
                    continue
                px = sigmoid_q(fields[c])
                py = sigmoid_q(fields[c + 1])
                roi_x = (2 * px - 32768 + (pixel % nx) * 65536) * HEAD_STRIDE[level]
                roi_y = (2 * py - 32768 + (pixel // nx) * 65536) * HEAD_STRIDE[level]
                roi_w = width_q(sigmoid_q(fields[c + 2]), ANCHOR_Q16[level][anchor][0])
                roi_h = width_q(sigmoid_q(fields[c + 3]), ANCHOR_Q16[level][anchor][1])
                x = transformed(roi_x, cfg_sx, cfg_ox)
                y = transformed(roi_y, cfg_sy, cfg_oy)
                w = transformed(roi_w, cfg_sx, 0)
                h = transformed(roi_h, cfg_sy, 0)
                if w <= 0 or h <= 0:
                    continue
                best_x, best_y, best_w, best_h = x, y, w, h
                best_raw, best_index, best_valid = raw, key, True
        head_base += 3 * cells

    # x/y/w/h came out in Q16 (both roi_* and the transform keep Q16 scale
    # throughout -- transformed()'s /65536 only undoes the *sx multiply,
    # not the original Q16-pixel scale from the stride multiply).
    px_x, px_y, px_w, px_h = best_x / 65536.0, best_y / 65536.0, best_w / 65536.0, best_h / 65536.0
    confidence = 1.0 / (1.0 + np.exp(-best_raw / 16384.0)) if best_valid else 0.0

    print(f"valid={best_valid} raw_objectness={best_raw} (Q14={best_raw/16384.0:.4f}) "
          f"confidence={confidence:.4f}")
    print(f"center=({px_x:.1f}, {px_y:.1f})  size=({px_w:.1f} x {px_h:.1f})  "
          f"box=x[{px_x-px_w/2:.1f},{px_x+px_w/2:.1f}] y[{px_y-px_h/2:.1f},{px_y+px_h/2:.1f}]")


if __name__ == "__main__":
    main()
