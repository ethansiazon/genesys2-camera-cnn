# Genesys 2 R13 camera UART tuner handoff

This folder contains the published camera source needed to explain, run or
rebuild the live tuner. Start with this page, then use UART_WALKTHROUGH.md to
follow the request from PowerShell through Verilog to the sensor.

Source: https://github.com/ethansiazon/genesys2-camera-cnn/tree/camera/color-debug
Exact published source revision: fede591750a48b4744b572a511da408bc8affe35
The GitHub repository may require access. The selected source files are copied
here at their original paths. Their hashes are in MANIFEST.json.

## Use it on the existing Genesys 2 camera setup

1. Verify the hardware against camera/WIRING.md. The supplied original R13
   bitstream uses PCLK on JA1 and D6 on JB8.
2. Program the FPGA with builds/reference_readout_20fps_filter_rgb565_r13/camera_hdmi.bit via JTAG/J17 in
   Vivado Hardware Manager. Keep only SW6 up and press BTNC to initialize.
3. Leave board power and HDMI connected. Move the USB cable to UART/J15 only.
   Leave SW7 down so raw recording does not take over the serial port.
4. Double-click camera/working/scripts/Tune_R13.cmd. It defaults to COM3.
   Use Tune_R13.cmd -Port COM4 if Device Manager lists COM4.
5. Type show, then try commands such as exposure 400, contrast 1, or wb auto.
   Watch the live image on HDMI. Use undo to reverse a change and save my_pick
   to export a JSON file. The console prints its path. See docs/R13_CAMERA_TUNER.md.

The original R13 bitstream was tested on the board and uses automatic white
balance at startup. It is included as a separate local artifact. This is the
same bitstream that was used when the live tuner was developed. The user later
selected picture settings in the tuner and built a separate startup preset.
The included source can also rebuild that profile. Each live change applies
immediately and lasts until camera initialization. A saved JSON file records
the values for a future build.

## Verify or rebuild

Offline host checks, run in PowerShell from this folder:

    & .\camera\working\scripts\Tune_R13.cmd -Help
    & .\camera\working\scripts\camera_control.ps1 -Action SelfTest

UART protocol and sensor arbitration simulation, with Python and Icarus Verilog
(iverilog and vvp on PATH, or pass --iverilog and --vvp):

    python tools/test_camera.py --out local_results/uart_check --only tb_uart_rx tb_camera_uart_control tb_init_host_control tb_top_live_control

Original R13 build, with Vivado 2026.1, Python and psutil:

    python tools/build_camera_guarded.py --vivado "C:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat" --out builds/r13_rebuild --format rgb565 --readout reference2x-20fps-filter

Use the local Vivado installation path and a fresh output directory. The
guarded build uses one thread and requires at least 3 GiB free to start.
The saved startup preset uses reference2x-20fps-saved-picture instead.
