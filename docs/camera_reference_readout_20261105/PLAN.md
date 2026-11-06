# R9: reference-derived sensor readout comparison

## Evidence and question

Ethan confirmed wrong colours on physical objects under room lighting, excluding
screens and ceiling lights from that comparison: blue becomes green, green grey,
yellow pink, white pale pink, pink orange, and bright blue nearly off-white.
This rules out photographing an angled LCD as the sole explanation. It does not
identify the faulty register or establish an electrical fault.

The r8 RGB565 transport did not visibly improve the original YUYV picture.
Disabling the colour matrix made the live scene mostly green/purple. Published
Espressif saturation-0 coefficients also gave no visible improvement. Both matrix
trials were restored and verified; automatic white balance was restored too.
No gamma adjustment was applied. Do not repeat those rejected recipes blindly.

The next hypothesis is an inconsistent sensor sampling/readout configuration.
Test one alternative *mode family*, not an isolated cosmetic saturation tweak.
This trial deliberately changes multiple coupled mode registers; it cannot
identify which individual register matters if the picture changes.

## Candidate versus RGB565 r8

Build with RGB565=1 and REFERENCE_READOUT=1. The defaults retain r8 behaviour.

| Register | R8 startup | R9 startup | Purpose |
|---|---:|---:|---|
| 3814, 3815 | 71, 71 | 31, 31 | Reference low-resolution sampling increments |
| 380E, 380F | 02, 08 | 03, D8 | Frame length 520 -> 984 lines |
| 3618 | reset default | 00 | Mode-dependent sensor control |
| 3612 | reset default | 29 | Mode-dependent sensor control |
| 3708 | reset default | 64 | Mode-dependent sensor control |
| 3709 | reset default | 52 | Mode-dependent sensor control |
| 370C | 02 | 03 | Mode-dependent sensor control |
| 4001 | reset default | 02 | Black-reference start line |
| 4004 | reset default | 02 | Black-reference line count |

All added writes finish before 3008=02 starts streaming. Keep 320 x 240 output,
crop/orientation, HTS 1896, PLL/dividers, pads, pulse-qualified receiver, pinout,
RGB565 byte order, HDMI, exposure 128 lines and analogue gain 1x unchanged.
Factory colour matrix/gamma and automatic white balance remain the starting point.
The new frame length is necessary for the larger sampled array; output height
alone does not determine readout time. This candidate may run more slowly.
It is not a full port or reproduction of the Linux driver.

## Primary references and limits

- Linux OV5640 driver, `ov5640_setting_low_res`: increments 31/31; mode controls
  3618/3612/3708/3709/370C and black-reference 4001/4004.
  https://raw.githubusercontent.com/torvalds/linux/master/drivers/media/i2c/ov5640.c
- The driver's QVGA **DVP** timing has height 240, vertical blanking 744 and
  horizontal total 1896: 240 + 744 = 984. Registers 3A02/03 are exposure-limit
  registers, not the frame-length registers; do not confuse them with 380E/F.
- Espressif OV5640 image-options code also pairs binned sampling with 31/31,
  but uses some other settings that are not transplanted in this candidate.
  https://raw.githubusercontent.com/espressif/esp32-camera/master/sensors/ov5640.c
- Manufacturer OV5640 specification: 3814/15 sampling increments; 380E/F frame
  length; 4001/4004 black-level-reference configuration.

Only register facts are adapted. No Linux C driver code is copied. Linux source
is GPL-2.0-or-later; Espressif source retains its upstream MIT/OpenMV notice.
Source download hashes and retrieval metadata are in SOURCES.json. Full reference
downloads are kept in ignored local_results, outside the shipped source.

## Verification and physical comparison

1. Check default-profile initialization and UART-host controls still pass.
2. Simulate actual top-level RGB565 capture for both profiles, including qualified
   short glitches, packed pixels and profile writes before streaming.
3. Build a frozen r9 snapshot with the existing 1.5 GiB memory guard and one
   compiler. Record routed timing, source hashes and bitstream hash.
4. Ethan manually loads the candidate through JTAG with wiring unchanged, only
   SW6 up, presses BTNC once, then waits 10 seconds. Compare physical blue,
   green, yellow and white objects in the same lighting and the bright-light fault.
5. If useful, return to UART for actual mode-register readback, frame geometry,
   frame rate and a raw capture. Simulation cannot predict sensor colour or FPS.
6. Keep the preferred original and r8 candidates. Do not promote r9 from build
   success or clean synthetic bars. If worse, restore a preserved bitstream.

Snapshot before source changes:
`local_artifacts/r8_before_reference_readout_20261105`.
No clock/pad/geometry changes through the UART allowlist; no board programming,
flash writes, Windows changes or remote Git push are performed by this build.
