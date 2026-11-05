#!/usr/bin/env python3
"""Pack a real photo into cnn_engine's feature-memory format for simulation.

Recipe reverse-engineered verbatim from the teammate's own exporter
(Genesys2_Teammate_Handoff_20261028/cv_model/reference_source/campaign/
shared_engine/export_wide_model_r4.py + data_roi256.py's sized()), which is
what originally produced the validated input_0/1/2.bin vectors:

  1. cv2.imread -> BGR uint8 HWC.
  2. letterbox-resize to 256x192 (data_roi256.sized): pad value 114, aspect
     preserved, centered. (256/192 == 4/3, so a 4:3-ish photo fills the
     canvas exactly with no padding.)
  3. BGR -> RGB, HWC -> CHW, /255 -> float32 in [0,1].
  4. Q14 fixed point: round(x * 16384), int32.
  5. Pad channel dim 3 -> 8 with zeros (NCHW8).
  6. Transpose to NHWC8, raw little-endian bytes -- this is exactly
     FEATURE_WORDS layout: one 256-bit word per pixel, 8 x 32-bit
     sign-extended lanes (channels 0..7, channels 3..7 = 0), raster order
     (row-major, H then W). Confirmed byte-for-byte against the real
     input_0.bin size (1,572,864 bytes = 49152 words x 32 bytes).

Only the first ROWS rows (each row = WIDTH=256 words) are emitted, matching
this project's own existing precedent (bd/create_bd.tcl's coefficient
sim-bypass cuts 41,600 -> 256 words for the same reason): the full 49,152
word count through the realistic DDR3 behavioral model is impractically
slow in simulated wall-clock time and isn't needed to answer "does feature
memory holding real nonzero data change cnn_ap_done's behavior" -- see
docs/PHASE2_LOG.md's C3 investigation.
"""
import argparse
import sys

import cv2
import numpy as np

WIDTH, HEIGHT = 256, 192
Q_SCALE = 16384  # 2**14


def sized(image, width=WIDTH, height=HEIGHT):
    h, w = image.shape[:2]
    scale = min(width / w, height / h)
    nw, nh = round(w * scale), round(h * scale)
    px, py = (width - nw) // 2, (height - nh) // 2
    out = np.full((height, width, 3), 114, np.uint8)
    out[py:py + nh, px:px + nw] = cv2.resize(
        image, (nw, nh),
        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR,
    )
    return out


def pack(image_path, rows, crop=None, row_offset=0):
    image = cv2.imread(image_path)
    if image is None:
        raise RuntimeError(f"could not read image: {image_path}")
    if crop is not None:
        l, t, r, b = crop
        image = image[t:b, l:r]
    canvas = sized(image)  # HWC, BGR, uint8, 192x256x3
    rgb = canvas[:, :, ::-1]  # BGR -> RGB
    chw = np.ascontiguousarray(rgb).transpose(2, 0, 1).astype(np.float32) / 255.0
    q14 = np.rint(chw * Q_SCALE).astype(np.int32)  # (3, 192, 256)
    padded = np.zeros((8, HEIGHT, WIDTH), np.int32)
    padded[:3] = q14
    nhwc8 = padded.transpose(1, 2, 0)  # (192, 256, 8)
    cropped = nhwc8[row_offset:row_offset + rows]
    lanes_u32 = cropped.astype(np.uint32)  # two's complement reinterpret
    return lanes_u32.reshape(-1, 8)  # (rows*WIDTH, 8)


def to_hex_lines(words_x8):
    lines = []
    for lanes in words_x8:
        word = 0
        for i, lane in enumerate(lanes):
            word |= (int(lane) & 0xFFFFFFFF) << (32 * i)
        lines.append(f"{word:064x}")
    return lines


def to_lane32_lines(words_x8):
    # Flat list of 32-bit hex lanes in ascending address order (lane 0 of
    # pixel 0 first) -- one per line. This is the real-hardware JTAG-AXI
    # debug path's view: jtag_axi_0's default AXI width is 32 bits, so
    # scripts/jtag_photo_test.tcl bursts these directly instead of going
    # through the 256-bit BRAM-staging path (sim-only -- see
    # rtl/feature_bram_stage.v's header comment). Address order matches
    # to_hex_lines' bit layout exactly (lane i at bits [32*(i+1)-1:32*i]),
    # so both outputs describe the identical byte stream.
    lines = []
    for lanes in words_x8:
        for lane in lanes:
            lines.append(f"{int(lane) & 0xFFFFFFFF:08x}")
    return lines


def main():
    p = argparse.ArgumentParser()
    p.add_argument("image")
    p.add_argument("out_hex")
    p.add_argument("--rows", type=int, default=1,
                    help="number of top image rows to pack (each row = 256 words)")
    p.add_argument("--crop", type=str, default=None,
                    help="l,t,r,b pixel box to crop before letterbox-resize")
    p.add_argument("--row-offset", type=int, default=0,
                    help="first canvas row (0..191) to start packing from")
    p.add_argument("--format", choices=["readmemh256", "lanes32"], default="readmemh256",
                    help="readmemh256: one 64-hex-digit 256-bit word per line "
                         "(for feature_bram_stage.v's $readmemh, simulation). "
                         "lanes32: one 8-hex-digit 32-bit lane per line, 8 per "
                         "pixel, ascending address order (for "
                         "scripts/jtag_photo_test.tcl's real-hardware AXI bursts).")
    args = p.parse_args()

    crop = tuple(int(x) for x in args.crop.split(",")) if args.crop else None
    words = pack(args.image, args.rows, crop=crop, row_offset=args.row_offset)
    if args.format == "lanes32":
        lines = to_lane32_lines(words)
    else:
        lines = to_hex_lines(words)
    with open(args.out_hex, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} {args.format} lines ({args.rows} rows) to {args.out_hex}")


if __name__ == "__main__":
    sys.exit(main())
