# Shipped bitstreams

Ready-to-program images for the two boards, added by Niko on 9 November 2026.
Both are JTAG-volatile unless written to flash or booted from a USB stick: a
power cycle or PROG returns the board to whatever is in its own flash.
`SHA256SUMS` in each folder lists the exact bytes; check before programming.

## genesys2/ -- camera -> CNN -> Basys link, rev 3 (HDMI live view)

| | |
|---|---|
| File | `cnn_subsystem_top.bit` (+ `cnn_subsystem_top.ltx` for the JTAG AXI debug core) |
| Part | xc7k325tffg900-2, Vivado 2023.2, built 6 Nov 2026 03:46 |
| Sources | `~/fpga/genesys2-cv-model` on Niko's PC, mirrored in `Menlo2925/FPGA_Project_Lab` under `genesys2/cv-model/` |
| Timing | met, WNS +0.018 ns (strategy Performance_ExplorePostRoutePhysOpt) |
| Utilisation | 69,001 LUT, 376 BRAM, 310 DSP |
| Camera RTL | Ethan's R13 (`camera/versions/reference_readout_20fps_filter_rgb565_r13`), RGB565, 20 fps, majority filter; white-balance hold `H`/`A` over USB-UART |
| Pipeline | 320x240 frame -> DDR3 (3 rotating buffers) -> centre crop 256x192 -> CNN @ 140 MHz -> decoder -> POSITION frame on Pmod JD1 to the Basys 3 JB1; HDMI shows the live frame, crop window, reticle and green/yellow detection box |
| Measured | every other frame processed (CNN + decoder ~53 ms > 50 ms frame), 10 reports/s, capture -> POSITION 78.08 ms with 0.24 ms spread over 241 frames |

Bring-up: SW6 up, press BTNC, LED map in `fpga_system/`'s PHASE3 notes in the
lab repo. Program with Vivado hardware manager or the lab repo's
`scripts/program.tcl` (it picks the Kintex even when the Basys shares the hub).

## basys3/ -- turret controller, tracking-only debug build

| | |
|---|---|
| File | `top.bit` (+ `top.ltx`: ILA/VIO probe map, the ILA is unreadable without it) |
| Part | xc7a35tcpg236-1, Vivado 2023.2, built 9 Nov 2026 22:35 |
| Sources | `Menlo2925/FPGA_Project_Lab`, `build_debug.tcl -tclargs outdir=build_debug_trackonly_scale` |
| Timing | met, WNS +0.128 ns |
| Build | `ENGAGE_ALLOWED=0` (tracks, never fires), `CAMERA_X_FLIP=1`, `CAMERA_Y_FLIP=0`, `CAMERA_SCALE_Q8=128` (camera offsets halved after the 1.9x over-scale was measured), TF02 rangefinder on JB2, fire pulse on JA10, Genesys link on JB1 |
| Known issue | acquire lead is still enabled in this image; on a USB/QSPI boot it never gets the JTAG lead-0 push, so the turret can overshoot a moving target. A `build_debug_trackonly_nolead` image with `ACQUIRE_LEAD_ENABLE=0` is being built and will replace this one. |

Niko boots the Basys from a USB stick (JP1 = USB, exactly one `.bit` on the
stick), so this file can be copied there as-is.
