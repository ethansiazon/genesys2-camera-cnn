# Faster camera diagnosis: proposed next engineering step

Status: design review only, not implemented or built. Preferred baseline remains
camera/versions/last_exposure_test. Recent analog-startup and equal-gain trials
have not established acceptable live colour. No further full-register batch is
selected from the photograph alone.

## Evidence and limits

- Clean synthetic camera bars and complete captures do not establish every
  live pixel byte is correct. Timing/signal integrity remain possible factors.
- Laptop conversion of saved YUYV reproduces highlight artefacts, so HDMI-only
  changes cannot fully explain/fix those captures.
- Equal colour gains are a diagnostic control, not colour calibration under
  room lighting. Purple output alone does not identify the faulty stage.
- Settings such as gamma control 5480=00 must be interpreted against the
  specification; zero does not by itself mean gamma is disabled.

## Why change the test method

Current host tools only receive UART diagnostics; the top has no UART RX input.
Every setting trial therefore changes a startup table and rebuilds the FPGA.
The Genesys 2 already has the other USB-UART signal on FPGA Y20, LVCMOS33,
called uart_tx_in in Digilent's master XDC. The existing FPGA TX is Y23.
Adding input/control logic requires no camera rewiring. Check the board pin
reference again at implementation; never drive the USB bridge's output.

Primary board reference:
https://raw.githubusercontent.com/Digilent/digilent-xdc/master/Genesys-2-Master.xdc

## Proposed implementation requirements

1. Start from preferred sensor writes plus the physically checked r3 diagnostic
   logic. Preserve short-pulse receiver, clocks, conversion and archived bits.
2. Synchronize UART input and receive 115200 8N1 with framing/error detection.
3. Add bounded checked commands for camera-register read/write. Allow only
   relevant documented colour/exposure registers for writes; reject malformed,
   unknown or incomplete commands. Include request IDs and explicit status.
4. Arbitrate SCCB ownership: initialization/refresh and host transactions cannot
   overlap. Hold a request until safe, or report busy; never partially mux a
   transaction. Camera streaming and video continue through adjustments.
5. Read back every write and report NACK/timeouts. Log before/after register
   values and permit restoring a saved preset. Default startup stays preferred.
6. Coordinate command responses with existing telemetry/snapshot UART output;
   never interleave bytes or mislabel packet contents. Bound host waits.
7. Test serial framing, invalid commands, register allowlist, SCCB arbitration,
   timeout/NACK handling, restoration and unchanged top-level camera capture.
   Build one guarded candidate only after checks pass; no automatic programming.

After physical validation, setting trials should take seconds rather than a
new implementation run. This interface does not itself fix image quality.

## Colour investigation after interface validation

Use a stationary matte white/grey reference and coloured objects in ordinary
light, with a separate bright-light test. Save unmodified raw captures and
compare neutral chroma, clipping, colour appearance and brightness separately.
Change one named control at a time; keep a baseline preset and rollback log.
If the ESP code that produced the known-good picture is available, compare its
sensor mode, pixel format, clocks and initialization instead of assuming its
entire table is interchangeable with the present FPGA mode.

No flash programming, camera rewiring, driver/Windows changes or Git push is
included. No claim of correct live colours or CNN benefit follows from this plan.
