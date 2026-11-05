# Camera work safely stopped — 20 October 2026

The user requested stopping after loading the recorder and saving one raw frame.
That boundary is complete. Do not resume builds, camera fixes, research, training,
or programming unless the user asks to continue.

## Saved best working camera version

Best archive: `C:\Users\ethan\Desktop\genesys2_camera_hdmi_20261019\saved_versions\best_camera_20261020`
Bitstream SHA256: `b0cb809916ab4df4265cfb1f2007d68e4598f4b6cde008da9a39093d6e46a9b3`
All 72 manifest files verified. Matching source, wiring, build evidence,
restore instructions and RESTORE_BEST.ps1 are preserved there.
Clean camera test bars and the streak fix were physically verified. Live video
is recognisable, but bright/white objects still have false colours. This is not
a claim that the camera work is finished. The combined ISP recipe was rejected
after it made colours worse; the range switch only changed contrast.

## Final raw capture

Independent recorder archive: `C:\Users\ethan\Desktop\genesys2_camera_hdmi_20261019\saved_versions\raw_camera_capture_20261020`
Original raw YUYV bytes: `C:\Users\ethan\Desktop\genesys2_camera_hdmi_20261019\saved_versions\raw_camera_capture_20261020\reports\raw_yuv_20261020_003241.yuyv.bin`
SHA256: `802e56a9cd02c91c22c63cbf999174be948b00e2cdefe12d9f6622a27502f329`
Preview: `C:\Users\ethan\Desktop\genesys2_camera_hdmi_20261019\saved_versions\raw_camera_capture_20261020\reports\raw_yuv_20261020_003241.limited.png`
5487 ordered packets; 76800 pixels; 153600 bytes; zero reported address errors;
zero transfer resynchronizations; camera frame 5.
The real preview was inspected and preserves the remaining colour problem.
Other conversion previews are diagnostic views, not applied fixes.
Passing capture metadata does not prove all camera byte values are correct.

## Board state at stopping point

The board currently runs raw_yuv_snapshot (SHA256 `53d749e45772c7dac18ef6603df51c7837d23a105c745658b487718cb4b2f9ba`), which uses the
same qualified receiver and live display path as the best saved version. Only
the independent diagnostic recording format differs. Final physical confirmation:
UART/J15 only, SW6/SW7 up, other switches down, BTNC pressed.
For normal live viewing SW7 can be put down; leave only SW6 up.
Keep PCLK on JA physical pin 1 and D6 on JB physical pin 8; preserve all other wiring.
USB serial was closed after transfer. Programming tools have exited. No further
hardware job was started. No QSPI flash write, driver change or Windows change.
Keep one board USB connected at a time for now. Main power off/PROG loses the
volatile configuration; use the saved best archive instructions to restore.

## Future work, only if explicitly resumed

Use this raw capture to distinguish camera byte/format issues from image
processing settings. Do not assume the cause or repeat the rejected bulk ISP
recipe. Preserve the working receiver and all original variants.
