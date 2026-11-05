# Active camera debugging copy

This is the editable copy of Ethan's preferred manual-exposure version,
selected on 4 November 2026. The unchanged saved version is
`../versions/last_exposure_test`. Original bitstream SHA256:
`2a4cfed6b09c4b06ff9c2b739cb0a284b4b2b251db3c72dc4affbced6fdf0185`.

Initial RTL and constraints are byte-identical to that saved version.
Exposure is fixed at 128 lines, gain 1x, VTS 520. The user reports a dark,
washed-out picture, with remaining green distortion on bright lights.
Monitor aspect-ratio stretching has been corrected on the monitor.

Edit RTL here; keep versions/ unchanged. The generated Vivado project is
`../../builds/camera_exposure_debug_20261104/camera_hdmi.xpr`.
The root tools/create_camera_project.tcl recreates the project in a NEW directory.
Build outputs/captures stay ignored; push changes only after Ethan approves.
The copied .bit is the original baseline, not a newly built result. After RTL
changes it must not be presented as matching those changes.

Normal viewing: only SW6 up, press BTNC. Capture remains 320 x 240 YUV422,
displayed at 640 x 480 / 60 Hz. PCLK is JA1 and D6 is JB8; full mapping is
in ../WIRING.md. Verify actual wiring before programming a new design.

Next: obtain current camera-register and raw-pixel evidence, then isolate
exposure, data capture/byte interpretation and colour processing one change
at a time. Sensor colour bars alone do not prove correct live colour.

## Raw diagnostic added 4 November

SW7 now records pre-RGB YUYV bytes using the earlier tested raw observer.
Exposure remains 128 lines, gain 1x, VTS 520. The image conversion and display
path are unchanged. Use scripts/analyze_raw_yuv.py for D16C captures; the old
RGB565 analyze_snapshot.py decoder is incompatible with this new mode.
Wait for the camera to settle before raising SW7; lower then raise it to capture
a new frame without resetting the camera. The preserved .bit in this folder is
still the OLD baseline; use the separately built diagnostic .bit after it passes.
