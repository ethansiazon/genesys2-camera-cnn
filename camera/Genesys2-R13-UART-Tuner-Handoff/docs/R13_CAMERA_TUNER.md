# Tune the R13 camera live

Load the preferred R13 camera bitstream once. On this laptop it is at
`builds/reference_readout_20fps_filter_rgb565_r13/camera_hdmi.bit`.
Leave the board powered and HDMI connected, then move the USB cable from
JTAG/J17 to UART/J15. Keep only SW6 up. Close other serial tools before opening
the tuner. After the white balance settles, double-click
`camera/working/scripts/Tune_R13.cmd`. It uses COM3 by default. If Windows has
assigned another port, run `Tune_R13.cmd -Port COM4` with the actual port number.

Watch HDMI while typing commands at the `camera:` prompt. Type `show` to get
your starting values. Try one change at a time under the same lighting.

| Command | What it adjusts |
|---|---|
| `exposure 400` | Light collected by the sensor. Higher values can blur motion. |
| `gain 1.25` | Sensor gain. Higher values can make grain more visible. |
| `wb auto` | Let white balance adapt to the lighting. |
| `wb hold` | Hold the current settled white balance. |
| `wb 1.20 1.00 1.85` | Set red, green and blue gains directly. Use `show` to find a starting point. |
| `brightness 1` | Change picture brightness after capture. |
| `contrast 1` | Change the separation between light and dark tones. |
| `saturation 1` | Change how strong the colors look. |
| `gamma reference` | Try a published tone curve. `gamma start` returns to your session's starting curve. |
| `undo` | Reverse the latest adjustment. |
| `reset` | Restore the settings read when this session opened. |
| `save daylight` | Export the live readback to `daylight.json` in the session folder. |
| `help` | List commands and ranges. |
| `quit` | Close the tuner. The current picture stays active until camera reset. |

Send the saved JSON when you have a picture you want as a startup preset. The
terminal prints its full path. Auto white-balance gains in the raw readback are
observations. The startup settings list excludes those gains when auto mode is
active, so a preset can preserve auto mode.

BTNC restores the bitstream's original startup picture. Reopen the tuner after
using BTNC so the undo history starts from the restored picture. If a write
fails partway, the tuner stops and leaves the before values and readbacks in
the session folder. If no USB serial port is found, check J15 and Device Manager.

The tuner verifies the live sensor mode and uses the existing UART register
write list. R11 and R13 share sensor settings, so select R13 in Vivado before
tuning. Focus, sharpness, denoise, clock and resolution have no controls here.
The new command workflow was checked in Windows PowerShell against a simulated
camera. The physical appearance of the tone and color controls still needs a
board comparison.

Register references: [OmniVision OV5640 specification, sections 5.1 and 7.26](https://dl.sipeed.com/MAIX/HDK/Chip_DS/OV5640-datasheet.pdf)
and [Espressif OV5640 driver](https://raw.githubusercontent.com/espressif/esp32-camera/master/sensors/ov5640.c).
