# Manual white-balance isolation candidate (r5)

Based on the physically read-back r3 128-line diagnostic, whose complete sensor
write sequence matched the preferred last_exposure_test archive. Only seven
manual white-balance writes added in synthesizable RTL. R/G/B gains are all
0x0400 (1x); automatic gain selection is overridden with 3406=01. This is a
diagnostic control, not a calibrated colour preset or a promised highlight fix.

Exposure remains 128 lines, sensor gain 1x, VTS 520, capture 320x240 and HDMI
640x480 at 60 Hz. Receiver, conversion, memory and diagnostic logic match r3.
No rejected Linux analog-startup writes are present. Normal view only SW6 up,
BTNC. SW0 rising refreshes the 48 sensor reads without writes. SW7 records RAW
YUYV, decoded with scripts/analyze_raw_yuv.py (not the old RGB565 decoder).

Original preferred .bit remains camera/versions/last_exposure_test/camera_hdmi.bit.
The copied .bit in this working folder is that OLD baseline, not these edits.
New build output: builds/unity_wb128_20261104_r5/camera_hdmi.bit.
Rejected r4 copy is preserved in local_artifacts/rejected_analog_working_20261104_r4.
Keep PCLK JA1 / D6 JB8. Do not program automatically or push without approval.
