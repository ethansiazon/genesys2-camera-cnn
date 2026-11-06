# Camera live controls r6

Purpose: speed up measured camera-setting comparisons. This interface is not
an image-quality fix. Startup sensor writes exactly match the preferred
`last_exposure_test` version, with automatic white balance and exposure128/1x.
The original receiver, colour converter and memory sources are unchanged from
r3. Y20 is now an FPGA UART input; Y23 remains output. No external camera
rewiring, OS/driver changes or flash writes.

## Operation

Board: only SW6 up for normal view; BTNC restores the complete startup recipe.
Host controls require SW7 down. SW7 raw recording retains its existing output
protocol; host operations received during recording are rejected, with their
response deferred until recording ends. Do not pipeline commands. One request
must receive its matching complete response before sending another.

Runtime transactions are accepted by the existing init FSM only in its idle
post-init state. Initialization and SW0 read-refresh take priority. No separate
driver can seize or partially mux the SCCB wires. init_done remains asserted
while a host transaction is performed; capture continues. An accepted write
is always followed by a separate readback. NACK, timeout and mismatch are
reported explicitly. There is no automatic retry. A write with a failed or
lost response can already have taken effect; retain the saved before values.

## Host tool

`camera/working/scripts/camera_control.ps1` uses .NET SerialPort (no extra package).
It first verifies a ping response before attempting register operations.

Examples from the repository root (ONLY after correct firmware and UART are ready):

```powershell
& camera/working/scripts/camera_control.ps1 -Action Ping -Port COM3
& camera/working/scripts/camera_control.ps1 -Action Read -Port COM3
& camera/working/scripts/camera_control.ps1 -Action Read -Registers 5000,5001,5005,5381,5382
& camera/working/scripts/camera_control.ps1 -Action Preset -Preset UnityWB
& camera/working/scripts/camera_control.ps1 -Action Preset -Preset AutoWB
& camera/working/scripts/camera_control.ps1 -Action Write -Writes '3501=06'
& camera/working/scripts/camera_control.ps1 -Action Restore -RestoreFile 'ABSOLUTE_PATH_TO_SAVED_SESSION.json'
```

Use quoted register names to retain hexadecimal formatting if needed. Each
write reads and saves the old value before sending the change. Every session
gets a new `local_results/live_controls/.../SESSION.json` plus wire/request logs.
Restore replays saved before values in reverse order, with write/readback checks.
Preset BaselineExposure restores exposure128, sensor gain1x and manual AEC/AGC;
it does not undo other colour-register changes. BTNC reruns the entire baseline.

Equal-gain UnityWB is a diagnostic control, not a calibrated indoor/daylight
white-balance preset. No preset is automatically applied by loading r6.

## Wire protocol

115200 baud, 8 data bits, no parity, 1 stop bit. Binary eight-byte request:

`A5 5A sequence opcode address-high address-low value checksum`

Checksum is the XOR of the previous seven bytes. Opcode 50=ping, 52=read,
57=write with readback (all hexadecimal). IDs are eight-bit. Host tool validates
ID, opcode, address, requested value and response signature, not just the tag.
The command parser times out partial frames after 50 ms and pending operations
after two seconds. Host wait is bounded at six seconds, with no automatic retry.
Malformed UART stops are rejected; the receiver waits for idle after a break.

Response: an atomic, existing-style eight-word ASCII hex packet:

`D1650001 sequence opcode status address requested readback 4C495645`

Status: 0=OK, 1=bad format/checksum, 2=denied register/value, 3=recording active,
4=camera NACK, 5=timeout, 6=UART framing error, 7=readback mismatch.
Normal D164 telemetry and D16C raw packets retain their original format.
The ordinary 48-register diagnostic page is latched; use SW0 to refresh it.
Command responses reflect their actual transaction results.

Reads can address any 16-bit register; unsupported addresses may NACK. Writes
are restricted in hardware to 3400..3406; 3500..3503,350A,350B; 5000,5001,5005;
5180..5197,519E; 5380..538B; 5480..5490; 5580..558C. Reserved high bits in gain
fields and unsupported 3502 fractional lines are rejected. Clocks, DVP geometry,
pad directions, PLL/power/reset and sensor output-format registers are excluded.

## Validation and remaining physical work

Simulation covers RX bytes/framing, CRC, whitelist, bounded errors, write
readback, startup/refresh arbitration and actual top-level serial/SCCB access.
The end-to-end top-level fixture checks command/telemetry packet boundaries,
record-mode denial/deferred reply, rejected writes causing no mutation, and
continued 640-pixel synthetic capture. SIM_FAST_INIT uses faster test UART;
physical firmware uses 115200. These simulations do not validate board timing,
signal integrity or live colour; physical ping/read validation is still required.

First physical step: load r6, only SW6 up, BTNC, wait five seconds; then UART
only. Read ID and startup registers WITHOUT applying new tuning. Once verified,
compare one named setting on a stationary matte neutral/colour scene, keeping
brightness and clipping separate from colour neutrality. Preserve raw captures.

Primary references:
- https://raw.githubusercontent.com/Digilent/digilent-xdc/master/Genesys-2-Master.xdc
- https://cdn.sparkfun.com/datasheets/Sensors/LightImaging/OV5640_datasheet.pdf
- https://raw.githubusercontent.com/espressif/esp32-camera/master/sensors/ov5640.c
