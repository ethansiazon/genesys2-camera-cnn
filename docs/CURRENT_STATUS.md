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

### Physical result: reference-startup block rejected

User reports r4 is "way worse everything looks darker with more purple with a
slight green hue (farther from real colors)". This is a qualitative regression;
no r4 UART settings/raw capture was obtained. Do not repeat or promote this
register block. It does not establish a black-sun root cause or identify which
setting changed the appearance. Working source still records this rejected
candidate; the preferred archive and earlier diagnostic copies remain intact.
Next physical action: reload camera/versions/last_exposure_test/camera_hdmi.bit,
only SW6 up, BTNC and wait five seconds; confirm preferred image returns.
Baseline restoration is not yet confirmed. A read-only ISP/AWB diagnostic is
already built as r3 if needed later; do not call it physically tested or read
UART until the user confirms the appropriate connection and loaded version.

User confirms preferred baseline image restored. Rejected r4 is no longer the
reported running design. r3 bit hash and its complete sensor-write sequence
were rechecked against the preferred baseline: identical writes. Next request
is manual loading of r3, readback refresh via SW0 and UART-only connection.
No new compiler job or automatic board programming started.

## Physical ISP readback obtained

User confirmed r3 loaded, SW0 refreshed and UART only. COM3 capture saved at
local_results/physical_isp_readback128_20261104_r3/diagnostics_20261104_235316.json.
Camera ID 5640, switches 40, both read-NACK masks zero, complete 76800-pixel
frames at 320x240. White balance automatic (3406=00); sampled gains R=1.1455x,
G=1.2031x, B=1.0000x. Unequal gains alone do not prove incorrect calibration.
The colour matrix matches datasheet power-on values; 5480=00 alone does NOT
prove gamma disabled. User observes green hue on white objects in this r3 image.
Readbacks are latched by refresh, not continuous measurements of gain changes.
Next physical request: stationary white/colour reference and bright light,
raise SW7 without reset for raw snapshot. Keep UART only for transfer.
No new colour settings, compiler job or board programming initiated here.

Raw r3 snapshot raw_yuv_20261104_235655 completed with all 5487 packets;
user then requested redo due to setup mistake. Keep this capture out of white
reference calibration. Await SW7 down/up after scene is ready, no BTNC.
Do not infer white-object chroma or change gains from the invalidated frame.

## Manual white-balance isolation candidate r5

Redo raw frame completed: local_results/physical_isp_readback128_20261104_r3/white_reference_redo/raw_yuv_20261105_000004.txt.
5487 packets, 153600 bytes, zero transfer resynchronizations; visible bright-light
colour errors reproduced in independent laptop conversion. Not a calibrated
white chart; do not fit gains from this frame. Preparing r5 from physically
read-back r3, only seven manual WB writes added. Colour gains R/G/B=1x and
3406=01, exposure128/sensor gain1x unchanged. Equal gains are a diagnostic
control, not final calibration. Previous rejected r4 working folder preserved
in local_artifacts/rejected_analog_working_20261104_r4. No analog-block retry.
Current physical board still r3. Physical r5 performance remains unknown.

R5 unity-WB build complete in 318 seconds. Setup +0.295 ns, hold +0.076 ns,
zero routing errors and no ERROR/CRITICAL WARNING log entries. Three targeted
checks passed: original 48-register refresh, manual WB ordering/values before
streaming and no writes on refresh, and top-level inverted-HREF capture/UART.
Bit: builds/unity_wb128_20261104_r5/camera_hdmi.bit
SHA256: 754433b86e128950ec96100fdaff250574c8752eb2ead9154d61e219b90a4602
User has confirmed JTAG only, only SW6 up. Await manual programming, BTNC,
5-second settling and physical image report. No appearance claim made.
Baseline fallback remains unchanged; working source hashes match this build.

## User reports purple haze after r5 instructions

User supplied a monitor photograph and reports persistent purple haze/hue and
frustration with lack of image improvement. Severe bright-light colour errors
also remain visible. R5 is not accepted as an improvement. Its actual manual
gain registers have not been physically read back; do not claim that verified.
Phone photograph is not calibrated/paired raw data. No new sensor setting was
chosen from it. No compiler is running. Current report follows r5 instructions;
preferred fallback remains available. See camera_unity_wb_20261104/PHYSICAL_RESULT.json.

Code audit confirms UART diagnostics are transmit-only. Proposed efficiency
change: add UART RX and serialized, checked camera-register controls so most
setting comparisons do not require rebuilding. Official Digilent master XDC
confirms uart_tx_in is Y20 (FPGA input); existing uart_rx_out is Y23 (FPGA TX).
See CAMERA_LIVE_CONTROL_PLAN.md. This is not implemented or promised as a
colour fix. Seek exact ESP configuration that previously produced clean video.

## Live controls r6 under development

Exact known-working ESP code is unavailable per user. Preserving r5 working
copy in local_artifacts/unity_wb_working_before_live_controls_r5. New working
copy starts from r3 diagnostic with exact preferred startup sensor writes,
auto WB, exposure128 and gain1x. Adding UART RX/control, not new colour tuning.
Control owns SCCB only through init FSM handshake after startup/refresh.
No physical build/load result yet; current user image report follows r5.

R6 live-control build completed in 318 seconds. Setup +0.235 ns, hold
+0.084 ns, zero route errors and no ERROR/CRITICAL WARNING log entries.
Six targeted simulations plus host encoder/decoder self-test passed.
Initial full serial integration simulation exceeded 90s; only its simulation
UART rate was increased to reduce simulated bit periods. Physical baud remains
115200. The actual-wire serial/camera/telemetry check then passed in 63.6s.

Bit: builds/live_control128_20261105_r6/camera_hdmi.bit
SHA256 257cb8304019cf2636d342623904b6077e33d7b4ac333410c8d32fd16f004e98
Project: builds/camera_live_control_20261105_project/camera_hdmi.xpr
Preferred startup sensor writes and original archived bit hash were verified
unchanged. Frozen build hashes match active RTL/constraints. No new colour
recipe is applied at startup. Physical UART control and image quality remain
unverified. Next user action: load r6 through JTAG, only SW6 up, BTNC and wait
5s; move to UART only with main power maintained. Then run host Read/Ping
without writes to verify signature, ID, startup exposure/AWB and actual read
handshake before any live colour tuning. No Git push or auto-programming.

User confirms r6 loaded, only SW6 up, UART only. First host Read could not open
COM3 because Windows currently lists no serial port. Follow-up PnP inventory
also lists no VID_0403/FTDIBUS board USB device. No ping/register operation was
sent and no settings changed (session changes/reads empty). Requested reseating
UART/J15 and laptop USB ends while main board power stays on. Re-enumerate the
actual serial port before trying it. Do not rebuild or change drivers for this
connection observation. Physical r6 control validation remains pending.

## R6 physical live controls validated

Known-working cable at J15 and another laptop USB port restored FTDI COM3.
No driver/OS changes. Live-control signature verified; ID5640 and baseline
exposure128/gain1x read correctly. No-op 3406=00 write/readback passed. Then
3406=01 froze existing automatic gains; all six gain bytes exactly match the
prior live read: R=04CD, G=052F, B=0400 (approximately1.200/1.296/1.000x).
No new gain values or colour recipe selected. This is actual host-to-camera
read/write evidence, not image-quality evidence. Only WB mode changed.
Current board r6, UART only, only SW6 up, manual WB holds the prior gains.
Do not reset before the requested neutral-reference snapshot: BTNC would
restore automatic WB. Next user action is matte white paper centred on desk,
coloured object beside it, no bright lamp/screen in view; then raise SW7 without
BTNC. Save raw neutral reference before choosing colour gains.

## R6 matte-paper reference obtained

Complete raw local_results/live_controls/r6_neutral_reference_20261105/raw_yuv_20261105_005506.txt; 5487 packets, no
transfer resyncs. White paper clearly visible with red-handled tool. Three
selected unclipped paper regions median RGB approximately107/107/105,102/102/99,
114/111/111 using independent limited-range conversion. Chroma medians Cb127,
Cr128/129. This does not justify broad WB correction and does not establish
colour correctness everywhere. No colour-gain changes selected. The scene is
dim; proposed next isolated test exposure128->160 lines (+25%) with current
gains held, camera/paper/lighting stationary. Await user SW7 down (SW6 stays up)
before sending commands, since firmware blocks commands during raw replay.
Current board remains exposure128, manual held gains, UART only, SW6/SW7 up.

## Live exposure160 trial applied

User confirmed SW7 down, same scene, no reset. Before/after physical readbacks
verify only3501 changed08->0A (128->160 lines). Exposure manual, sensor gain1x,
WB manual and all six colour-gain bytes unchanged. No rebuild. Volatile setting
only; no new image-quality claim. User observation and same-scene raw capture
are pending. Next request SW7 up after settling, without BTNC. Current board
R6 UART only, SW6 up, exposure160, held gainsR04CD/G052F/B0400. To undo viaUART
write3501=08 or restore the saved write-session before value. BTNC restores
preferred startup128 and automatic WB, so do not reset during paired comparison.

Exposure160 raw after-frame completed at
local_results/live_controls/r6_exposure160_capture_20261105/raw_yuv_20261105_010205.txt.
Fresh frame15218 vs prior9211, but paper/camera framing shifted; no paired
brightness effect estimated. User did not notice a change and asked about UART
operation; explained controls act live without a reset/rebuild. Proposed next
visual bracket256 lines while holding WB, using complete3500/3501/3502 write
sequence as in Espressif set_aec_value, checking VTS first. No claim that the
earlier single-byte update failed; source sequencing is followed to remove an
uncertainty. Current physical setting remains160, SW6/SW7 up, UART only. Await
SW7 down before writes. No colour gains changed; no image fix claimed.

## New source review: prioritize register-address audit

User supplied Camera Journey repo, generic pasted notes, manufacturer PDF and
MIT pixel_reconstruct lab. No further exposure changes were made while reviewing.
Concrete mismatch found: our reference-tagged startup3016=C3 /3020=21 differ
from Espressif DRIVE_CAPABILITY302C=C3 /CLOCK_POL_CONTROL4740=21 and MIT ROM.
Manufacturer PDF confirms3016 and302C have different functions. Current table
also has tested final4740=22, which must remain unchanged for a controlled test.
This is not a proved colour cause, but deserves priority over broad tuning.
See CAMERA_REFERENCE_AUDIT_20261105.md for pinned sources, limits and next steps.
Current r6 write allowlist blocks pad/clock writes: no host bypass. Next useful
physical read whenSW7down:3016/3020/302C, read-only. A corrected drive-address
entry needs a separate preserved candidate/build. Larger256-line exposure was
not applied. Board remains160, held manualWB, UART only, SW6/SW7up per last reply.


## R7 address correction prepared after physical audit

User confirmed SW7down/SW6up/UART/noreset. Read-only session completed with
ID5640,3016=03,3020=21,302C=02,4740=22,exposure160,manualWB. All mutations=[]
(PRECHANGE_READBACK.json). 302C drive field is default1x; intendedC3 never reached
that address. This is not a proved colour cause. Working entry6 now writes
302C=C3 instead of3016=C3, the only RTL change. Other settings and protected
receiver are unchanged. See camera_drive_address_20261105/PLAN.md. Original
archived favourite and r6 source backup preserved. Simulations/build pending;
no programming or runtime pad write occurred. Current running board remainsr6,
exposure160,heldWB,SW6up/SW7down,UARTonly. New startup will restore128/autoWB.


R7 build complete: drive_address128_20261105_r7/camera_hdmi.bit;
SHA256 1a87f4655d11fde536ed1252f4ec258d0e653c671082723395f994d3d6fde45b.
320seconds,setup+0.168ns,hold+0.074ns,route/DRCzeroerrors,noERROR/CRITICALWARNING.
Three relevant simulations passed; frozen source audit confirms only entry6
address/comment differs fromr6. No physical image result or board programming.
User confirmedJTAGonly/mainpoweron/onlySW6up. Await manual Program Device,
thenBTNC/fivesecondsettle and same-scene observation. New startup128/autoWB.
To rollback load immutable last_exposure_test/camera_hdmi.bit (onlySW6up+BTNC).


## R7 rejected by physical observation

User answered "Worse" to r7 comparison of purple tint/green bright areas.
Saved camera_drive_address_20261105/PHYSICAL_RESULT.json. No raw capture or
post-load register verification; do not infer exact cause from this observation.
R7 remains preserved in frozen build; it is not the preferred camera version.
Restore immutable last_exposure_test/camera_hdmi.bit (SHA verified), onlySW6up,
BTNC and five-second settle. Await user confirmation before assuming rollback.
Working init source restored to r6 baseline from preserved backup; runtime UART
controls remain available in source. This source restore is not board programming.
Candidate RGB565 comparison can isolate YUV interpretation/conversion and sensor
format path; requires dedicated capture/format handling, not a whole MIT ROM copy.
No new build or camera setting changes launched after rejection. Current board
inferredr7/JTAGonly/onlySW6up based on requested test; rollback not yet confirmed.


## Physical clarification and numerical overflow audit

User clarified board is stillr7 and now looks roughly similar to preferred
last_exposure_test after startup tint settles. Initial worse report revised;
PHYSICAL_RESULT.json preserves both observations. No rollback confirmed; working
source remainsr6 while loaded boardr7 (deliberate separation recorded).
Bright lights still have dark inner region and green/coloured edges.

Converter RTL matches original andr7 byte-for-byte. 25088 independent real-valued
reference vectors passed(all256Y,7Cb*7Cr boundary/neutral/extreme values,both
range modes,tolerance2). Signed22bit intermediates and explicit saturation make
simple converter wraparound unlikely; this is not a proof against all hardware
or sensor arithmetic faults. Earlier rawYUYV lamp capture was independently
decoded with OpenCV and visually reproduces dark/coloured ring. Some ring Y
values are already29/41 before FPGA RGBconversion. This narrows away from
HDMI-only or converter-only explanation but cannot distinguish sensor/ISP
processing from received-byte errors/phase. No new hardware changes in audit.
Next priority controlled RGB565 format comparison, with dedicated packing path,
same image geometry/clocks/exposure and original source preserved. Do not
claim every fix tried or assume sensor defective. AWB startup settling is a
hypothesis consistent with automaticWB, not a verified cause of this observation.


## Offline colour trialsr8 prepared; board unavailable

User says teammates currently have board. No hardware connections attempted.
Source supports build-timeYUYV/RGB565 comparison fromr6 baseline; RGB565 bypasses
FPGAcolourconversion and tags raw snapshotsR565. Published reversible runtime
exposure/saturation/gamma/WB trials prepared, with format/ID/WB/VTS preflight.
All targeted simulations and offlinehost/decoder tests passed. See
camera_colour_trials_20261105/PLAN.md. Original archived favourite untouched.
Next build two separate frozen camera-only variants sequentially under guard;
no claimed image improvement before board comparisons. No push authorized.


## R8 offline preparation complete: both bitstreams passed

Both frozen-source builds passed routed timing, route/DRC and zero critical
warnings/errors. RGB565374s setup+0.214/hold+0.069ns; YUYV342s setup+0.294/
hold+0.075ns. Frozen source SHA manifests identical, generic differsRGB5651/0.
See camera_colour_trials_20261105/BUILD_SUMMARY.md and START_HERE.md.
Ten reversible runtime trial recipes ready, no actual trial applied in this
turn. RGB565 data decoding/tagging and legacyYUV path tested. Board unavailable
with teammates; no UART/JTAG access, no programming. Original archived favourite
unchanged, noCNN changes or Git push. Next step is physical same-scene format
comparison before stacking picture tuning. Do not call these confirmed fixes.
Desktop test kit and ZIP will contain baseline, both builds, matching source,
recipes, instructions, blank observationsheet and evidence. User can test later.
