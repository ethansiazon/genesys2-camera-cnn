# Camera handoff â€” start here

Goal: OV5640 live colour image through the Genesys 2 HDMI OUT/TX. No CNN is included in this camera design. Package prepared 28 October 2026 from the saved 20 October work. Nothing was programmed or rebuilt during packaging.

## Which version?

| Folder under versions/ | What it is | Physical observation |
|---|---|---|
| best_receiver | Best verified receiver, recommended debugging baseline | Camera test bars clean, live image clear, bright/white regions still falsely coloured. |
| last_exposure_test | **Last version tested before stopping** | Lower fixed exposure/gain reduced most false colours, but image became very dark; bright ceiling lights still green. |
| raw_recorder | Same qualified receiver with raw YUYV recorder | Includes a complete saved raw frame and conversion previews for offline diagnosis. |

Each has matching RTL, constraints, simulation sources, build scripts, reports and camera_hdmi.bit. Original archive README/restore scripts are historical: their local Windows paths and statements about what is currently programmed are NOT current instructions. Use this README and the new scripts/ folder instead. The final exposure trial did not have a fresh UART readback/raw capture; its result was visual only.

## Requirements and opening in Vivado

- Windows with AMD Vivado (original builds: 2026.1), Kintex-7 device support for **xc7k325tffg900-2**. Other releases have not been verified.
- Extract the ZIP first, preferably to a short local path such as C:/g2_camera. Do not build inside the ZIP or a synced network folder.
- From this camera folder, run the following in Vivado's Tcl Console to create an editable project from the best receiver:

```tcl
cd C:/g2_camera
set argv [list best_receiver C:/g2_camera_work]
source scripts/create_project.tcl
```

Change best_receiver to last_exposure_test or raw_recorder if wanted. The script refuses to overwrite an existing project. It only creates a project; it does NOT build or program anything. Open the resulting camera_hdmi.xpr on later visits. No extra camera IP repository is required; the camera source and HDMI logic are included.

## Building a new bitstream

Use one build at a time, with enough free RAM. From a Vivado command prompt:

```powershell
vivado -mode batch -source C:/g2_camera/versions/best_receiver/scripts/build.tcl -tclargs C:/g2_camera_build
```

Use a new output directory for each experiment. This is the existing canonical batch build: maximum 2 threads, BRAM cascade-height limit 1, setup/hold checks before writing the bitstream. It never connects to a board. For GUI synthesis the new project script also sets the same cascade-height limit. Do not discard that setting: an earlier BRAM implementation produced a DRC error without it. The canonical Tcl build does not monitor free RAM; the optional scripts/build_with_guard.py wrapper stops its own build process tree if free RAM falls below 1.5 GiB. Use that on a 16 GB laptop.

## Loading an existing bitstream

First check WIRING.md against the actual wires, with power OFF while changing wires. These files assume the later PCLK/D6 swap. With correct wiring and main power on, connect USB-JTAG/J17, open Vivado Hardware Manager, connect to the board, select the FPGA, choose the desired versions/.../camera_hdmi.bit, and use Program Device. This is volatile FPGA programming, not QSPI/SD flashing. A bare .bit does not survive power-off or PROG. No packaged startup script automatically programs a board.

After programming, put ONLY SW6 up, press BTNC and wait several seconds for live viewing. SW1 up + BTNC selects camera-generated colour bars. SW5 selects FPGA-generated test bars (bypasses camera). SW7 enables the diagnostic capture/replay in recorder versions; leave it down for normal viewing. Keep SW2/SW3 down for the baseline. Test with the exact build's RTL before reassigning switches.

## UART debugging

USB-UART/J15 is separate from USB-JTAG/J17. Serial settings: 115200 baud, 8 data bits, no parity, 1 stop bit. Select the COM port shown on the receiving laptop; COM3 in old scripts is only an old default. Close other serial readers first. Use the scripts belonging to the selected version. For example, from PowerShell:

```powershell
./versions/raw_recorder/scripts/read_uart.ps1 -Port COM5
./versions/raw_recorder/scripts/read_snapshot.ps1 -Port COM5
```

Check each script's parameters before use. The saved raw record and analysis are under versions/raw_recorder/reports/. Capture: 320 x 240, 153600 YUYV bytes, 5487 packets, zero reported transfer resync/address errors. This confirms transfer completeness, not that every camera byte was correct. Camera output is converted YUV to RGB for HDMI; the recorder preserves the original camera bytes. UART data transfer is slow and is not video streaming.

There were Windows blue screens during earlier USB/driver debugging on Ethan's laptop. Drivers were repaired there; that is not a diagnosis for another laptop. No driver installers or repair procedure are supplied for automatic execution. The cautious tested workflow used one board USB connection at a time, keeping board power on while moving between JTAG and UART. A power cycle loses the bitstream.

## Continue from here

1. Reproduce clean FPGA bars, then clean camera bars with best_receiver before changing exposure or colour conversion.
2. Preserve the qualified receiver: rejecting short input pulses removed visible streaks. Current code treats the camera signals as sampled inputs; do not assume the older source-synchronous experiment is the current implementation.
3. Compare raw_recorder bytes/decoded previews with a real scene and exact register readback. Isolate exposure, gain, byte format and colour-processing changes one at a time.
4. The last manual-exposure trial used 128 lines, VTS 520 and gain 1x. It improved colour symptoms but was too dark. This does not prove exposure was the sole cause.
5. Do not repeat the rejected bulk ISP settings blindly: they increased purple distortion. SW3 changed contrast without fixing colour; alternate byte order was also worse.

The unresolved problem is bright-region colour/brightness, not HDMI lock: FPGA-generated bars were clean. Full camera/CNN integration has not been built. See the separate CV package for that work. Saved reports contain historical absolute paths; runnable handoff entry points are relative or accept your own paths.


## Optional offline tests and raw-data analysis

Icarus Verilog can run the included functional testbenches without a board:
```powershell
python scripts/run_simulations.py --variant best_receiver --out C:/g2_camera_sim --iverilog C:/iverilog/bin/iverilog.exe --vvp C:/iverilog/bin/vvp.exe
```
This new wrapper directs results into a new folder and preserves the archived reports. Top-level simulation substitutes clock/HDMI primitives; it is not proof of physical timing. Camera-side analysis scripts need Python, NumPy and Pillow. Use raw_recorder/scripts/analyze_raw_yuv.py with an explicit raw-recorder trace filename; analyze_snapshot.py is for the older RGB565 recorder format, not raw YUYV. Run analysis on a copy if preserving original outputs.

Background sources used in the camera work: OV5640 product specification (https://cdn.sparkfun.com/datasheets/Sensors/LightImaging/OV5640_datasheet.pdf), Espressif's OV5640 driver (https://github.com/espressif/esp32-camera/blob/master/sensors/ov5640.c), and the Genesys 2 reference documentation. Their register examples are references, not proof that every module behaves identically.
