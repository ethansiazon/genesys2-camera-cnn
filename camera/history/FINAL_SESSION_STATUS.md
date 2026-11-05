# Camera session stopped — final visual result, 20 October 2026

User authorized one final manual exposure/gain trial, then stopping whether good
or bad. That trial is complete. No further build, programming or investigation
was started after the result. Resume only when the user asks.

## Observed outcome

User reports fewer false colours and most weird colours gone, but the image is
really dark. Bright ceiling lights still have green glitching. Pulsing was not
reported separately. This is a partial improvement with a significant brightness
tradeoff, NOT a complete fix or proof of the underlying cause. Manual exposure
was set to 128 lines (VTS 520), gain 1x; white balance was unchanged. No physical
register readback or raw capture was collected for this final trial.

## Preserved versions

The current board runs manual_exposure_once. Its separate archive is:
`C:\Users\ethan\Desktop\genesys2_camera_hdmi_20261019\saved_versions\manual_exposure_once_20261020`
Bitstream SHA256: `2a4cfed6b09c4b06ff9c2b739cb0a284b4b2b251db3c72dc4affbced6fdf0185`
The previous best verified receiver archive is untouched:
`C:\Users\ethan\Desktop\genesys2_camera_hdmi_20261019\saved_versions\best_camera_20261020`
Neither version is being claimed as a complete colour solution. Keep both to
compare when work resumes. Earlier raw image data remains in the separate
raw_camera_capture_20261020 archive.

## Stopping state

JTAG/J17 only; ONLY SW6 up. User was instructed to press BTNC for live viewing.
Programming finished successfully and hardware tools have exited. No active
camera build, serial transfer or analysis remains. No QSPI, driver or Windows
changes. Camera wiring remains PCLK to JA1, D6 to JB8, other wiring unchanged.
Power off/PROG loses volatile FPGA configuration; previous best archive includes
restore instructions. Nothing will resume automatically from this session.

## Evidence for any future session

Lower fixed exposure/gain changed the symptom. This supports checking exposure-
dependent behaviour and received values, but does not distinguish camera image
processing from data capture/format faults. Do not claim overexposure is proven
or assume higher exposure can safely restore brightness without bringing back
false colours. Keep changes isolated and preserve the qualified receiver.
