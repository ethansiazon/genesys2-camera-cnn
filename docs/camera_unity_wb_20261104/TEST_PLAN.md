# Manual white-balance isolation

Reference: physically tested/read-back r3. It uses the preferred archive's
sensor writes. R5 adds seven writes only: 3406=01 (manual), then R/G/B gain
pairs 3400..3405=04,00 each. Exposure stays 128 lines and sensor gain 1x.
R5 preserves r3 receiver, clocks, conversion, raw capture and readback logic.
No rejected analog-startup settings are added.

This is an equal-gain diagnostic control, not a calibrated white-balance
preset. Unequal automatic gains can be correct for the illumination. A
darkened or differently tinted picture is possible even though exposure is
unchanged. Do not promise a colour fix or brightness improvement.

User has confirmed JTAG only connected, only SW6 up. Before programming again
confirm wiring has remained PCLK JA1 and D6 JB8 if there has been any rewiring.

1. Manually load builds/unity_wb128_20261104_r5/camera_hdmi.bit in Hardware Manager.
2. Only SW6 up; BTNC; wait five seconds. Compare the SAME scene and lighting.
3. Record ordinary white/pale surfaces and bright-light green/dark/purple
   artefacts separately. Do not treat a less visible artefact caused solely by
   a darker image as a confirmed colour improvement.
4. If useful, pulse SW0 to refresh reads, then connect UART only with main
   power maintained. Verify 3406=01 and 3400..3405=04/00/04/00/04/00, zero NACKs,
   and unchanged exposure registers. This remains pending until measured.
5. For paired raw capture, leave camera/objects fixed, raise SW7 without BTNC.
   Use this working copy's RAW YUYV decoder.

Fallback remains camera/versions/last_exposure_test/camera_hdmi.bit. No QSPI
writes, Windows changes, automated board programming or remote Git push.
