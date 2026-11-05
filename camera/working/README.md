# Best verified camera receiver — saved 20 October 2026

This is the qualified_sampler bitstream, preserved with its matching RTL,
constraints and build evidence. It is the best physically verified version so
far; it is NOT a claim that the camera is fully finished.

Verified: clean camera colour bars, clear live image, 320×240 capture displayed
at 640×480, complete76,800-pixel frame, and no long corrupted rows in the saved
test-pattern capture. Remaining issue: false colours around bright/white objects.
The later combined ISP-reference recipe made colours worse and was rejected.

## Normal live-camera controls

- Only SW6 up; SW0–SW5 and SW7 down. Press BTNC and wait a few seconds.
- SW1 up + BTNC selects the camera's colour bars.
- SW5 up selects FPGA-generated bars, bypassing the camera.
- SW7 up records/replays a diagnostic copy over UART; it does not freeze HDMI.
- SW3 changes conversion range; it changed contrast but did not fix false colours.

Wiring: PCLK→JA physical1; D6→JB physical8. Preserve the remaining confirmed
camera wiring. This archive includes no CNN or actuator logic.

## Restore through JTAG only

Keep board main power on. Connect only USB-JTAG/J17; leave UART/J15 disconnected.
Run RESTORE_BEST.ps1 in local PowerShell. It verifies the bitstream hash, USB
identity and absence of other hardware tools before loading via Vivado.
This loads volatile FPGA configuration, NOT QSPI flash. Board power-off/PROG
requires reloading. No drivers or Windows settings are changed.

For diagnostics, wait until programming tools close, then move to UART/J15 only.
Detailed build evidence and example captures are in reports/.
