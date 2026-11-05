# Still-image capture from the preferred camera version

This project copies `last_exposure_test` exactly. Its original bitstream already
contains a full-frame snapshot recorder, so the capture feature requires no
new FPGA circuitry or camera settings. The new work is the laptop save tool.
The separate colour experiments and active camera source are unchanged.

Camera input: 320 x 240 YUYV. FPGA converts to RGB for display; the existing
recorder makes a 5/6/5-bit RGB copy of those pixels and transfers it over UART.
The PNG contains that copy expanded to RGB8. It is not raw Bayer, a full-precision
RGB888 capture or a screenshot of the HDMI monitor. No image enhancement is used.

## On this laptop

Open the new Vivado project at:

`C:/Users/ethan/Desktop/Genesys2-Still-Capture-20261105/project/camera_hdmi.xpr`

The matching, unchanged preferred bitstream is in that folder's parent:

`C:/Users/ethan/Desktop/Genesys2-Still-Capture-20261105/camera_hdmi.bit`

1. Check WIRING.md. Saved wiring is PCLK on JA1 and D6 on JB8. If teammates
   changed it, compare their wiring before programming. Module supply is 3.3 V.
2. Program the included bitstream through JTAG/J17 in Hardware Manager.
   Keep ONLY SW6 up; press BTNC, then allow about 10 seconds to settle.
3. Keep board power on and move the USB cable to UART/J15 only. Leave SW7 down.
4. Double-click `Capture_Image.cmd` in the project folder. A PowerShell window
   opens. The launcher allows this local script for that PowerShell process only;
   it does not change permanent Windows execution-policy settings. It finds the UART port when unambiguous and checks the normal-view
   telemetry before asking for a capture. It never writes camera registers.
5. Once it says READY, hold the camera still and raise SW7. Leave SW6 up.
   Do not press BTNC. The next full frame freezes; transfer usually takes
   roughly 40–90 seconds at 115200 baud.
6. Wait for DONE, then lower SW7. To take another photo, run the launcher again.

If automatic port selection is ambiguous, run from a terminal in the project:

```powershell
./Capture_Image.cmd -Port COM3
```

Replace COM3 with the actual USB-UART port. No driver repair or Windows changes
are included. Do not run another UART reader or control script at the same time.
Starting with SW7 already up would replay an old frozen frame; the new reader
requires normal live telemetry first to avoid silently accepting that case.

## Saved files

Each photo gets a separate folder under Desktop/Genesys2-Camera-Images:

- `image.png`: native 320 x 240 RGB image for CNN testing.
- `preview.png`: 960 x 720 enlarged view, for looking at the photo.
- `transfer.txt`: original UART packets.
- `IMAGE.json`: frame number, image and transfer hashes, format and limits.
- `CAPTURE.json`: port, switch telemetry and transfer status.

Only a complete, correctly ordered frame with valid metadata is accepted.
Partial transfers are preserved for diagnosis and never marked as a valid image.
The original protocol has no payload checksum, so these checks do not establish
that every received sensor or serial bit is electrically correct.

## Using the images with the CNN

Use `image.png`, not the enlarged preview. Keep the original frame; use the
retained model's own RGB/crop/resize/padding/normalization steps when testing.
Its neural input is 256 x 192, but that does not mean the saved camera photo
should be forcibly stretched to that size beforehand. No CNN weights changed.

A still photo can test detection. It cannot evaluate the full motion-proposal
and tracking pipeline, which needs successive frames or video. A photo with no
drone is useful for false detections, but cannot measure drone recall.

The preferred camera's darkness and bright-light colour artefacts remain.
This capture tool does not fix those and does not add CNN inference to the FPGA.

## Verification and portability

RTL/constraints match the preferred archive byte-for-byte; the bitstream SHA256
is `2a4cfed6b09c4b06ff9c2b739cb0a284b4b2b251db3c72dc4affbced6fdf0185`.
The decoder was checked on every RGB565 encoding, complete/partial metadata,
packet order, bad padding and output-overwrite protection. Host parser/switch
checks run without opening USB. Physical transfer with this new launcher is
pending board availability.

The launcher uses the existing Python environment on Ethan's laptop. For another
machine, use Python with Pillow and pass its executable via `-Python PATH` to
`source/scripts/capture_image.ps1`. The Vivado source is local in `source/`.
To move the project folder, recreate it with `create_project.tcl` and a new output
path; do not assume cached absolute Vivado paths survive a move.
