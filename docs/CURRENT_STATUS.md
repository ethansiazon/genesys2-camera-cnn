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
User reports loading the diagnostic: image looks more purple and remains dark.
Awaiting current UART register readback and raw-frame capture. Do not treat the
new image as an improvement or start exposure/gamma changes before comparison.

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

## Active exposure experiment - 4 November

After raw-128 readback/live capture and clean-looking synthetic bars, the
working source changes only the exposure setpoint from 128 to 192 lines. Gain
stays 1x and frame timing stays fixed. Two targeted functional checks passed.
The guarded single-thread build is builds/exposure192_20261104_r2.
User has JTAG only connected, board powered, only SW6 up. The board still runs
the raw-128 build until the new candidate is explicitly loaded.

The exposure-192 build completed in 328 seconds with setup slack +0.245 ns and
hold slack +0.063 ns, zero routing errors. Its frozen RTL differs from raw-128
only in ov5640_init.v (one exposure setpoint plus its comment). The user has
been asked to load it manually and compare the same scene. Physical results
remain pending; do not claim a brightness or colour improvement yet.

## Current ISP readback experiment - 4 November

Exposure-192 was physically tested and read back correctly, but the user reports
brighter output with worse green/purple colouring. It was not promoted. Its raw
capture is saved locally; framing differs from the raw-128 capture, so aggregate
statistics are not a paired brightness/colour effect estimate.

The active working source now RESTORES 128-line exposure/1x gain and extends
read-only diagnostics to 48 registers, including AWB gains and colour-matrix/ISP
controls. Its sensor-write table matches the captured raw-128 version exactly.
SW0 rising edge repeats READS only, leaving init_done/camera streaming intact;
SW0 still shows the overlay while up. Normal viewing remains only SW6 up. UART
page D1640004 carries the additional 24 ISP values; D1640002 remains compatible.
The initialization/refresh/NACK and top-level UART-page/capture checks passed.
Build: builds/isp_readback128_20261104_r3, guarded single-thread, not yet complete.
User moved USB to JTAG only, board powered, only SW6 up. No new version has yet
been loaded. Current physical board remains the exposure-192 test.

ISP readback build completed in 318 seconds; setup +0.289 ns, hold +0.071 ns,
zero routing errors. Bitstream:
builds/isp_readback128_20261104_r3/camera_hdmi.bit
SHA256 b5efa2d466facf3e188cf2b164fae4c355505f2c105526f556e868b12b1e4e90.
User was asked to load it, only SW6 up, BTNC then wait 5 seconds, pulse SW0 up
for 1 second and down (no BTNC), then move to UART/J15 only while main power
stays on. That reply is pending. Do not read COM3 until UART is confirmed.
After confirmation verify D1640004 ISP packets and read actual AWB/CMX controls.
Current code performs no new ISP writes; causes of colour distortion remain open.

## Controlled analog/reference-startup trial - 4 November

User authorized a fresh candidate based directly on last_exposure_test. The
previous pending ISP-readback build was not confirmed loaded; its working copy
is preserved in local_artifacts/isp_readback_working_before_analog_20261104.
Active working RTL now matches the preferred archive except 28 verified Linux
reference startup writes in ov5640_init.v. No receiver, colour conversion,
exposure, gain, clock, wiring or memory changes. Original RGB565 snapshot format
restored with the archive. New output: builds/analog_reference128_20261104_r4.
Physical appearance remains untested. Do not call this a confirmed colour fix.

Reference-startup build completed in 332 seconds. All 16 functional fixtures
passed. Routed setup slack +0.279 ns, hold +0.084 ns; zero routing errors,
zero ERROR/CRITICAL WARNING log entries. Bit SHA256:
7f287fae0a415126e231f36e4bb643f9bd449e1739dbd76941cc210354ffc7ab.
Separate project: builds/camera_analog_reference128_20261104_project/camera_hdmi.xpr.
The frozen RTL hashes match camera/working. The preferred original .bit hash
was rechecked unchanged. No board programming or remote Git push performed.
Next: user loads r4 via JTAG after wiring confirmation; only SW6 up, BTNC,
wait 5 seconds and compare same scene/white objects/ceiling light. Save the
physical observation before promoting or changing another variable.
