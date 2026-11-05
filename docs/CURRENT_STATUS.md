# Status at import â€” 4 November 2026

## Camera: Ethan's saved work

Active baseline changed on 4 November 2026: Ethan selected the final
manual-exposure version as his preferred picture. `camera/working` now starts
from `camera/versions/last_exposure_test`, with identical RTL/constraints.
See CAMERA_PREFERRED_BASELINE_20261104.json for hashes and current observations.
Monitor stretching was corrected using the monitor's aspect-ratio setting.

The earlier qualified-receiver checkpoint is `camera/versions/best_receiver`.
Its historical bitstream SHA256:
`b0cb809916ab4df4265cfb1f2007d68e4598f4b6cde008da9a39093d6e46a9b3`.
It produced clean sensor test bars and clear live images, with false colours
around bright/white objects. Qualified short-pulse rejection removed streaks.
This is sampled-input capture; do not revert to the earlier source-sync experiment.

`last_exposure_test` is a separate final trial: 128 exposure lines, VTS 520,
gain 1x, white balance unchanged. Visual feedback: fewer false colours, very dark,
ceiling lights still green. Its final trial had no fresh physical register
readback/raw capture. Cause of the remaining issue is unproved.

`raw_recorder` holds the earlier complete 320 x 240 YUYV capture: 153,600 bytes,
5,487 packets, zero reported transfer resync/address errors. Transfer completeness
does not prove all incoming camera values were correct. Raw captures are ignored
by Git and retained in the local/original archives.

Next: use the confirmed preferred exposure baseline with matching wiring/switches.
Capture exact registers and raw pixels for normal and bright objects. Compare
received YUV values and offline RGB conversion; isolate capture/byte interpretation
from sensor configuration. Then vary one setting and compare against baseline.
No new camera programming or heavy build occurred during repository preparation.

## Active raw diagnostic — 4 November

The editable camera/working source now adds raw YUYV observation/recording using
the earlier tested observer and snapshot format. Exposure remains 128 lines,
gain 1x, VTS 520; camera conversion and HDMI paths are unchanged. SW7 recordings
use D16C packets and require analyze_raw_yuv.py. Host captures default to ignored
local_results/captures. The register reader labels the current exposure/gain
readback addresses correctly. Seventeen functional fixtures and the host decoder
fixture passed. The guarded single-thread build is in
builds/raw_exposure_diagnostic_20261104_r1; inspect its STATUS.json before acting.
The raw diagnostic built successfully in about 5 minutes. Setup slack +0.175 ns,
hold slack +0.078 ns, zero routing errors. See camera_raw_diagnostic_20261104.
Awaiting user loading/comparison; physical image quality is not yet verified.

## CNN and Niko's board work

Retained V5 epoch 8 EMA: 331,114 parameters, 256 x 192 RGB ROI, P2/P3 heads.
R9 software motion proposals, approximate camera-translation compensation and
single-target tracking are separate from CNN computation and remain unintegrated
in hardware. Decoder selection uses raw objectness and geometry; class fields
must not be presented as validated aircraft rejection.

Niko's Oct 29 system ran prepared images on actual Genesys 2 hardware via JTAG:
CNN at 140 MHz, decoder at 100 MHz. 100 selected positive frames from 10 videos:
96 centres within 32 pixels, mean error 12.83 pixels (256 x 192 image coordinates).
These are not precision/recall/96%-accuracy or negative-scene tests. All seven
decoded fields matched the 100 MHz run. CSV evidence has one >32px outlier in
V_DRONE_045 and three in V_DRONE_078; the handoff's all-four-in-078 prose is wrong.
Physical UART bytes and continuous auto-retrigger behaviour remain unverified.

Oct 29 routed totals: 68,048 LUTs (33.39%), 72,907 FFs (17.89%), 308 DSPs (36.67%),
366 RAMB36 + 15 RAMB18 (83.93% block RAM). This includes DDR/CNN/decoder/debug
support, but no live camera, motion/crop or tracker. Of these, coefficient staging
alone uses 256 RAMB36 (57.53% of device BRAM). Removing it is an opportunity, not
a completed optimization; simply subtracting yields 26.4%, not a new fit report.
The earlier 23.37% result measured the isolated routed CNN core.

No full live-camera CNN pipeline or complete-system frame rate has been proved.
Do not use imported old notes saying the board is currently running a bitstream
as a statement of the present board state.
