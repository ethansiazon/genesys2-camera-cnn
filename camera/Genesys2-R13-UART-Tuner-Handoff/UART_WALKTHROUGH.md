# Follow a live adjustment end to end

1. Tune_R13.cmd starts tune_r13.ps1 in Windows PowerShell. The tuner reads the
   sensor ID and timing/format settings, then turns commands into bounded
   changes to named picture registers. Example: exposure 400 encodes 400 << 4,
   or 0x01900, as 3500=00, 3501=19, 3502=00. Only changed bytes are sent.
2. camera_control.ps1 opens the Genesys 2 USB serial bridge at 115200 baud,
   8 data bits, no parity, one stop bit. It pings before issuing requests.
   The host saves the before value and the verified reply for each write.
3. top_genesys2.v receives bytes with uart_rx.v. camera_uart_control.v checks
   packet format, XOR and the write allowlist. It allows a single request at
   a time and hands the address and operation to ov5640_init.v through the
   host_valid/host_ready interface.
4. ov5640_init.v owns the sensor setup and arbitrates the existing SCCB bus.
   When the sensor is initialized and idle, it runs the host request through
   sccb_master.v. A write is followed by a separate SCCB read and comparison.
5. uart_report.v formats the reply and uart_tx.v sends it back over J15.
   The host filters out unrelated diagnostics and matches sequence, opcode,
   address and requested value. HDMI is still the live picture.
6. tune_r13.ps1 keeps undo history and saves a JSON snapshot on request.
   The UART log is in local_results/camera_tuner. A reset reapplies the
   bitstream's startup table. Preserve the live test and final startup preset
   as separate steps.

## Wire format

Request is eight binary bytes:

    A5 5A SEQ OP ADDR_HI ADDR_LO VALUE XOR

XOR is the XOR of the first seven bytes. Sequence is an 8-bit correlation ID.
Opcode 50 pings, 52 reads and 57 writes with readback. All opcode values above
are hex. A read uses a zero request value. Example request for sequence 1,
read 3406:

    A5 5A 01 52 34 06 00 9E

Reply is an ASCII line with eight space-separated 32-bit hex words:

    D1650001 SEQ OP STATUS ADDRESS REQUESTED ACTUAL 4C495645

Status codes: 0 OK, 1 malformed, 2 write denied, 3 recording active,
4 sensor NACK, 5 timeout, 6 UART framing error, 7 write readback mismatch.
D164 packets are diagnostics and are not command replies. SW7 switches the
link to the recording stream, so a blocked command may time out at the host.
Stop on an uncertain write and inspect the saved transaction log before retrying.

## Where to edit

- Host controls and allowed UI values: camera/working/scripts/tune_r13.ps1.
- Binary framing, timeout and request/reply validation: camera_control.ps1 in
  the same folder. camera_trials.json supplies the reference gamma recipe.
- FPGA write policy: camera/working/rtl/camera_uart_control.v, write_allowed.
  The current tuner works within the existing image-register allowlist.
  Keep sensor clocks, wiring and resolution separate from image tuning.
- FPGA connection and UART pin mapping: top_genesys2.v and
  camera/working/constraints/genesys2.xdc.
- Permanent picture settings: ov5640_init.v startup table.
  REFERENCE_READOUT=5 is original R13, and 6 adds the saved picture.
- Protocol tests: tb_uart_rx.v, tb_camera_uart_control.v,
  tb_init_host_control.v and tb_top_live_control.v in camera/working/sim.

A register readback confirms what the sensor accepted. Judge the actual color
and brightness on HDMI in the intended lighting.
