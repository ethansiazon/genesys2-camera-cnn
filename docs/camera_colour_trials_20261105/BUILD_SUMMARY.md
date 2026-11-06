# Camera-only r8 build evidence

| Candidate | GenericRGB565 | Setup slack(ns) | Hold slack(ns) | Duration |
|---|---:|---:|---:|---:|
| YUYV control |0|+0.294|+0.075|342s|
| RGB565 comparison |1|+0.214|+0.069|374s|

Both completed route/DRC with zero errors and zero critical warnings. Frozen
RTL/constraints/build script hashes match exactly; build generic selects format.
Tests and host scripts were run offline. No board was connected or programmed.
Original preferred bitstream hash was rechecked before packaging. No source,
model weights or split from the CNN was changed. All new physical colour,
brightness, saturation and highlight outcomes remain UNTESTED.

YUYV SHA256:2f50ac8395cb33fcb877e517d98aff484d4db0a068f5df79323af7939e73832c
RGB565 SHA256:10aa69b4e8f142f553127b2ab570ff06b5ce5513df5bd32269201dd4908e2f9f
Original SHA256:2a4cfed6b09c4b06ff9c2b739cb0a284b4b2b251db3c72dc4affbced6fdf0185

Camera input320x240; HDMI640x480 at60Hz. Memory includes debug raw snapshot.
These are not fullcamera/CNN/DDR/tracking integration resource or speed results.
