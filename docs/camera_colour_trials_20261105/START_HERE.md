# Camera colour test kit

Prepared November 5, 2026. These are test candidates, not confirmed fixes.
The board was unavailable during preparation. No camera settings or board
programming were performed. Your preferred original is included unchanged.

## The files

| Folder | What it does |
|---|---|
| 00_original | Your preferred original image. Use this to go back. |
| 01_yuyv_control | The existing colour format, with live UART controls. |
| 02_rgb565_comparison | A different camera colour format that bypasses the FPGA YUV conversion. |
| scripts | Reversible exposure, saturation, gamma and white-balance trials. |
| source | Matching camera source code and rebuild tools. |
| reports | Simulation and build evidence. |

Both new versions use the same wiring, image size, clocks and starting exposure.
Neither includes the r7 drive-strength change. Camera input is 320 x 240;
HDMI output is 640 x 480 at 60 Hz. These are camera-only builds, without the CNN.

## When the board is available

1. Check WIRING.md first. If your teammates changed the wiring, do not program
   from the old pin map. Saved wiring has PCLK on JA1 and D6 on JB8.
2. In Vivado Hardware Manager, choose Program Device and select
   01_yuyv_control/camera_hdmi.bit. Keep ONLY SW6 up. Press BTNC.
3. Wait about 10 seconds for the camera's automatic colour adjustment to settle.
   Include white paper and red/blue objects. Check bright ceiling lights in a
   separate shot. Keep the camera, scene, lighting and monitor settings fixed.
4. Load 02_rgb565_comparison/camera_hdmi.bit with the same switches and reset.
   Compare darkness, colour strength, white/grey tint and the light glitches.
5. Write down the result in RESULTS.csv. A photo of each version helps.
6. If the new version is worse, load 00_original/camera_hdmi.bit with ONLY SW6
   up and press BTNC. Nothing in this kit changes the board's flash memory.

For camera-generated colour bars, put SW1 and SW6 up and press BTNC. Test the
bars and the actual live image separately. Clean bars do not prove correct live
colour. SW5 shows FPGA-generated bars and bypasses the camera.

Leave SW2, SW3 and SW4 down for the first comparison. They are YUV controls and
have no effect in the RGB565 build. Leave SW7 down for normal viewing and UART
commands. SW7 up records a still image. SW0 enables the diagnostic overlay.

## Tuning without another build

The new versions support live changes through USB-UART/J15. The original
recovery bitstream does not support these controls. Keep the board powered
when moving the USB cable from JTAG to UART. Confirm the correct COM port.

Start by allowing white balance to settle, then freeze it with HoldWB. Test
one setting family at a time, keeping the same scene:

- Exposure128 / Exposure192 / Exposure256: compare brightness at fixed gain.
- GammaReference: try the published gamma curve.
- Saturation0 / Saturation1 / Saturation2: compare published colour matrices.
- AutoWB: resume automatic white balance.
- WBOffice: optional room-lighting preset if neutral paper is actually tinted.

These make ten available trials including HoldWB. More exposure or saturation
can make some problems worse; neither repairs corrupted pixels. Restore each
trial before testing another family. BTNC returns to startup settings.

Open PowerShell in this kit folder to list or inspect trials without connecting:

```powershell
./scripts/camera_trials.ps1 -Action List
./scripts/camera_trials.ps1 -Action Plan -Trial GammaReference -ExpectedFormat RGB565
```

See TECHNICAL_GUIDE.md for apply, rollback, raw-capture and rebuild commands.
Each actual trial checks the sensor and format, saves the old settings, and
checks written values. A failed transfer stops rather than retrying repeatedly.
Do not run a capture reader and a control script at the same time.

## What the results will tell us

If RGB565 is clearly better, the YUV path deserves further investigation. If
both show the same light artefacts, sensor processing and received camera data
remain possible causes. Neither result by itself proves the camera is faulty.

The builds passed digital tests and routed timing. We still need real-camera
comparisons before choosing a new preferred version.
