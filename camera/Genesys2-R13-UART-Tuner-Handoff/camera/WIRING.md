# Actual wiring used by these saved bitstreams

Read this before programming. PCLK was moved from JB8 to JA1 and D6 from JA1 to JB8. Older comments in archived files may still describe the original mapping. The mapping below and actual top-level signal assignments take precedence over those old comments. Do not wire from cable colour or a rotated photograph.

| Header physical pin | HDL port | FPGA package pin | Camera signal | Direction at FPGA |
|---|---|---|---|---|
| JA1 | ja[0] | U27 | PCLK | Input |
| JA2 | ja[1] | U28 | D8 | Input |
| JA3 | ja[2] | T26 | XCLK | Output |
| JA4 | ja[3] | T27 | HS / HREF | Input |
| JA7 | ja[4] | T22 | D4 | Input |
| JA8 | ja[5] | T23 | D2 | Input |
| JA9 | ja[6] | T20 | PWDN | Output |
| JA10 | ja[7] | T21 | RESET | Output |
| JB1 | jb[0] | V29 | D7 | Input |
| JB2 | jb[1] | V30 | D5 | Input |
| JB3 | jb[2] | V25 | D3 | Input |
| JB4 | jb[3] | W26 | SDA | Bidirectional |
| JB7 | jb[4] | T25 | D9 | Input |
| JB8 | jb[5] | U25 | D6 | Input |
| JB9 | jb[6] | U22 | VS / VSYNC | Input |
| JB10 | jb[7] | U23 | SCL | Bidirectional |

On each 12-pin Pmod connector, pins 5 and 11 are GND; pins 6 and 12 are 3.3 V. Verify connector pin-1 orientation against the board documentation before connecting. This is the module whose 8-bit data bus is labelled D2 through D9, not a module labelled D0 through D7. Follow the labels on your module. Camera 3V supply connects to 3.3 V, with shared ground; do not connect it to 5 V. Power OFF before moving wires.

Ethan measured 3.31 V at the camera and used approximately four-inch jumper wires. The same camera and wires produced a clean image with an ESP board. This does not prove signal timing/levels are correct at the FPGA. HDMI display connects to HDMI OUT/TX. J17 is USB-JTAG; J15 is USB-UART. The source's uart_rx_out signal is the FPGA's transmitted diagnostics toward the board USB-UART chip, despite its confusing name.
