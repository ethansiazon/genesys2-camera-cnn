# Reference audit prompted by Ethan's new sources

Read-only audit; no source or sensor settings changed in this review.
Live exposure trial is on hold while a stronger initialization-address issue
is evaluated. Current reported board state remains r6, exposure160, manual
held WB gains R04CD/G052F/B0400, UART only, SW6/SW7 up.

## Highest-priority finding: reference address translation mismatch

Active ov5640_init.v labels these startup writes as reference values:

- entry6: 3016=C3
- entry7: 3020=21

Espressif sensor_default_regs instead uses DRIVE_CAPABILITY=C3 and
CLOCK_POL_CONTROL=21. Its register definitions resolve these names to 302C
and 4740 respectively. MIT's ROM explicitly contains 302CC3 and 474021 in
the same startup sequence. Our current table later writes 4740=22 for the
tested receiver configuration; that later choice must not be overwritten
blindly from a different-polarity reference.

The supplied manufacturer PDF confirms 3016 is PAD OUTPUT ENABLE 00 (strobe,
SIOD and debug fields), while 302C is PAD CONTROL 00 (drive strength in bits7:6).
They are not interchangeable. 3020 has no entry in this PDF's register table;
that absence alone does not prove it is a harmful or invalid register.

This is a definite mismatch with the claimed reference, not proof of a colour
root cause. Code provenance suggests mistranslated symbolic addresses, but
original design intent has not been independently recovered. Do not silently
edit immutable archived baselines. Next steps: read actual3016/3020/302C once
SW7 is down; prepare a separately tested correction to the drive-address entry,
preserving the measured slow clock, window, receiver and final4740=22 polarity.
Treat removal of the other undocumented write as a separate controlled change.
R6's write allowlist intentionally excludes these pad/clock addresses, so do
not bypass it from the host script. Any change requires a reviewed new build.

Primary references inspected:
- https://fpga.mit.edu/6205/_static/F24/default_files/week05/rom.mem
- https://raw.githubusercontent.com/espressif/esp32-camera/master/sensors/private_include/ov5640_settings.h
- https://raw.githubusercontent.com/espressif/esp32-camera/master/sensors/private_include/ov5640_regs.h
- C:/Users/ethan/Downloads/OV5640_datasheet.pdf, version2.03, PDF pages23,101,103

Espressif inspected file blob SHAs:
settings: f52572fa2b0e8ffe0791ab64a77bf96c8c2bb541
definitions: c28d80f5bb5843d072a0285a820731b1c9489f3c

## MIT capture materials

https://fpga.mit.edu/6205/F24/assignments/camera/pixel_reconstruct
https://fpga.mit.edu/6205/F24/assignments/camera/camera_1

The MIT receiver uses RGB565 two-byte pixels, active-low blanking syncs,
byte-phase reset during blanking, and 200MHz oversampling. Its supplied setup
is 720p RGB565, subsampled to320x180 in FPGA memory. Our camera is320x240 YUYV,
with a tested qualified receiver and a separate YUV-to-RGB conversion. Similar
sampling architecture is useful corroboration, not a timing proof for our wires.

Useful new comparison path: a separate RGB565 diagnostic can remove YUV chroma
pairing/conversion from the path, keeping the original available. A successful
RGB565 image would narrow the investigation; it would not automatically prove
all YUV processing is wrong. A full MIT ROM transplant would also change mode,
clocks/polarities and image size, so it is not a controlled drop-in correction.

## Camera Journey repository

https://github.com/davemuscle/camera_journey
Inspected commit:539c6dd464dbebc72a94ce18b204a67cd8566d4f
Inspected code: doc/ov5640_init.txt, ov5640/best_cam_config.txt,
python/ov5640.py, ov5640/ov5640_vstream.vhd.

Relevant: OV5640 parallel capture, runtime UART register control, line-length
checks and offline image verification. The author also reports unresolved
intensive raw noise and eventually moved to an IP camera; this is not a clean,
proven reference that guarantees an image-quality cure.

Its presets target RAW Bayer/1080p with different PLL/window/ISP settings, not
our YUV path. Files named best_cam_config do not establish a validated final
recipe. Our existing raw recorder captures camera-processed YUV before FPGA
RGB conversion; a Bayer diagnostic would bypass more sensor processing and
could later be reconstructed on the laptop, but needs its own capture path.
No downloaded repository code was executed or copied into synthesizable RTL.

## Pasted generic summary

Useful as background only. The universal5V supply instruction does not apply
to our module labelled3V and previously measured at3.31V; keep existing3.3V.
MIPI details do not apply to our parallel DVP connection. Sampling edge/sync
polarity depend on the configured mode. The short Verilog example is incomplete
and is not a replacement for our qualified byte/line receiver. An initialization
table need not consume block RAM or contain hundreds of writes to be correct.

No new compiler, hardware programming, USB-driver change or live tuning was
started as part of this audit. The larger exposure256 trial is not applied.
