"""Decode bounded raw UART captures using their embedded format identifier.

No hardware access. RGB565 is high byte first per OV5640 4300=61.
The legacy analyze_raw_yuv.py remains YUYV-only and rejects RGB captures.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from analyze_raw_yuv import decode

FORMATS = {0x59555630: 'yuyv', 0x52353635: 'rgb565'}


def read_capture(path, expected='auto'):
    packets = [[int(w, 16) for w in line.split()]
               for line in Path(path).read_text(encoding='ascii').splitlines() if line.strip()]
    if len(packets) != 5487:
        raise ValueError('Expected 5487 packets for a complete 320x240 capture')
    values = []
    for i, words in enumerate(packets):
        if len(words) != 8 or words[0] != (0xD16C0000 | i):
            raise ValueError(f'Invalid packet or order at {i}')
        if any(w < 0 or w > 0xFFFFFFFF for w in words):
            raise ValueError('UART word outside 32-bit range')
        if i < 5486:
            for word in words[1:]:
                values.extend([word & 65535, word >> 16])
    meta = packets[-1]
    if meta[1] != 76800 or meta[2] != 0 or meta[4:7] != [1, 76800, 16]:
        raise ValueError('Capture incomplete, misaligned or has address errors')
    if meta[7] not in FORMATS:
        raise ValueError(f'Unknown format identifier {meta[7]:08X}')
    fmt = FORMATS[meta[7]]
    if expected != 'auto' and expected != fmt:
        raise ValueError(f'Expected {expected}, received {fmt}; refusing reinterpretation')
    words = np.asarray(values[:76800], dtype=np.uint16).reshape(240, 320)
    return words, fmt, meta[3]


def expand_rgb565(words):
    # Decode actual packed channels, not a YUV interpretation or colour gain.
    r = ((words >> 11) & 31).astype(np.uint8)
    g = ((words >> 5) & 63).astype(np.uint8)
    b = (words & 31).astype(np.uint8)
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4),
                     (b << 3) | (b >> 2)], axis=-1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file', type=Path)
    p.add_argument('--expected-format', choices=['auto', 'yuyv', 'rgb565'], default='auto')
    args = p.parse_args()
    words, fmt, frame = read_capture(args.file, args.expected_format)
    raw = np.stack([words >> 8, words & 255], axis=-1).astype(np.uint8).tobytes()
    raw_path = args.file.with_suffix('.' + fmt + '.bin')
    raw_path.write_bytes(raw)
    if fmt == 'rgb565':
        previews = {'rgb565': expand_rgb565(words)}
    else:
        y = (words >> 8).astype(np.uint8)
        u = np.repeat((words[:, ::2] & 255).astype(np.uint8), 2, axis=1)
        v = np.repeat((words[:, 1::2] & 255).astype(np.uint8), 2, axis=1)
        previews = {'limited': decode(y, u, v), 'full': decode(y, u, v, True)}
    images = {}
    for name, rgb in previews.items():
        path = args.file.with_suffix('.' + name + '.png')
        Image.fromarray(rgb).resize((960, 720), Image.Resampling.NEAREST).save(path)
        images[name] = str(path)
    result = {'source': str(args.file), 'format': fmt, 'camera_frame': frame,
              'pixels': 76800, 'raw_bytes': len(raw), 'raw_sha256': hashlib.sha256(raw).hexdigest(),
              'images': images, 'scope': 'Received sensor output before FPGA RGB conversion. '
              'A valid transfer does not prove the DVP bytes are electrically correct.'}
    args.file.with_suffix('.format_analysis.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
