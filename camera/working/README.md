# Controlled reference startup candidate

Fresh copy of camera/versions/last_exposure_test, Ethan's preferred picture.
Only ov5640_init.v differs in synthesizable RTL: 28 Linux-verified startup
register writes inserted after the PLL-source selection and before DVP/ISP setup.
All original settings/order remain; exposure 128 lines, gain 1x, capture 320x240,
HDMI 640x480 at 60 Hz. This is an unproved sensor-initialization experiment.

The previous ISP/raw diagnostic copy is preserved under local_artifacts/ and Git.
This candidate uses the ORIGINAL RGB565 snapshot format, not raw YUYV recording.
Use this copy's scripts/analyze_snapshot.py, not the previous raw decoder.
The copied camera_hdmi.bit here is the ORIGINAL baseline bitstream; it does not
contain these edits. Use the new builds/analog_reference128_20261104_r4 output.

Normal live viewing: ONLY SW6 up; press BTNC, wait five seconds.
Camera bars: SW1 and SW6 up; BTNC. Verify PCLK JA1 and D6 JB8 before programming.
Keep versions immutable. No board programming or Git pushes occur automatically.
See docs/CAMERA_ANALOG_REFERENCE_20261104.json for verified source provenance.
