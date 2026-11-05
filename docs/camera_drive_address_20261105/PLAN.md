# R7 controlled drive-address correction

Parent: r6 live-control source at2818a31, tracked state4387210.
Preserved local source: local_artifacts/live_control_r6_before_drive_address_fix.
Favourite archived bitstream camera/versions/last_exposure_test is untouched.

Change only startup entry6 address3016 ->302C; retainC3 as in Espressif and MIT.
Do not alter entry7(3020=21), final4740=22, ISP, exposure128/gain1x,
clock/window, qualified receiver, converter or UART allowlist.
This corrects a verified reference mismatch. 4x drive is not inherently better;
compare actual camera bars and live images before adopting. Removing the old
3016 write is part of this one-address correction, so improvement alone would
not isolate drive strength from the previous pad-enable side effect.

Physical pre-read: ID5640,3016=03,3020=21,302C=02,4740=22.
Current r6 runtime exposure160 and heldWB3406=01; the new build resets startup
back to preferred exposure128 and automaticWB. Compare with preferred original
under matching switches/scene; do not compare brightness directly to volatile160.

Verify initialization/host arbitration and qualified top-level capture. Build
one separate frozen snapshot with memory guard. User loads manually only after
JTAG confirmation. No programming, Git push, pad writes or OS changes here.
After loading: onlySW6up +BTNC. Record bar/live observation, then actual302C
readback through UART. A good simulation/timing result is not image validation.
