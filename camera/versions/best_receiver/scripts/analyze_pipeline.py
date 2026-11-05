"""Compare bytes consumed by the real receiver with real framebuffer writes.

Assumes SW2/SW3/SW4 down: YUYV, limited-range BT.601, normal U/V.
No image-quality verdict is inferred from colour-bar boundaries.
"""
import argparse
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rgb(y, cb, cr):
    yd = 298 * (y - 16)
    clamp = lambda v: max(0, min(255, (v + 128) >> 8))
    return [clamp(yd + 409 * (cr - 128)),
            clamp(yd - 208 * (cr - 128) - 100 * (cb - 128)),
            clamp(yd + 516 * (cb - 128))]


def decode(words):
    value = sum(words[i + 1] << (32 * i) for i in range(4))
    debug = (value >> 66) & ((1 << 49) - 1)
    return dict(index=words[0] & 65535, write=bool(value & 1),
                address=(value >> 1) & 0x1ffff,
                rgb=[(value >> 34) & 255, (value >> 26) & 255,
                     (value >> 18) & 255],
                reserved_old_rgb=(value >> 42) & 0xffffff,
                byte=debug & 255, valid=bool(debug & 256),
                href=bool(debug & 512), vsync=bool(debug & 1024),
                phase=(debug >> 11) & 3, x=(debug >> 13) & 1023,
                y=(debug >> 23) & 1023, frame=(debug >> 33) & 65535)


def analyze(records):
    groups = collections.defaultdict(dict)
    duplicates = []
    for r in records:
        if r['valid']:
            key = (r['frame'], r['y'], r['x'])
            if r['phase'] in groups[key]:
                duplicates.append([r['index'], *key, r['phase']])
            groups[key][r['phase']] = r['byte']
    expected = {}
    complete = []
    for (frame, y, x), phases in groups.items():
        if set(phases) == {0, 1, 2, 3} and x < 320 and y < 240:
            y0, cb, y1, cr = (phases[p] for p in range(4))
            complete.append(dict(frame=frame, y=y, x=x,
                                 yuyv=[y0, cb, y1, cr]))
            expected[(frame, y * 320 + x)] = rgb(y0, cb, cr)
            if x + 1 < 320:
                expected[(frame, y * 320 + x + 1)] = rgb(y1, cb, cr)
    writes = [r for r in records if r['write']]
    matched = 0
    mismatches = []
    observed = collections.Counter()
    for r in writes:
        key = (r['frame'], r['address'])
        observed[key] += 1
        if key in expected:
            if r['rgb'] == expected[key]:
                matched += 1
            else:
                mismatches.append(dict(index=r['index'], frame=r['frame'],
                                       address=r['address'], actual=r['rgb'],
                                       expected=expected[key]))
    # End-of-buffer conversion may still be in flight; only call a write missing
    # if that complete group's last byte is at least 8 source clocks from EOF.
    last_safe = len(records) - 9
    safely_completed = set()
    for r in records:
        if r['index'] <= last_safe and r['valid'] and r['phase'] == 3:
            for dx in (0, 1):
                key = (r['frame'], r['y'] * 320 + r['x'] + dx)
                if key in expected:
                    safely_completed.add(key)
    rows = []
    for frame, y in sorted({(g['frame'], g['y']) for g in complete}):
        row_groups = [g for g in complete if (g['frame'], g['y']) == (frame, y)]
        row_writes = [r for r in writes if r['frame'] == frame and r['address'] // 320 == y]
        rows.append(dict(frame=frame, y=y, complete_pairs=len(row_groups),
                         writes=len(row_writes), unique_addresses=len({r['address'] for r in row_writes}),
                         common_yuyv=[dict(values=list(v), count=n) for v, n in
                                      collections.Counter(tuple(g['yuyv']) for g in row_groups).most_common(12)]))
    return dict(records=len(records), consumed_bytes=sum(r['valid'] for r in records),
                complete_yuyv_pairs=len(complete), phase_duplicates=duplicates,
                framebuffer_writes=len(writes), exact_rgb_matches=matched,
                rgb_mismatches=len(mismatches), mismatch_examples=mismatches[:24],
                missing_safe_addresses=[list(k) for k in sorted(safely_completed - observed.keys())],
                duplicate_write_addresses=[dict(frame=k[0], address=k[1], count=n)
                                           for k, n in observed.items() if n > 1],
                writes_without_complete_input=sum(k not in expected for k in observed),
                rows=rows,
                assumptions='SW2/SW3/SW4 down; compares digital receiver and buffer writes only. '
                            'A correct conversion does not prove clean input bytes or clean HDMI output.'), complete


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('trace', nargs='?', type=Path)
    args = parser.parse_args()
    trace = args.trace
    if trace is None:
        status = json.loads((ROOT / 'reports/LAST_PIPELINE.json').read_text(encoding='utf-8-sig'))
        if not status['complete']:
            raise RuntimeError('Cannot analyze an incomplete transfer')
        trace = Path(status['file'])
    packets = [[int(w, 16) for w in line.split()] for line in trace.read_text().splitlines() if line.strip()]
    if len(packets) != 2048:
        raise RuntimeError(f'Expected 2048 packets, got {len(packets)}')
    for i, p in enumerate(packets):
        if len(p) != 8 or p[0] != 0xD1680000 | i or p[5] != 2048 or p[7] != 0x50495045:
            raise RuntimeError(f'Bad packet {i}')
    records = [decode(p) for p in packets]
    result, groups = analyze(records)
    result['source'] = str(trace)
    trace.with_suffix('.decoded.json').write_text(json.dumps(records, indent=2))
    trace.with_suffix('.pairs.json').write_text(json.dumps(groups, indent=2))
    trace.with_suffix('.analysis.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
