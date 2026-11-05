# Reference-startup trial

This candidate starts directly from `camera/versions/last_exposure_test`,
the user's preferred saved image. Source checkpoint: `090f597`.

Only synthesizable RTL change relative to that archive: 28 startup writes in
`camera/working/rtl/ov5640_init.v`. All values were checked against Linux's
OV5640 initialization table. The repeated 3634=40 write is intentional and
matches the later existing write. This is an experiment, not a confirmed
black-sun diagnosis or colour fix. Some registers may already hold these
values by default. The rest of the Linux camera mode was not copied.

The earlier raw/ISP diagnostic copy is saved in
`local_artifacts/isp_readback_working_before_analog_20261104` and Git history.
No camera archive, CNN model, or data split was modified.

## Preserved settings

- Manual exposure: 128 lines; manual gain: 1x; VTS: 520.
- Capture: 320 x 240 YUYV; original YUV-to-RGB conversion and qualified receiver.
- HDMI: 640 x 480, 60 Hz; use the monitor's aspect setting to avoid stretching.
- Wiring: PCLK JA physical 1 / U27; D6 JB physical 8 / U25.
- Original RGB565 snapshot protocol; do not use the newer raw-YUYV decoder.

## Board comparison (pending)

1. Confirm actual wiring and JTAG connection before loading. No flash writes.
2. Program `builds/analog_reference128_20261104_r4/camera_hdmi.bit` manually.
3. Only SW6 up; press BTNC and wait five seconds.
4. Keep the camera stationary. Include a white object, coloured objects and
   the troublesome ceiling light. Record darkness, overall colour, green/purple
   patches and any pulsing. Photograph the scene if useful.
5. For sensor bars, SW1 and SW6 up, then BTNC. Record any new streaks or tint.
6. If needed, reload `camera/versions/last_exposure_test/camera_hdmi.bit`,
   only SW6 up, BTNC, and compare the SAME scene/lighting.

Original baseline bit SHA256:
`2a4cfed6b09c4b06ff9c2b739cb0a284b4b2b251db3c72dc4affbced6fdf0185`.

Passing simulation/timing establishes build correctness within those checks;
physical colour improvement still requires this comparison. Keep the new
candidate separate until the user confirms an improvement. No Git push has
been authorized for this work.
