## -----------------------------------------------------------------------------
## Genesys 2 (XC7K325T-2FFG900C) -- OV5640 on JA/JB, HDMI out.
## Trimmed from ~/fpga/digilent-xdc/Genesys-2-Master.xdc. Pins verified against
## that file, not typed from a datasheet.
## -----------------------------------------------------------------------------

## ---- 200 MHz system clock, LVDS, bank 33 ----
set_property -dict { PACKAGE_PIN AD12 IOSTANDARD LVDS } [get_ports { sysclk_p }]
set_property -dict { PACKAGE_PIN AD11 IOSTANDARD LVDS } [get_ports { sysclk_n }]
create_clock -period 5.000 -name sysclk [get_ports sysclk_p]

## ---- Camera: pin order is FIXED by the PCB's male headers ----
## The camera board plugs straight into the Pmods, so each position carries
## whatever that PCB wires there. This is the same order the Basys 3 XDC
## records. Positions are Pmod 1,2,3,4,7,8,9,10 -> index 0..7.
##
##   JA   D6  D8  XC  HS  |  D4  D2  PD  RT
##   JB   D7  D5  D3  SDA |  D9  PC  VS  SCL
set_property -dict { PACKAGE_PIN U27  IOSTANDARD LVCMOS33 } [get_ports { ja[0] }]  ;# PCLK input, dedicated P-side MRCC
set_property -dict { PACKAGE_PIN U28  IOSTANDARD LVCMOS33 } [get_ports { ja[1] }]  ;# D8     in
set_property -dict { PACKAGE_PIN T26  IOSTANDARD LVCMOS33 } [get_ports { ja[2] }]  ;# XCLK   out
set_property -dict { PACKAGE_PIN T27  IOSTANDARD LVCMOS33 } [get_ports { ja[3] }]  ;# HREF   in
set_property -dict { PACKAGE_PIN T22  IOSTANDARD LVCMOS33 } [get_ports { ja[4] }]  ;# D4     in
set_property -dict { PACKAGE_PIN T23  IOSTANDARD LVCMOS33 } [get_ports { ja[5] }]  ;# D2     in
set_property -dict { PACKAGE_PIN T20  IOSTANDARD LVCMOS33 } [get_ports { ja[6] }]  ;# PWDN   out
set_property -dict { PACKAGE_PIN T21  IOSTANDARD LVCMOS33 } [get_ports { ja[7] }]  ;# RESET  out

set_property -dict { PACKAGE_PIN V29  IOSTANDARD LVCMOS33 } [get_ports { jb[0] }]  ;# D7     in
set_property -dict { PACKAGE_PIN V30  IOSTANDARD LVCMOS33 } [get_ports { jb[1] }]  ;# D5     in
set_property -dict { PACKAGE_PIN V25  IOSTANDARD LVCMOS33 } [get_ports { jb[2] }]  ;# D3     in
set_property -dict { PACKAGE_PIN W26  IOSTANDARD LVCMOS33 } [get_ports { jb[3] }]  ;# SDA    io
set_property -dict { PACKAGE_PIN T25  IOSTANDARD LVCMOS33 } [get_ports { jb[4] }]  ;# D9     in
set_property -dict { PACKAGE_PIN U25  IOSTANDARD LVCMOS33 } [get_ports { jb[5] }]  ;# D6 input, swapped with PCLK
set_property -dict { PACKAGE_PIN U22  IOSTANDARD LVCMOS33 } [get_ports { jb[6] }]  ;# VSYNC  in
set_property -dict { PACKAGE_PIN U23  IOSTANDARD LVCMOS33 } [get_ports { jb[7] }]  ;# SCL    io

## NO create_clock ON PCLK. It lands on jb[5] = U25 = IO_L14N_T2_SRCC_14, the
## N side of a differential pair, and 7-series accepts a single-ended clock
## input only on the P side. CLOCK_DEDICATED_ROUTE FALSE does NOT override that
## -- that property governs routing, not the P/N rule, and Vivado rejects the
## N side at placement with [Place 30-876]. No Genesys 2 Pmod has a
## clock-capable P-side pin at connector position 8, so PCLK is sampled as DATA
## in the 200 MHz domain instead. See cam_capture.v.

## ---- HDMI out: raw TMDS from fabric, no transmitter chip ----
set_property -dict { PACKAGE_PIN AC20 IOSTANDARD TMDS_33 } [get_ports { hdmi_tx_p[0] }]
set_property -dict { PACKAGE_PIN AC21 IOSTANDARD TMDS_33 } [get_ports { hdmi_tx_n[0] }]
set_property -dict { PACKAGE_PIN AA22 IOSTANDARD TMDS_33 } [get_ports { hdmi_tx_p[1] }]
set_property -dict { PACKAGE_PIN AA23 IOSTANDARD TMDS_33 } [get_ports { hdmi_tx_n[1] }]
set_property -dict { PACKAGE_PIN AB24 IOSTANDARD TMDS_33 } [get_ports { hdmi_tx_p[2] }]
set_property -dict { PACKAGE_PIN AC25 IOSTANDARD TMDS_33 } [get_ports { hdmi_tx_n[2] }]
set_property -dict { PACKAGE_PIN AA20 IOSTANDARD TMDS_33 } [get_ports { hdmi_tx_clk_p }]
set_property -dict { PACKAGE_PIN AB20 IOSTANDARD TMDS_33 } [get_ports { hdmi_tx_clk_n }]

## ---- UART to the USB bridge ----
## Y23 is FPGA TX, Y20 is FPGA RX, confirmed in Digilent user-demo XDC.
## Do not swap these outputs experimentally: Y20 is driven by the USB bridge.
set_property -dict { PACKAGE_PIN Y23  IOSTANDARD LVCMOS33 } [get_ports { uart_rx_out }]

## ---- switches, button, LEDs ----
set_property -dict { PACKAGE_PIN G19  IOSTANDARD LVCMOS12 } [get_ports { sw[0] }]
set_property -dict { PACKAGE_PIN G25  IOSTANDARD LVCMOS12 } [get_ports { sw[1] }]
set_property -dict { PACKAGE_PIN H24  IOSTANDARD LVCMOS12 } [get_ports { sw[2] }]
set_property -dict { PACKAGE_PIN K19  IOSTANDARD LVCMOS12 } [get_ports { sw[3] }]
set_property -dict { PACKAGE_PIN N19  IOSTANDARD LVCMOS12 } [get_ports { sw[4] }]
set_property -dict { PACKAGE_PIN P19  IOSTANDARD LVCMOS12 } [get_ports { sw[5] }]
set_property -dict { PACKAGE_PIN P26  IOSTANDARD LVCMOS33 } [get_ports { sw[6] }]
set_property -dict { PACKAGE_PIN P27  IOSTANDARD LVCMOS33 } [get_ports { sw[7] }]
set_property -dict { PACKAGE_PIN E18  IOSTANDARD LVCMOS12 } [get_ports { btnc }]

set_property -dict { PACKAGE_PIN T28  IOSTANDARD LVCMOS33 } [get_ports { led[0] }]
set_property -dict { PACKAGE_PIN V19  IOSTANDARD LVCMOS33 } [get_ports { led[1] }]
set_property -dict { PACKAGE_PIN U30  IOSTANDARD LVCMOS33 } [get_ports { led[2] }]
set_property -dict { PACKAGE_PIN U29  IOSTANDARD LVCMOS33 } [get_ports { led[3] }]
set_property -dict { PACKAGE_PIN V20  IOSTANDARD LVCMOS33 } [get_ports { led[4] }]
set_property -dict { PACKAGE_PIN V26  IOSTANDARD LVCMOS33 } [get_ports { led[5] }]
set_property -dict { PACKAGE_PIN W24  IOSTANDARD LVCMOS33 } [get_ports { led[6] }]
set_property -dict { PACKAGE_PIN W23  IOSTANDARD LVCMOS33 } [get_ports { led[7] }]

## ---- asynchronous inputs ----
set_false_path -from [get_ports { sw[*] }]
set_false_path -from [get_ports { btnc }]

## The entire DVP is asynchronous data into the 200 MHz domain, PCLK included.
## Every one of these goes through a synchroniser in cam_capture; timing them
## as if they were source-synchronous would be meaningless.

## Capture and display are treated as separate clock domains: the frame buffer is a
## dual-clock BRAM with no handshake, and the overlay telemetry crosses through
## 2-flop synchronisers sampled at ~60 Hz. A torn read self-corrects.
set_clock_groups -asynchronous \
    -group [get_clocks -of_objects [get_pins clk_gen_i/bufg_200/O]] \
    -group [get_clocks -of_objects [get_pins clk_gen_i/bufg_pix/O]]

## Bitstream: the Genesys 2 boots from QSPI, so leave the config pins alone
## unless you intend to write flash.
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]

## SCCB read data is sampled after a settling interval.
set_false_path -from [get_ports {jb[3]}]

# DVP sampled as asynchronous data into matched synchronizer pipelines.
# No camera pin is used as a fabric clock in this variant.
set_false_path -from [get_ports {ja[0] ja[1] ja[3] ja[4] ja[5] jb[0] jb[1] jb[2] jb[4] jb[5] jb[6]}]
