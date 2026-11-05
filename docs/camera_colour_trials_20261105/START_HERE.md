# Camera colour tests: start here

Prepared November5,2026. The new versions passed offline checks; neither has
been tested on the actual camera yet. No board was connected during this work.
The original preferred bitstream remains unchanged.

## What is ready

| File/folder | Purpose |
|---|---|
| 00_original/camera_hdmi.bit | Your preferred original; recovery option |
| 01_yuyv_control/camera_hdmi.bit | Matched control, current YUV colour format and UART tuning |
| 02_rgb565_comparison/camera_hdmi.bit | Camera sends RGB565; FPGA unpacks colours directly |
| scripts/camera_trials.ps1 | Ten reversible picture-setting trials through UART |
| source/ | Matching RTL, constraints, scripts and simulations |
| RESULTS.csv | Record actual comparisons; no improvement assumed |

Both new builds keep320x240 capture,640x480 HDMI60Hz, the tested clocks,
manual exposure128/gain1x and startup automatic white balance. New RGB does
not keep the r7 drive-strength change. This isolates colour format against
r6/favourite. Same preferred source wiring:PCLK JA1,D6 JB8.

## First board session

1. Confirm the board still uses our saved camera wiring. If your teammates
   rewired anything, stop and compare WIRING.md before programming.
2. Use Vivado Hardware Manager -> Program Device. Start with01_yuyv_control.
   OnlySW6up, all othersdown; pressBTNC. Wait10seconds for colours to settle.
3. Keep camera, scene, lighting and monitor settings fixed. Include matte white
   paper and red/blue objects. Separately check the bright-light problem.
4. Load02_rgb565_comparison, same switches and reset. Compare the same scene.
   Take pictures and note: neutral whites, red/blue correctness, darkness,
   saturation, streaks and green/dark highlights. UseRESULTS.csv.
5. Test camera bars separately withSW1+SW6up andBTNC. Clean bars do not prove
   correct live colours. SW5 is the FPGA-only HDMI test pattern.
6. If either build is unusable, reload00_original, onlySW6up+BTNC.

SW2/SW3/SW4 are YUV byte/range/order controls. InRGB mode they have no effect.
Keep themdown for the first comparison. SW7 records a still frame; leave itdown
for normal viewing and UART commands. SW0 enables overlay/refreshes readback.
Avoid ceiling lamps in the neutral-paper colour check; test them separately.

## Picture tuning without rebuilding

Only use the new live-control builds. Keep board power on and move USB to
UART/J15 only after programming. SW7DOWN; no other serial reader open. BTNC
resets all volatile tuning back to startup defaults.

Open PowerShell in this test folder:

```powershell
./scripts/camera_trials.ps1 -Action List
./scripts/camera_trials.ps1 -Action Plan -Trial Saturation1 -ExpectedFormat RGB565
```

These two commands do not connect to hardware. For an actual trial:

```powershell
./scripts/camera_trials.ps1 -Action Apply -Trial HoldWB -ExpectedFormat RGB565 -Port COM3 -OutDir ./measurements/hold_wb_01
./scripts/camera_trials.ps1 -Action Apply -Trial Exposure192 -ExpectedFormat RGB565 -Port COM3 -OutDir ./measurements/exposure192_01
```

UseExpectedFormat YUYV for01. Find actual COM port inDeviceManager, not by
assumingCOM3 on another laptop. HoldWB freezes settled gains; it is not a
manual unity-gain recipe. First compare formats; then try only one setting
family at a time. Suggested order: Exposure192(with128/256 brackets), restore;
GammaReference,restore; Saturation0,restore; Saturation1,restore; Saturation2.
OfficeWB is optional only if neutral paper actually looks tinted.
Longer exposure may make light glitches worse; increased saturation cannot
repair wrong pixels. These are hypotheses to test, not ten promised fixes.

Restore a trial's saved pre-change values before trying another family:

```powershell
./scripts/camera_trials.ps1 -Action Restore -ExpectedFormat RGB565 -Port COM3 -RestoreFile ./measurements/exposure192_01/change/SESSION.json -OutDir ./measurements/undo_exposure192_01
```

If a transfer fails, stop and inspect the saved session. Some writes may have
landed; do not assume the camera is unchanged and do not repeatedly retry.
Restore files are for the same board/build/session, not a different camera.
The scripts validate sensorID,format,heldWB and exposure-frame margin. Each
write has readback and saved before-values. No format/clock/pad runtime writes.
No script automatically cycles through all experiments.

## Save the actual camera pixels

After settling, putSW7up without pressingBTNC and keepUART connected. Then:

```powershell
./scripts/read_snapshot.ps1 -Port COM3 -ExpectedFormat RGB565 -OutDir ./measurements/rgb_frame_01
python ./scripts/analyze_camera_capture.py ./measurements/rgb_frame_01/raw_yuv_TIMESTAMP.txt --expected-format rgb565
```

ReplaceTIMESTAMP with the saved filename. The historicalraw_yuv filename is
not the format authority: metadata distinguishesR565 fromYUV0. Use the new
analyzer forRGB. It needsnumpy+Pillow; no package installs are performed here.
LowerSW7 before another control command. Raw capture means bytes received
from camera before FPGAconversion; sensorISP still processed them.

## Rebuild on another laptop

UseVivado2026.1/xc7k325tffg900-2. The source/ folder contains the small camera
repository layout (camera/working plus tools). From that source/ directory, source
`tools/create_camera_project.tcl` with new project directory andrgb565 oryuyv:

```tcl
set argv [list C:/g2_rgb_trial rgb565]
source tools/create_camera_project.tcl
```

KeepSIM_FAST_INIT=0 and confirmRGB565=1 forRGB,0 forYUV. Build artifacts include
source hashes and routed timing reports. Camera-only resources/timing do not
establish fullcamera+CNNfit, colour quality or drone detection performance.
No CNN model, data split, board flash or teammate project was changed.
