"""Package this reviewed camera-only trial set; no hardware or network access."""
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--out', required=True, type=Path)
a = p.parse_args()
r = Path(__file__).resolve().parents[1]
out = a.out.resolve()
archive = out.with_suffix('.zip')
if out.exists() or archive.exists():
    raise SystemExit('Choose a fresh folder and ZIP path; existing packages are preserved')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


builds = [('01_yuyv_control', 'colour_yuyv_20261105_r8', 'yuyv'),
          ('02_rgb565_comparison', 'colour_rgb565_20261105_r8', 'rgb565')]
verified = []
for label, name, fmt in builds:
    folder = r / 'builds' / name
    status = json.loads((folder / 'STATUS.json').read_text(encoding='utf-8-sig'))
    if status['state'] != 'complete' or status['camera_format'] != fmt:
        raise SystemExit(f'Build not complete/correct format: {name}')
    if min(status['timing']['setup_wns_ns'], status['timing']['hold_whs_ns']) < 0:
        raise SystemExit('Timing failed')
    if sha(folder / 'camera_hdmi.bit') != status['bitstream_sha256']:
        raise SystemExit('Bitstream hash mismatch')
    log = (folder / 'vivado.log').read_text(encoding='utf-8', errors='replace')
    if '0 Critical Warnings and 0 Errors encountered' not in log:
        raise SystemExit('Review compiler errors/critical warnings before packaging')
    # Only runtime host tools/docs may differ from a frozen build. Hardware
    # source, constraints and configuration must match the tested snapshot.
    for sub in ['rtl', 'constraints']:
        for f in (folder / 'source' / sub).rglob('*'):
            if f.is_file() and sha(f) != sha(r / 'camera/working' / f.relative_to(folder / 'source')):
                raise SystemExit(f'Current source differs from compiled source: {f}')
    verified.append((label, folder, status))
original = r / 'camera/versions/last_exposure_test/camera_hdmi.bit'
if sha(original) != '2a4cfed6b09c4b06ff9c2b739cb0a284b4b2b251db3c72dc4affbced6fdf0185':
    raise SystemExit('Original recovery bitstream differs from recorded favourite')

out.mkdir(parents=True)
(out / '00_original').mkdir()
shutil.copy2(original, out / '00_original/camera_hdmi.bit')
for label, folder, status in verified:
    dest = out / label
    dest.mkdir()
    for name in ['camera_hdmi.bit', 'STATUS.json', 'SOURCE_SHA256.json']:
        shutil.copy2(folder / name, dest / name)
    shutil.copytree(folder / 'source', dest / 'frozen_build_source')
for sub in ['rtl', 'constraints', 'scripts', 'sim']:
    src = r / 'camera/working' / sub
    dest = out / 'source/camera/working' / sub
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
(out / 'source/tools').mkdir()
for name in ['build_camera_guarded.py', 'create_camera_project.tcl', 'test_camera.py']:
    shutil.copy2(r / 'tools' / name, out / 'source/tools' / name)
shutil.copytree(r / 'camera/working/scripts', out / 'scripts',
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
docs = r / 'docs/camera_colour_trials_20261105'
shutil.copytree(docs, out / 'reports')
for source, target in [('START_HERE.md', 'START_HERE.md'), ('TECHNICAL_GUIDE.md', 'TECHNICAL_GUIDE.md')]:
    shutil.copy2(docs / source, out / target)
shutil.copy2(r / 'camera/WIRING.md', out / 'WIRING.md')
shutil.copy2(docs / 'ESPRESSIF_LICENSE.txt', out / 'ESPRESSIF_LICENSE.txt')
(out / 'source/README.md').write_text(
    'Camera-only r8 source. Read ../START_HERE.md and ../WIRING.md first.\n'
    'Default format YUYV. RGB565 build requires RGB565=1 and SIM_FAST_INIT=0.\n'
    'The two candidate folders include their exact frozen build sources and\n'
    'configuration. Original recovery bitstream is in ../00_original.\n'
    'No physical colour acceptance yet; no automatic board programming or driver changes.\n', encoding='utf-8')
with (out / 'RESULTS.csv').open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Version_or_trial', 'Format', 'Actual_test_date', 'Scene',
                     'White_paper_tint', 'Red_blue_correct', 'Brightness',
                     'Colour_strength', 'Bright_light_glitch', 'Streaks',
                     'Better_same_worse', 'Saved_capture_or_photo', 'Notes'])
    for name, fmt in [('Original preferred', 'YUYV'), ('r8 control', 'YUYV'), ('r8 RGB comparison', 'RGB565')]:
        writer.writerow([name, fmt] + [''] * 11)
    recipes = json.loads((r / 'camera/working/scripts/camera_trials.json').read_text(encoding='utf-8'))
    for name in recipes['trials']:
        writer.writerow([name] + [''] * 12)
manifest = {'prepared_date': '2026-11-05', 'source_commit_at_packaging': subprocess.check_output(
    ['git', 'rev-parse', 'HEAD'], cwd=r, text=True).strip(),
    'physical_camera_tested_new_candidates': False, 'board_programmed': False,
    'original_sha256': sha(original),
    'candidates': {label: status for label, _, status in verified},
    'files': {f.relative_to(out).as_posix(): sha(f) for f in sorted(out.rglob('*')) if f.is_file()}}
(out / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in sorted(out.rglob('*')):
        if f.is_file():
            z.write(f, out.name + '/' + f.relative_to(out).as_posix())
with zipfile.ZipFile(archive) as z:
    if z.testzip() is not None:
        raise RuntimeError('ZIP validation failed')
print(json.dumps({'folder': str(out), 'zip': str(archive), 'zip_bytes': archive.stat().st_size,
                  'files': len(manifest['files']) + 1, 'archive_validated': True}, indent=2))
