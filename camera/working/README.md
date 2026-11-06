# Live camera-control diagnostic (r6)

Startup sensor writes exactly match the preferred last_exposure_test archive:
128 exposure lines, 1x sensor gain, automatic white balance. No rejected analog
or manual-unity settings are applied at startup. Receiver and RGB conversion
remain unchanged. UART RX is added on Y20 (FPGA INPUT), TX remains Y23.
Commands use the existing camera SCCB master only after init/refresh releases it.

Normal view only SW6 up; BTNC restores preferred startup settings. SW0 refreshes
diagnostic reads. SW7 raw snapshots still work; host commands are blocked during
recording and responses wait until recording ends. Control readback is authoritative;
the ordinary 48-register telemetry snapshot is latched and can be refreshed via SW0.

This is a test interface, not a demonstrated image fix. Physical validation pending.
Preserved original .bit here is OLD; build output will be in
builds/live_control128_20261105_r6/camera_hdmi.bit. Preserve archives and do not
push or program automatically. PCLK JA1 and D6 JB8 remain unchanged.
