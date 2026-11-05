# Genesys2 constraints for cnn_subsystem_top -- Phase 2 Task 5.
#
# DDR3 pin/timing constraints are NOT here: MIG's own generated output-
# product XDC (board-preset-derived in Task 1 via CONFIG.BOARD_MIG_PARAM)
# supplies those automatically once the BD is a project source and
# generate_target has run -- standard Vivado BD-IP constraint flow, no
# manual add_files needed for it. This file only covers the signals that
# aren't MIG's: the system clock, the board reset button, and UART.
#
# Pin/IOSTANDARD values pulled directly from
# ~/fpga/vivado-boards/new/board_files/genesys2/H/{board,part0_pins}.xml
# (components: sys_diff_clock, reset, usb_uart) -- not guessed, and cross-
# checked against ~/fpga/genesys2-ov5640-hdmi/constraints/genesys2.xdc,
# which already runs on this same board.

## System differential clock -- 200MHz, 3.3V LVDS (sys_diff_clock component).
## No create_clock here (code review, 2026-10-28): MIG's own generated XDC
## already constrains this same source pin at 4.999ns, and the create_clock
## this file used to have (5.000ns) silently won and overrode it --
## CRITICAL WARNING: [Constraints 18-1056] Clock 'sys_clk' completely
## overrides clock 'sys_clk_p' -- flagged by the tool, never reported.
## Numerically irrelevant (0.02% period difference) but a user XDC
## overriding IP-generated timing is fragile; let MIG's XDC be the sole
## source of truth for this clock.
set_property -dict { PACKAGE_PIN AD12 IOSTANDARD LVDS } [get_ports { sys_clk_p }]
set_property -dict { PACKAGE_PIN AD11 IOSTANDARD LVDS } [get_ports { sys_clk_n }]

## Board reset button (board.xml component "reset", part0_pins.xml loc R19).
## ASSUMPTION, not yet hardware-verified: Digilent's dedicated memory-
## controller reset button on this board family is active-low (matches
## mig.prj's SysResetPolarity ACTIVE LOW and this design's ext_reset_in/
## sys_rst_0 POLARITY ACTIVE_LOW with no inversion needed) -- confirm
## against the Genesys2 reference manual before relying on this in an
## actual board bring-up; this phase only needs synthesis/timing, not a
## programmed bitstream.
set_property -dict { PACKAGE_PIN R19  IOSTANDARD LVCMOS33 } [get_ports { sys_rst }]

## USB-UART bridge, FPGA transmit pin (board.xml component "usb_uart",
## logical port TxD -> physical pin usb_uart_txd, part0_pins.xml loc Y23).
## Matches genesys2-ov5640-hdmi's uart_rx_out at the same pin/standard.
set_property -dict { PACKAGE_PIN Y23  IOSTANDARD LVCMOS33 } [get_ports { uart_tx_pin }]
