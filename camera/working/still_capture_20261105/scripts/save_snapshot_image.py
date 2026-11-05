"""Validate the original D16A/SNAP snapshot and save an unenhanced RGB PNG.

This is the last_exposure_test framebuffer-write RGB565 copy, not r8 raw YUV.
No camera/network access; needs Pillow. Preserve the 320x240 original for CNNs.
"""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

WIDTH, HEIGHT = 320, 240
DEPTH = WIDTH * HEIGHT
DATA_PACKETS = (DEPTH + 13) // 14


def decode_snapshot(path):
    rows = [line.split() for line in Path(path).read_text(encoding='ascii').splitlines() if line.strip()]
    if len(rows) != DATA_PACKETS + 1:
        raise ValueError('Incomplete capture: expected 5487 packets')
    pixels = []
    for index, row in enumerate(rows):
        if len(row) != 8 or any(len(s) != 8 or any(c not in '0123456789abcdefABCDEF' for c in s) for s in row):
            raise ValueError(f'Invalid hexadecimal packet {index}')
        words = [int(s, 16) for s in row]
        if words[0] != 0xD16A0000 | index:
            raise ValueError('Wrong snapshot format or packet order')
        if index < DATA_PACKETS:
            for word in words[1:]:
                pixels.extend([word & 65535, word >> 16])
        else:
            meta = words
    if meta[1] != DEPTH or meta[2] != 0 or meta[4:] != [1, DEPTH, 16, 0x534E4150]:
        raise ValueError('Incomplete/misaligned camera frame or wrong metadata; no image accepted')
    if any(pixels[DEPTH:]):
        raise ValueError('Nonzero padding in final data packet')
    rgb = bytearray()
    for value in pixels[:DEPTH]:
        rgb.extend([(((value >> 11) & 31) * 255 + 15) // 31,
                    (((value >> 5) & 63) * 255 + 31) // 63,
                    ((value & 31) * 255 + 15) // 31])
    return Image.frombytes('RGB', (WIDTH, HEIGHT), bytes(rgb)), meta[3]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True, type=Path)
    p.add_argument('--out-dir', required=True, type=Path)
    args = p.parse_args()
    image, frame = decode_snapshot(args.input)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    outputs = [args.out_dir / n for n in ['image.png', 'preview.png', 'IMAGE.json']]
    if any(path.exists() for path in outputs):
        raise FileExistsError('Image outputs already exist; use a fresh capture folder')
    image.save(outputs[0])
    image.resize((960, 720), Image.Resampling.NEAREST).save(outputs[1])
    result = {'complete': True, 'image': str(outputs[0].resolve()),
              'preview': str(outputs[1].resolve()), 'camera_frame': frame,
              'width': WIDTH, 'height': HEIGHT, 'mode': 'RGB',
              'transfer_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
              'image_sha256': hashlib.sha256(outputs[0].read_bytes()).hexdigest(),
              'format': 'RGB565 copy of framebuffer-write pixels, expanded to RGB PNG',
              'enhancements': 'None; no brightness, saturation, denoising or crop applied',
              'cnn_note': 'Use image.png. Keep full frame; model-specific crop/resize belongs in inference preprocessing.',
              'limits': '5/6/5-bit snapshot precision; not full RGB888 readback, HDMI screenshot, raw Bayer, motion/tracking evaluation or proof of electrical byte correctness.'}
    outputs[2].write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('Saved CNN image:', outputs[0].resolve())
    print('Saved larger preview:', outputs[1].resolve())


if __name__ == '__main__':
    main()
