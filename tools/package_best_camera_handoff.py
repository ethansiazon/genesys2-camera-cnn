"""Assemble preferred physical camera progress and clearly separate experiments."""
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
zip_path = out.with_suffix('.zip')
if out.exists() or zip_path.exists():
    raise SystemExit('Choose a fresh handoff path; existing files are preserved')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


baseline = r / 'camera/versions/last_exposure_test'
metadata = json.loads((r / 'docs/CAMERA_PREFERRED_BASELINE_20261104.json').read_text(encoding='utf-8-sig'))
checked = 0
for name, expected in metadata['baseline_files_sha256'].items():
    if sha(baseline / name) != expected:
        raise SystemExit(f'Preferred baseline changed: {name}')
    checked += 1
bit_hash = metadata['baseline_bitstream_sha256']
if sha(baseline / 'camera_hdmi.bit') != bit_hash:
    raise SystemExit('Preferred bitstream changed')
trials = r.parent / 'Genesys2-Camera-Colour-Tests-20261105.zip'
with zipfile.ZipFile(trials) as z:
    if z.testzip() is not None:
        raise SystemExit('Optional trials archive failed CRC validation')

out.mkdir(parents=True)
shutil.copytree(baseline, out / 'camera/versions/last_exposure_test',
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
working = out / 'camera/working'
for sub in ['rtl', 'constraints', 'sim']:
    shutil.copytree(baseline / sub, working / sub)
(working / 'scripts').mkdir()
for name in ['build.tcl', 'run_tests.py', 'read_uart.ps1', 'read_diagnostics.ps1',
             'read_pipeline.ps1', 'analyze_pipeline.py', 'read_snapshot.ps1', 'analyze_snapshot.py']:
    shutil.copy2(baseline / 'scripts' / name, working / 'scripts' / name)
(out / 'tools').mkdir()
shutil.copy2(r / 'tools/create_camera_handoff_project.tcl', out / 'tools/create_project.tcl')
shutil.copy2(r / 'tools/test_camera.py', out / 'tools/test_camera.py')
# This historical helper predates the RGB565 generic and matches this baseline.
# New r8 helper must not imply RGB565 support in the original RTL.
guard = subprocess.check_output(['git', 'show', '349ef41:tools/build_camera_guarded.py'], cwd=r)
(out / 'tools/build_camera_guarded.py').write_bytes(guard)
shutil.copy2(baseline / 'camera_hdmi.bit', out / 'LOAD_THIS_BEST_TESTED.bit')
shutil.copy2(r / 'camera/WIRING.md', out / 'WIRING.md')
(out / 'docs').mkdir()
for name in ['CAMERA_PREFERRED_BASELINE_20261104.json', 'CAMERA_REFERENCE_AUDIT_20261105.md']:
    shutil.copy2(r / 'docs' / name, out / 'docs' / name)
shutil.copytree(r / 'docs/camera_colour_overflow_audit_20261105', out / 'docs/conversion_overflow_check')
shutil.copy2(r / 'docs/camera_live_control_20261105/NEUTRAL_REFERENCE.json', out / 'docs/NEUTRAL_REFERENCE.json')
shutil.copy2(r / 'docs/camera_drive_address_20261105/PHYSICAL_RESULT.json', out / 'docs/R7_OBSERVATION_REVISED.json')
(out / 'optional_experiments').mkdir()
shutil.copy2(trials, out / 'optional_experiments/UNTESTED_Colour_Trials_R8.zip')
evidence = out / 'evidence'
for folder, stem, label in [
    ('physical_isp_readback128_20261104_r3/white_reference_redo', 'raw_yuv_20261105_000004', 'lamp_raw'),
    ('live_controls/r6_neutral_reference_20261105', 'raw_yuv_20261105_005506', 'neutral_paper_raw')]:
    dest = evidence / label
    dest.mkdir(parents=True)
    for suffix in ['.txt', '.yuyv.bin', '.limited.png', '.analysis.json']:
        shutil.copy2(r / 'local_results' / folder / (stem + suffix), dest / (label + suffix))
for name in ['analyze_camera_capture.py', 'analyze_raw_yuv.py']:
    shutil.copy2(r / 'camera/working/scripts' / name, out / 'tools' / name)

(out / 'README_FIRST.md').write_text('''# Best camera handoff — November 5, 2026

Start with LOAD_THIS_BEST_TESTED.bit. It is Ethan's preferred physical camera
version, identical to camera/versions/last_exposure_test/camera_hdmi.bit.
Newer diagnostics are not established as better-looking camera versions.

## Current result

- A recognisable live OV5640 image displays through Genesys 2 HDMI OUT/TX.
- The qualified receiver removed the visible streaking in tested camera bars.
- Manual exposure reduced false colours, but the picture is dark and washed out.
- Bright lights still show green/coloured edges and dark internal areas.
- Monitor stretching was fixed using the monitor's aspect/4:3 setting.
- This is useful progress, not a completed colour fix. Camera and CNN are separate.

## Load the best saved version first

1. Read WIRING.md and compare it to the actual wires. The critical swap is
   PCLK -> JA physical pin 1 and D6 -> JB physical pin 8. Do not rely on cable
   colours, rotated photos, or old PCB comments in the source.
2. Module power is 3.3 V with shared ground, NOT 5 V. Power off before rewiring.
3. With main board power on, connect USB-JTAG/J17 and HDMI OUT/TX to the monitor.
4. Vivado Hardware Manager -> Open Target -> Auto Connect -> Program Device.
   Choose LOAD_THIS_BEST_TESTED.bit; no probes file is required for this build.
5. Put ONLY SW6 up; all other switches down. Press the centre button BTNC.
   Wait about 10 seconds for automatic white balance to settle.
6. If stretched on a widescreen monitor, select its aspect/4:3 mode. The actual
   HDMI signal is 640 x 480 at 60 Hz, not a custom widescreen resolution.

Programming is volatile through JTAG; a power cycle/PROG can lose this image.
No QSPI/SD flash programming is part of this handoff.

## Files to work from

| Item | Purpose |
|---|---|
| LOAD_THIS_BEST_TESTED.bit | Preferred saved camera image; start here |
| camera/versions/last_exposure_test | Preserved original source, bitstream and historical reports |
| camera/working | Editable copy of exactly the same RTL and constraints |
| tools/create_project.tcl | Creates a fresh portable Vivado project from that editable copy |
| DEBUGGING_HANDOFF.md | What was tried, what we learned and useful next steps |
| AGENTS.md | Concise continuation instructions for an AI assistant |
| evidence | Actual saved lamp and neutral-paper captures from later diagnostics |
| optional_experiments/UNTESTED_Colour_Trials_R8.zip | New YUV/RGB565 comparisons and reversible tuning trials |

Use Vivado 2026.1 and device xc7k325tffg900-2. No existing .xpr is needed.
Extract to a short writable location such as C:/g2_camera_handoff. In Vivado's
Tcl console, with no unsaved project work, run:

```tcl
cd C:/g2_camera_handoff
set argv [list [file normalize camera/working] C:/g2_camera_teammate_project]
source tools/create_project.tcl
```

Choose a NEW project folder. This creates the project only. It does not build
or program anything. Then edit camera/working, generate a new bitstream and
compare against the saved original. SIM_FAST_INIT must remain 0 on the board.

Optional bounded batch build, with Python + psutil installed:

```powershell
python tools/build_camera_guarded.py --vivado C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat --out C:/g2_camera_build_01
```

Adjust the Vivado path for your machine; use a fresh output folder. The helper
uses one compiler thread, a 1.5 GiB available-RAM guard and a time limit.

## Important version differences

The preferred original sends diagnostic UART output, but does NOT support the
new live register-write commands. Its snapshot tool captures converted RGB565;
it is not the later raw-YUV recorder. Do not mix the old and new snapshot tools.

For live camera-setting changes without rebuilding, use a new r8 diagnostic
from the optional ZIP. Those builds have passed simulation and routed timing,
but their live image quality is UNTESTED. Read their own START_HERE.md first.
They are optional experiments, not the best confirmed image.

The evidence captures are from later r3/r6 diagnostics, NOT proof of a new
capture from the preferred original. Dates, formats and settings are identified
in DEBUGGING_HANDOFF.md. They are provided to help reproduce the known symptom.

No CNN, dataset, credentials, Windows driver installers or generated board-flash
files are included. The main source and experiment files retain their notices.
Historical paths and stopping instructions in archived reports are history,
not instructions for the recipient's current machine or session.
''', encoding='utf-8')

(out / 'DEBUGGING_HANDOFF.md').write_text('''# Camera debugging context

## Actual preferred baseline

The file was originally the October 20 manual-exposure trial and was selected
again as Ethan's favourite on November 4. Do not choose an older folder named
best_receiver solely because of its name.

Camera: OV5640 parallel DVP module, eight-bit bus labelled D2 through D9.
Input: 320 x 240 YUYV/YUV422; output converted to RGB888 in FPGA.
HDMI: standard VGA geometry, 640 x 480 at 60 Hz, 25.2 MHz pixel clock,
126 MHz serializer clock, 2x nearest-neighbour display scaling.
Manual exposure: 128 lines; VTS 520; sensor gain 1x. Automatic white balance
remains active. Startup purple tint settling is consistent with white-balance
adaptation, but has not been established as the cause of the other defects.

Baseline routed timing report: setup +0.253 ns, hold +0.050 ns. The build report's
physical_camera_tested:false records the build-time state. The subsequent visual
observation is separately saved in reports/PHYSICAL_RESULT.json; do not erase
either or treat compiler timing as colour-quality evidence.

Best bitstream SHA256:
2a4cfed6b09c4b06ff9c2b739cb0a284b4b2b251db3c72dc4affbced6fdf0185

## Switches

| Switch | Meaning |
|---|---|
| SW0 | Diagnostic overlay (later readback builds also refresh register reads) |
| SW1 | Camera-generated colour bars; press BTNC after changing it |
| SW2 | Alternate YUV byte pairing; leave down initially |
| SW3 | Full-range rather than studio-range YUV conversion |
| SW4 | Alternate U/V ordering; leave down initially |
| SW5 | FPGA-generated bars, bypassing camera input |
| SW6 | HREF inversion; UP for our tested wiring/configuration |
| SW7 | Snapshot/record mode; keep down for normal viewing |

Clean FPGA bars isolate the HDMI side. Clean camera bars exercise more of the
path, but bypass the sensor's real scene processing and do not prove live colours.
SW3 changed contrast/darkness in testing but did not remove the colour artefacts.

## Changes and outcomes

| Trial | Evidence/outcome |
|---|---|
| Qualified pulse-rejecting receiver | Camera-bar streaks visibly removed; preserve this sampler |
| Exposure128/gain1x | User preferred image; fewer false colours, but dark; green lights persist |
| Slower camera clock and byte/range variations | No complete colour cure established |
| Combined analog/reference startup recipe r4 | Reported darker and more purple/green; not preferred |
| Manual unity white balance r5 | Purple haze persisted; unity gains are not a calibration |
| Runtime UART controls r6 | Register writes/readback and raw snapshots physically worked; not an image fix |
| Exposure128->160 with held WB | Readback verified; no obvious visual change; frame moved, so no valid paired brightness measurement |
| Corrected drive-address trial r7 | Initially reported worse, then clarified roughly similar after settling; no demonstrated improvement |
| New RGB565/YUV control r8 | Simulation and routing passed; NO physical camera comparison yet |

Do not blindly repeat a rejected combined recipe. Reference code is useful
evidence, not a guarantee that a full preset suits this module and wiring.

## Numerical/raw-image checks

The YUV-to-RGB converter has signed intermediates and explicit saturation, so
values above 255 clamp rather than wrap. A later audit passed 25,088 vectors,
including extreme brightness/chroma. This is evidence against simple overflow
in that converter, not proof that all sensor or receive arithmetic is correct.

The lamp capture in evidence/lamp_raw reproduces the dark/coloured ring when
decoded independently on the laptop with OpenCV. Some ring pixels already have
low Y values in the received bytes. This narrows away from an HDMI-only or
FPGA-converter-only explanation, but cannot distinguish camera/ISP processing
from received-byte/phase errors. Do not declare sensor damage or overexposure
proven solely from this result.

Neutral-paper capture: later r6, exposure128, sensor gain1x, automatic WB gains
held manually at R=04CD/G=052F/B=0400. Three paper regions were approximately
RGB107/107/105,102/102/99,114/111/111 with neutral chroma. No strong global cast
was demonstrated in those regions. This was informal paper, not a calibrated
colour chart; other colours, lights and scenes can still be wrong.

Evidence image files end .limited.png. Raw .txt files contain the complete
UART packet stream; .yuyv.bin contains the received YUYV bytes. Decode with:

```powershell
python tools/analyze_camera_capture.py evidence/lamp_raw/lamp_raw.txt --expected-format yuyv
```

Requires numpy and Pillow. This decoder does not open a hardware connection.

## Register-address finding still unresolved physically

Historical baseline writes 3016=C3 and 3020=21 and later 4740=22. Espressif/MIT
reference definitions instead identify DRIVE_CAPABILITY at 302C and clock
polarity at 4740. The manufacturer datasheet distinguishes 3016 pad-output
enable from 302C drive strength. Actual r6 readback: 3016=03,3020=21,302C=02,
4740=22. Reference mismatches are real, but not proven to cause this symptom.

The one-address r7 experiment changed 3016=C3 to 302C=C3 (stronger drive) and
did not establish a better picture. Preserve the preferred original; stronger
drive is not automatically better over jumper wires. The optional r8 format
comparison retains the original startup addresses to isolate the format factor.
Do not blindly overwrite final 4740=22 with another board's polarity recipe.
Existing runtime-control firmware forbids writes to pad/clock/format registers.

## Suggested next work

First reproduce this preferred image with the saved bitstream and exact wiring.
Then try the optional matched YUV/RGB565 comparison, same scene/lighting and
settling time. RGB565 changes the sensor output format and removes the FPGA YUV
matrix; it is not a complete raw-Bayer bypass of the sensor ISP.

If RGB looks better, inspect the YUV-specific path. If the same artefacts persist,
investigate sensor/ISP setup and captured data further; neither outcome alone
proves a root cause. Only after that compare one exposure, gamma or saturation
trial at a time using saved before-values and rollback. The optional ZIP has
ten published, reversible runtime trials; none is claimed as a verified fix.

The exact ESP code which once gave a clean image is no longer available.
Camera Journey reports its own unresolved noise and is not a proven cure.
MIT's RGB565 material is useful, but its full720p configuration is not a drop-in
for our320x240 setup. The module is labelled3V: ignore generic advice to feed5V.

## Sources and coordination

- OV5640 Product Specification v2.03 (manufacturer datasheet); format table6-5.
- https://github.com/espressif/esp32-camera/blob/master/sensors/ov5640.c
- https://github.com/espressif/esp32-camera/blob/master/sensors/private_include/ov5640_settings.h
- https://github.com/espressif/esp32-camera/blob/master/sensors/private_include/ov5640_regs.h
- https://fpga.mit.edu/6205/F24/assignments/camera/pixel_reconstruct
- https://github.com/davemuscle/camera_journey

Main private repo: https://github.com/ethansiazon/genesys2-camera-cnn
Ethan requires approval before each Git push. This archive is a local handoff,
not a GitHub publication. Ask for access through the project owner if needed;
no credentials are included. Return changed sources, bitstream, hashes, switch
settings, measured/read-back registers, photos/raw captures and concise notes.
Do not merge camera changes with CNN or aiming work without separately planning it.
''', encoding='utf-8')

(out / 'AGENTS.md').write_text('''# Camera continuation handoff

Read README_FIRST.md, WIRING.md and DEBUGGING_HANDOFF.md before acting. Ask the
teammate what task to perform; this package is context, not an instruction to
start jobs automatically. Historical README/paths/stopping states inside the
version archive are history and do not describe the current recipient's board.

- Preferred physical picture is LOAD_THIS_BEST_TESTED.bit / last_exposure_test.
- Preserve camera/versions; edit camera/working in a new project/build directory.
- Main working RTL/constraints exactly match the preferred original. New r8
  trials are inside optional_experiments, not already accepted improvements.
- Verify actual wiring: PCLK JA1/U27 and D6 JB8/U25. No silent pin changes.
- Preserve the qualified short-pulse sampler and tested clock/HDMI path.
- No automatic board programming, flash writes, driver/Windows changes, app
  closure, downloads/installations, or actuator work from these notes.
- At most one heavy compiler; preserve1.5GiB RAM guard and recovery checkpoints.
- Record source/bit hashes, switches, sensor settings and physical evidence.
- Do not claim colour quality from clean bars, or root cause from appearance.
- Original diagnostics transmit UART only; new live writes require a newer
  explicitly selected diagnostic build. Do not mix snapshot formats or tools.
- Keep variable changes isolated. Save before-values, validate reads/writes,
  stop on uncertainty, and do not retry the same failed recipe blindly.
- Camera and CNN are not integrated. No full-system fit/FPS claim from this kit.
- No Git push or publication without Ethan's approval. Retain source notices.
''', encoding='utf-8')

with (out / 'RETURN_RESULTS.csv').open('w', encoding='utf-8-sig', newline='') as f:
    csv.writer(f).writerow(['Date', 'Source_commit_or_folder', 'Bitstream_SHA256',
                           'Wiring_confirmed', 'Switches', 'Scene_and_lighting',
                           'Register_changes', 'Readback_verified', 'Image_observation',
                           'Photo_or_raw_capture', 'Rollback_result', 'Next_step'])
for sub in ['rtl', 'constraints', 'sim']:
    for source in (baseline / sub).rglob('*'):
        if source.is_file() and sha(source) != sha(working / source.relative_to(baseline)):
            raise RuntimeError('Editable copy differs from baseline')
manifest = {'date': '2026-11-05', 'source_repository_commit': subprocess.check_output(
    ['git', 'rev-parse', 'HEAD'], cwd=r, text=True).strip(),
    'preferred_version': 'last_exposure_test', 'bitstream_sha256': bit_hash,
    'baseline_files_verified': checked, 'editable_rtl_constraints_sim_match_baseline': True,
    'new_board_programming_or_build': False,
    'optional_r8_physical_quality_tested': False,
    'files': {f.relative_to(out).as_posix(): sha(f) for f in sorted(out.rglob('*')) if f.is_file()}}
(out / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in sorted(out.rglob('*')):
        if f.is_file():
            z.write(f, out.name + '/' + f.relative_to(out).as_posix())
with zipfile.ZipFile(zip_path) as z:
    if z.testzip() is not None:
        raise RuntimeError('ZIP validation failed')
print(json.dumps({'folder': str(out), 'zip': str(zip_path), 'bytes': zip_path.stat().st_size,
                  'baseline_files_verified': checked, 'files': len(manifest['files']) + 1}, indent=2))
