# Offline camera colour trials, r8

User request November5: board unavailable (teammates testing); prepare revisions
for dark/washed colours and bright green/dark light artefacts. No serial-port,
JTAG, board programming, OS/driver or actuator operations are included here.
Remote fetched: origin/main still1d215ab, no new teammate changes to merge.

Parent workingr6; original last_exposure_test and earlier trials immutable.
Local backup: local_artifacts/r6_before_format_trials_20261105. Do not silently
use r7 drive-strength change: its image was clarified as similar, not improved.
Entry3016=C3 and3020=21 remain historical baseline mismatches for controlled
format isolation; they are not endorsed as correct reference translations.

Two separate builds from one parameterized source, with identical pins/clocks,
320x240 geometry, exposure128/gain1x, automaticWB and qualified sampler:
- yuyv control: RGB565=0,4300=30,501F=00, existing conversion.
- rgb565 diagnostic: RGB565=1,4300=61,501F=01, high-byte-first RGB565
  expanded directly toRGB888. No FPGA YUV matrix. Same framebuffer write timing.
  Capture metadata magicR565 vsYUV0 prevents silent wrong-format decoding.

DefaultRGB565=0 preserves YUV behaviour. No format switching mid-frame.
SW6 remains up to invert HREF as physically tested. SW2/SW3/SW4 only affect
YUV interpretation; they are ignored forRGB. SW1 still requests camera bars,
SW5 HDMI-only bars,SW7 raw snapshot,SW0 overlay/readback. Keep unused switches down.
RGB telemetry brightness fields use green as a proxy; not sensorY luminance.

Ten runtime trials, default script actionList and Plan never opens hardware.
Exposure128/192/256 follows Espressif3500->3501->3502 at manual gain1x, with
VTS margin check. WB must first settle and be held for paired tests. Saturation
0/1/2 and gamma0 are published reference recipes, not tuned/calibrated to this
module. OfficeWB is optional, not recommended from prior near-neutral paper.
Every apply checks sensorID and format, reads prior values, verifies writes,
saves rollback, stops on failure; no automatic trial loop or port retries.
Existing firmware allowlist unchanged: no clock/pad/format runtime writes.
Do not combine variable families until single trials establish effects.

Tests completed before synthesis: seven relevantYUV/RGB/capture/UART fixtures;
additional actual top RGB test with5nsPCLK/HREF/VSYNC excursions; exact known
primaries and640framebuffer pixels; metadata;76800offline RGB pixels and legacy
YUV byte preservation; wrong/unknownformat refusal; mocked host guards.
Tests substitute sensor/clock/HDMI models: no physical-colour validation implied.

Primary sources: Espressif esp32-camera sensors/ov5640.c set_pixformat,
set_saturation,set_aec_value,set_wb_mode and private_include/ov5640_settings.h
sensor_fmt_rgb565,sensor_saturation_levels,sensor_regs_gamma0. Exact downloaded
source hashes recorded in camera/working/scripts/camera_trials.json. OV5640v2.03
PDFp87 table6-5 explicitly specifies4300=61 Rhigh/G/B packing. MIT6205 supports
two-byte RGB565 reconstruction, but its complete720pROM is not transplanted.

https://github.com/espressif/esp32-camera/blob/master/sensors/ov5640.c
https://github.com/espressif/esp32-camera/blob/master/sensors/private_include/ov5640_settings.h
https://fpga.mit.edu/6205/F24/assignments/camera/pixel_reconstruct
Local manufacturerPDF: C:/Users/ethan/Downloads/OV5640_datasheet.pdf

Next physical work: compare same scene, normal white paper and coloured objects,
then a separate ceiling-light shot; allow10secondsWB settle. TestYUV control
first, thenRGB. Record bars and live result separately. A clean RGB image only
narrows the YUVpath; persistence does not prove sensor damage. Preserve original.
Build/timing results are separate from subjective image-quality acceptance.
