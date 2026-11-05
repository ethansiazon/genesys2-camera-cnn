# Standalone CNN+DDR3/AXI timing subsystem block design -- Phase 2 (see
# docs/superpowers/plans/2026-10-28-phase2-ddr-axi-timing.md).
#
# Clock-domain note (Global Constraints / Review Focus item 5): ap_clk on
# cnn_engine_0 is tied directly to MIG's ui_clk, and ap_rst_n to the
# ui_clk-domain peripheral_aresetn below. This avoids a CDC in this
# standalone phase. Camera integration (handoff phase 3+) runs the pixel
# pipeline on a different clock and will need a real CDC at that boundary --
# this tie does not survive past this phase unmodified.
set root_dir [file dirname [file dirname [file normalize [info script]]]]

create_bd_design cv_subsystem

# ---------------------------------------------------------------------------
# MIG (Task 1)
# ---------------------------------------------------------------------------
create_bd_cell -type ip -vlnv xilinx.com:ip:mig_7series:4.2 mig_7series_0
set_property CONFIG.BOARD_MIG_PARAM {ddr3_sdram} [get_bd_cells mig_7series_0]

# Simulation-only: bypass MIG's full calibration sequence for a much shorter
# sim. Gated on an env var (not a permanent property) so the exact same
# script produces the real, full-calibration hardware build by default --
# Task 5's build must NEVER run with this set. Set PHASE2_SIM_BYPASS_CAL=1
# only when invoking this script to build the Task 4 simulation snapshot.
if {[info exists ::env(PHASE2_SIM_BYPASS_CAL)] && $::env(PHASE2_SIM_BYPASS_CAL) eq "1"} {
    set_property CONFIG.SIM_BYPASS_INIT_CAL {FAST} [get_bd_cells mig_7series_0]
    puts "SIM_BYPASS_INIT_CAL=FAST (simulation-only, PHASE2_SIM_BYPASS_CAL=1)"
}

create_bd_intf_port -mode Slave -vlnv xilinx.com:interface:diff_clock_rtl:1.0 sys_clk
set_property CONFIG.FREQ_HZ 200000000 [get_bd_intf_ports sys_clk]
connect_bd_intf_net [get_bd_intf_ports sys_clk] [get_bd_intf_pins mig_7series_0/SYS_CLK]

make_bd_intf_pins_external [get_bd_intf_pins mig_7series_0/DDR3]
make_bd_pins_external [get_bd_pins mig_7series_0/sys_rst]

# ---------------------------------------------------------------------------
# Reset tree for the ui_clk domain (Task 2) -- replaces Task 1's raw
# aresetn stub. Standard Processor System Reset pattern: gated by MIG's
# clock-lock signal, driven by an external reset-in that Task 4's top-level
# wrapper will source from a real board input.
# ---------------------------------------------------------------------------
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 proc_sys_reset_0
create_bd_port -dir I -type rst ext_reset_in
set_property CONFIG.POLARITY {ACTIVE_LOW} [get_bd_ports ext_reset_in]
connect_bd_net [get_bd_ports ext_reset_in] [get_bd_pins proc_sys_reset_0/ext_reset_in]
connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins proc_sys_reset_0/slowest_sync_clk]
connect_bd_net [get_bd_pins mig_7series_0/mmcm_locked] [get_bd_pins proc_sys_reset_0/dcm_locked]
# Also gate on MIG's own ui_clk-domain reset (code review, 2026-10-28):
# mmcm_locked alone can deassert before MIG's UI-side reset sequencing is
# actually done -- harmless today only because every AXI master in this
# design waits on init_calib_complete before issuing traffic, but a latent
# trap for Phase 3 once something doesn't. aux_reset_in defaults to
# active-high (CONFIG.C_AUX_RESET_HIGH=1), matching ui_clk_sync_rst's own
# polarity with no inversion needed -- confirmed, not assumed.
connect_bd_net [get_bd_pins mig_7series_0/ui_clk_sync_rst] [get_bd_pins proc_sys_reset_0/aux_reset_in]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins mig_7series_0/aresetn]

# ---------------------------------------------------------------------------
# CNN core (regenerated, byte-identical to Phase 1's validated RTL sim) as
# an RTL-module BD cell.
#
# TIMING FIX (2026-10-29, closing PHASE2_STATUS.md's open WNS=-1.954ns
# finding): the real post-route critical path is entirely inside
# cnn_engine_0's own HLS-generated convolve logic
# (grp_convolve_fu_357/.../shl_ln24_5_reg -> .../value_84_reg, 33 logic
# levels, 5.994ns required vs 4.444ns available at ui_clk's 225.02MHz) --
# NOT anything in this phase's own integration RTL. cnn_engine.v is a
# frozen, Phase-1-validated artifact (docs/PHASE2_LOG.md Task 2) that this
# project does not edit, and it was never designed to run this fast: it was
# HLS-synthesized for a 100MHz target (rtl/cnn_core/cnn_engine.v:10,
# HLS_INPUT_CLOCK=10.000000) and Phase 1's own out-of-context synthesis
# measured 128.12MHz Fmax (PHASE1_STATUS.md) -- both comfortably below
# ui_clk's 225.02MHz, which this design simply tied it to directly as a
# known, documented simplification ("this tie does not survive past this
# phase unmodified", see this file's header comment, now superseded by the
# fix below). Fix: give cnn_engine_0 its own clock domain at the core's own
# validated 100MHz design target (real margin under the measured 128.12MHz
# Fmax, not pushed to that edge) via a dedicated clk_wiz deriving from
# ui_clk, with axi_clock_converter CDC bridges on all three of its AXI
# interfaces back to the ui_clk-domain smartconnect. This changes nothing
# about cnn_engine's own internal logic or netlist -- it only changes what
# clock drives it.
# ---------------------------------------------------------------------------
add_files -norecurse [glob [file join $root_dir rtl cnn_core *.v]]
update_compile_order -fileset sources_1
create_bd_cell -type module -reference cnn_engine cnn_engine_0

# --- Decoupled clocks (2026-10-29 latency experiment): cnn_engine_0 and
# decode_work_heads_0 used to share clk_out1 at one frequency. Every timing
# failure this session (200/150/135MHz attempts) was caused by paths inside
# decode_work_heads_0's own arithmetic (width_q(), transformed()), never
# cnn_engine -- meaning the decoder was holding cnn_engine's achievable
# frequency down to whatever the decoder itself could tolerate. Splitting
# them lets each be pushed to its own real ceiling independently.
# clk_out1 -> cnn_engine_0 (the one we want to push as high as closes
# cleanly, CNN_CLK_MHZ below). clk_out2 -> decode_work_heads_0, deliberately
# kept at a conservative, easily-closing frequency: its own real compute is
# fast (observed ~12ms over JTAG was mostly poll overhead, not real
# compute), it does not need to go fast, only to not be the bottleneck.
# CONFIG.PRIM_SOURCE=No_buffer because the input here is an internal fabric
# clock (ui_clk), not a top-level differential/single-ended board pin --
# clk_wiz's GUI default assumes the latter and would otherwise try to
# instantiate an IBUFG on a non-port net.
if {![info exists ::env(CNN_CLK_MHZ)]} { set ::env(CNN_CLK_MHZ) 140.000 }
create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clk_wiz_0
set_property -dict [list \
    CONFIG.PRIM_SOURCE {No_buffer} \
    CONFIG.PRIM_IN_FREQ {225.022502} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $::env(CNN_CLK_MHZ) \
    CONFIG.CLKOUT2_USED {true} \
    CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {100.000} \
    CONFIG.USE_LOCKED {true} \
    CONFIG.USE_RESET {true} \
    CONFIG.RESET_TYPE {ACTIVE_HIGH} \
] [get_bd_cells clk_wiz_0]
connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins clk_wiz_0/clk_in1]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_reset] [get_bd_pins clk_wiz_0/reset]

# Matching reset tree for the cnn_engine_0 domain (clk_out1), same
# proc_sys_reset pattern as proc_sys_reset_0 (Task 2) -- gated on
# clk_wiz_0's own lock signal, same board-level ext_reset_in.
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 proc_sys_reset_1
connect_bd_net [get_bd_ports ext_reset_in] [get_bd_pins proc_sys_reset_1/ext_reset_in]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] [get_bd_pins proc_sys_reset_1/slowest_sync_clk]
connect_bd_net [get_bd_pins clk_wiz_0/locked] [get_bd_pins proc_sys_reset_1/dcm_locked]

# Second reset tree for decode_work_heads_0's own domain (clk_out2) -- both
# outputs share clk_wiz_0's single MMCM, so they lock together; still a
# separate proc_sys_reset instance per domain, same as every other clock
# boundary in this design.
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 proc_sys_reset_2
connect_bd_net [get_bd_ports ext_reset_in] [get_bd_pins proc_sys_reset_2/ext_reset_in]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out2] [get_bd_pins proc_sys_reset_2/slowest_sync_clk]
connect_bd_net [get_bd_pins clk_wiz_0/locked] [get_bd_pins proc_sys_reset_2/dcm_locked]

connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] [get_bd_pins cnn_engine_0/ap_clk]
connect_bd_net [get_bd_pins proc_sys_reset_1/peripheral_aresetn] [get_bd_pins cnn_engine_0/ap_rst_n]
# A plain RTL-module BD cell (not packaged IP) carries no clock/frequency
# metadata for its AXI interfaces, so the auto-inferred bus interfaces default
# to a guessed FREQ_HZ that mismatches the connected clock's real rate.
# Associate ap_clk with all three AXI interfaces explicitly so FREQ_HZ
# propagates from the actual connected clock (now clk_wiz_0's 100MHz)
# instead.
set_property CONFIG.ASSOCIATED_BUSIF {m_axi_feature_ddr:m_axi_coefficient_ddr:s_axi_control} [get_bd_pins cnn_engine_0/ap_clk]

# --- CDC bridges: cnn_engine_0's three AXI interfaces (cnn_clk, 100MHz)
# cross into the ui_clk (225.02MHz) domain everything else in this design
# runs on. axi_clock_converter's S_AXI is always the slave side (where the
# upstream master plugs in) and M_AXI the master side (driving the next
# slave) regardless of which physical direction data flows -- so the two
# data masters (feature/coefficient) plug into S_AXI on the cnn_clk side
# and come out M_AXI on the ui_clk side toward smartconnect; the control
# path (smartconnect driving INTO cnn_engine's AXI-Lite slave) is the
# mirror image.
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_clock_converter:2.1 axi_clock_converter_0
set_property CONFIG.PROTOCOL {AXI4} [get_bd_cells axi_clock_converter_0]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] [get_bd_pins axi_clock_converter_0/s_axi_aclk]
connect_bd_net [get_bd_pins proc_sys_reset_1/peripheral_aresetn] [get_bd_pins axi_clock_converter_0/s_axi_aresetn]
connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins axi_clock_converter_0/m_axi_aclk]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins axi_clock_converter_0/m_axi_aresetn]
connect_bd_intf_net [get_bd_intf_pins cnn_engine_0/m_axi_feature_ddr] [get_bd_intf_pins axi_clock_converter_0/S_AXI]

create_bd_cell -type ip -vlnv xilinx.com:ip:axi_clock_converter:2.1 axi_clock_converter_1
set_property CONFIG.PROTOCOL {AXI4} [get_bd_cells axi_clock_converter_1]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] [get_bd_pins axi_clock_converter_1/s_axi_aclk]
connect_bd_net [get_bd_pins proc_sys_reset_1/peripheral_aresetn] [get_bd_pins axi_clock_converter_1/s_axi_aresetn]
connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins axi_clock_converter_1/m_axi_aclk]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins axi_clock_converter_1/m_axi_aresetn]
connect_bd_intf_net [get_bd_intf_pins cnn_engine_0/m_axi_coefficient_ddr] [get_bd_intf_pins axi_clock_converter_1/S_AXI]

create_bd_cell -type ip -vlnv xilinx.com:ip:axi_clock_converter:2.1 axi_clock_converter_2
set_property CONFIG.PROTOCOL {AXI4LITE} [get_bd_cells axi_clock_converter_2]
connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins axi_clock_converter_2/s_axi_aclk]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins axi_clock_converter_2/s_axi_aresetn]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] [get_bd_pins axi_clock_converter_2/m_axi_aclk]
connect_bd_net [get_bd_pins proc_sys_reset_1/peripheral_aresetn] [get_bd_pins axi_clock_converter_2/m_axi_aresetn]
connect_bd_intf_net [get_bd_intf_pins axi_clock_converter_2/M_AXI] [get_bd_intf_pins cnn_engine_0/s_axi_control]

# ---------------------------------------------------------------------------
# jtag_axi debug master (kept permanently -- SESSION_HANDOFF_20261028.md's
# "keep this permanently as a debug tool, not throwaway").
# ---------------------------------------------------------------------------
create_bd_cell -type ip -vlnv xilinx.com:ip:jtag_axi:1.2 jtag_axi_0
connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins jtag_axi_0/aclk]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins jtag_axi_0/aresetn]

# ---------------------------------------------------------------------------
# smartconnect: a 3-slave x 2-master crossbar. Slaves are cnn_engine_0's two
# AXI-M ports (feature 256b, coefficient 128b -- width conversion against
# MIG's native width is SmartConnect's job) plus jtag_axi_0. Masters are
# MIG's AXI slave (M00, reachable from all three slaves -- this is the "1
# master AXI toward MIG" the plan names) and cnn_engine_0's AXI-Lite control
# port (M01, address-routed so only jtag_axi's traffic ever reaches it --
# cnn_engine's own two data masters have no reason to address their own
# control port). This gives jtag_axi_0 both of the debug capabilities the
# handoff doc calls for -- a DDR backdoor AND control-register access --
# from its single physical AXI master port, through one crossbar instead of
# a second dedicated interconnect.
# ---------------------------------------------------------------------------
create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 smartconnect_0
set_property CONFIG.NUM_SI {3} [get_bd_cells smartconnect_0]
set_property CONFIG.NUM_MI {2} [get_bd_cells smartconnect_0]
connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins smartconnect_0/aclk]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins smartconnect_0/aresetn]
connect_bd_intf_net [get_bd_intf_pins axi_clock_converter_0/M_AXI] [get_bd_intf_pins smartconnect_0/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_clock_converter_1/M_AXI] [get_bd_intf_pins smartconnect_0/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins jtag_axi_0/M_AXI] [get_bd_intf_pins smartconnect_0/S02_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M00_AXI] [get_bd_intf_pins mig_7series_0/S_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M01_AXI] [get_bd_intf_pins axi_clock_converter_2/S_AXI]

# ---------------------------------------------------------------------------
# Coefficient BRAM staging + copy FSM (Task 3, standalone-simulated already)
# as the smartconnect's fourth slave. start is tied directly to
# init_calib_complete as a level (not edge-detected): copy_fsm only ever
# leaves S_IDLE once and never returns there while start stays high (see
# rtl/copy_fsm.v's S_DONE state), so a level trigger gives the identical
# one-shot-after-calibration behavior the plan's "rising edge" called for,
# without a dedicated edge-detector module.
# ---------------------------------------------------------------------------
add_files -norecurse [list \
    [file join $root_dir rtl copy_fsm.v] \
    [file join $root_dir rtl coeff_bram_stage.v] \
]
update_compile_order -fileset sources_1
create_bd_cell -type module -reference coeff_bram_stage coeff_bram_stage_0
# CRITICAL FIX (code review, 2026-10-28): the Verilog default
# HEXFILE="rtl/coefficients.hex" is relative, and each per-IP out-of-context
# synthesis run's CWD is deep under vivado/.../cv_subsystem_coeff_bram_stage_0_0_synth_1/,
# where that relative path does not exist. synth_design treated the missing
# file as a non-fatal CRITICAL WARNING ([Synth 8-4445]) and silently
# dissolved the entire 41,600x128 array into undriven registers (0 BRAM,
# 0 LUT in that IP's utilization row) -- found only by reading the per-IP
# runme.log, not build.log, which never saw it. An absolute path works from
# every CWD (project root for simulation, any vivado/*.runs/*/ for OOC
# synthesis) and needs no per-context workaround.
set_property CONFIG.HEXFILE [file join $root_dir rtl coefficients.hex] [get_bd_cells coeff_bram_stage_0]
create_bd_cell -type module -reference copy_fsm copy_fsm_0
# Simulation-only: cut the coefficient count from the real 41,600 down to
# 256 for Task 4's testbench. Rationale: Task 3 already proved all 41,600
# words transfer correctly against a lightweight behavioral AXI slave
# (errors == 0, word-for-word). Task 4's job is to prove the real,
# MIG-backed system's calib -> copy -> ap_start -> ap_done handshake chain
# actually completes -- a full DDR3 behavioral model is realistic-timing,
# not fast, and 41,600 individual AXI transactions through it would make
# this simulation impractically slow in wall-clock time without adding any
# real verification value Task 3 didn't already provide. Task 5's hardware
# build (this env var unset) keeps the real 41,600-word default.
# $readmemh on a smaller array just takes the file's first WORDS lines, so
# this is still real coefficient data, not synthetic filler.
if {[info exists ::env(PHASE2_SIM_BYPASS_CAL)] && $::env(PHASE2_SIM_BYPASS_CAL) eq "1"} {
    set_property CONFIG.WORDS {256} [get_bd_cells coeff_bram_stage_0]
    set_property CONFIG.WORDS {256} [get_bd_cells copy_fsm_0]
    puts "WORDS=256 (simulation-only, PHASE2_SIM_BYPASS_CAL=1)"
}
connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins coeff_bram_stage_0/clk]
connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins copy_fsm_0/clk]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins copy_fsm_0/rst_n]
# Unlike cnn_engine_0 (three AXI interfaces sharing one ap_clk, genuinely
# ambiguous without CONFIG.ASSOCIATED_BUSIF), copy_fsm_0 has exactly one
# clock pin and one AXI interface -- Vivado associates them unambiguously
# on its own; setting ASSOCIATED_BUSIF here is read-only/rejected and
# unnecessary.
connect_bd_net [get_bd_pins copy_fsm_0/bram_addr] [get_bd_pins coeff_bram_stage_0/addr]
connect_bd_net [get_bd_pins coeff_bram_stage_0/data] [get_bd_pins copy_fsm_0/bram_data]
connect_bd_net [get_bd_pins mig_7series_0/init_calib_complete] [get_bd_pins copy_fsm_0/start]

set_property CONFIG.NUM_SI {4} [get_bd_cells smartconnect_0]
connect_bd_intf_net [get_bd_intf_pins copy_fsm_0/m_axi] [get_bd_intf_pins smartconnect_0/S03_AXI]

# ---------------------------------------------------------------------------
# Feature BRAM staging + second copy FSM -- C3 real-image investigation
# (docs/PHASE2_LOG.md, 2026-10-29), simulation-only (same
# PHASE2_SIM_BYPASS_CAL gate as the rest of this script's sim overrides).
# Loads a real letterbox-resized/Q14-quantized photo row into cnn_engine's
# feature region (FEATURE_BASE_ADDR, matching ap_start_seq.v) via the same
# proven copy_fsm pattern, just DATA_WIDTH=256 and a different hex file. NOT
# part of the permanent hardware build -- a real camera-frame loader is
# future Phase 3 work, not this bring-up test's job.
# ---------------------------------------------------------------------------
set sim_bypass_cal [expr {[info exists ::env(PHASE2_SIM_BYPASS_CAL)] && $::env(PHASE2_SIM_BYPASS_CAL) eq "1"}]
if {$sim_bypass_cal} {
    add_files -norecurse [file join $root_dir rtl feature_bram_stage.v]
    update_compile_order -fileset sources_1
    create_bd_cell -type module -reference feature_bram_stage feature_bram_stage_0
    set hexfile_env [expr {[info exists ::env(PHASE2_FEATURE_HEXFILE)] ? $::env(PHASE2_FEATURE_HEXFILE) : [file join $root_dir rtl feature_drone.hex]}]
    set_property CONFIG.HEXFILE $hexfile_env [get_bd_cells feature_bram_stage_0]
    create_bd_cell -type module -reference copy_fsm copy_fsm_1
    set_property CONFIG.DATA_WIDTH {256} [get_bd_cells copy_fsm_1]
    set_property CONFIG.BASE_ADDR {64'h0000000080000000} [get_bd_cells copy_fsm_1]
    connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins feature_bram_stage_0/clk]
    connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins copy_fsm_1/clk]
    connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins copy_fsm_1/rst_n]
    connect_bd_net [get_bd_pins copy_fsm_1/bram_addr] [get_bd_pins feature_bram_stage_0/addr]
    connect_bd_net [get_bd_pins feature_bram_stage_0/data] [get_bd_pins copy_fsm_1/bram_data]
    connect_bd_net [get_bd_pins mig_7series_0/init_calib_complete] [get_bd_pins copy_fsm_1/start]
    set_property CONFIG.NUM_SI {5} [get_bd_cells smartconnect_0]
    connect_bd_intf_net [get_bd_intf_pins copy_fsm_1/m_axi] [get_bd_intf_pins smartconnect_0/S04_AXI]

    add_files -norecurse [file join $root_dir rtl and2.v]
    update_compile_order -fileset sources_1
    create_bd_cell -type module -reference and2 and2_0
    connect_bd_net [get_bd_pins copy_fsm_0/done] [get_bd_pins and2_0/a]
    connect_bd_net [get_bd_pins copy_fsm_1/done] [get_bd_pins and2_0/b]
    puts "FEATURE PATH ADDED (simulation-only, PHASE2_SIM_BYPASS_CAL=1): feature_bram_stage_0 + copy_fsm_1 + and2_0, HEXFILE=$hexfile_env"
}

# ---------------------------------------------------------------------------
# pipeline_seq: hardware auto-sequencer, 2026-10-29, SUPERSEDES ap_start_seq
# (removed -- having both would race, two masters each able to write
# cnn_engine's control registers around the same time). Triggers
# cnn_engine, polls its done, configures + triggers decode_work_heads_0,
# polls its done, captures its 7 BEST_O registers, and transmits them over
# UART -- the full self-contained CNN+decode+UART chain, no JTAG needed to
# drive each step. Needs AXI-Lite READ capability (poll both cores' ap_done,
# capture decoder results) that ap_start_seq.v/copy_fsm.v never needed
# (write-only), hence a new module rather than extending either. Same
# trigger source ap_start_seq used (copy_fsm_0/done on real hardware,
# and2_0/y in the sim-only feature-path build). See rtl/pipeline_seq.v's
# header for the full design and UART byte framing.
# ---------------------------------------------------------------------------
add_files -norecurse [file join $root_dir rtl pipeline_seq.v]
update_compile_order -fileset sources_1
create_bd_cell -type module -reference pipeline_seq pipeline_seq_0
connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins pipeline_seq_0/clk]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins pipeline_seq_0/rst_n]
if {$sim_bypass_cal} {
    connect_bd_net [get_bd_pins and2_0/y] [get_bd_pins pipeline_seq_0/trigger]
} else {
    connect_bd_net [get_bd_pins copy_fsm_0/done] [get_bd_pins pipeline_seq_0/trigger]
}

# S04 is free in the hardware path (ap_start_seq_0, which used to sit
# there, is removed); in the sim path S04 is already copy_fsm_1 (the
# sim-only feature copy), so pipeline_seq_0 takes S05 there instead --
# decoder's own slave index below is adjusted to match (S05 hardware / S06
# sim), keeping both paths gap-free.
set_property CONFIG.NUM_SI [expr {$sim_bypass_cal ? 6 : 5}] [get_bd_cells smartconnect_0]
connect_bd_intf_net [get_bd_intf_pins pipeline_seq_0/m_axi] [get_bd_intf_pins smartconnect_0/[format "S%02d_AXI" [expr {$sim_bypass_cal ? 5 : 4}]]]

# UART byte feed -- externalized so cnn_subsystem_top.v (outside the BD,
# where uart_tx.v is instantiated) can wire it to the real UART TX pin.
create_bd_port -dir O -from 7 -to 0 pipeline_uart_data
create_bd_port -dir O pipeline_uart_stb
create_bd_port -dir I pipeline_uart_busy
connect_bd_net [get_bd_pins pipeline_seq_0/uart_data] [get_bd_ports pipeline_uart_data]
connect_bd_net [get_bd_pins pipeline_seq_0/uart_stb] [get_bd_ports pipeline_uart_stb]
connect_bd_net [get_bd_ports pipeline_uart_busy] [get_bd_pins pipeline_seq_0/uart_busy]

# ---------------------------------------------------------------------------
# Decoder core (decode_work_heads) -- real-hardware offset/confidence
# decode, 2026-10-29. Reads cnn_engine's HEAD0/HEAD1 output directly from
# the shared feature DDR region and produces a single best detection
# (x,y,w,h,confidence,raw_objectness). Pre-generated HLS RTL from the
# teammate's handoff (cv_model/fpga/decoder_rtl/), already cosim-validated
# (HOST_CHECK.json in that same directory) -- not re-synthesized here, same
# "frozen, already-validated artifact" status as cnn_engine's own RTL.
# Decoupled (2026-10-29): decode_work_heads_0 now lives on clk_wiz_0's
# clk_out2/proc_sys_reset_2 domain, independent of cnn_engine_0's clk_out1 --
# see this file's clk_wiz_0 section header comment for why. Still the same
# CDC bridge pattern as cnn_engine_0 (two axi_clock_converters) -- lighter
# decode logic than the 331K-param CNN core, kept at a conservative fixed
# 100MHz (clk_out2) since its own real compute doesn't need to go fast.
# ---------------------------------------------------------------------------
add_files -norecurse [glob [file join $root_dir rtl decoder_core *.v]]
update_compile_order -fileset sources_1
create_bd_cell -type module -reference decode_work_heads decode_work_heads_0
connect_bd_net [get_bd_pins clk_wiz_0/clk_out2] [get_bd_pins decode_work_heads_0/ap_clk]
connect_bd_net [get_bd_pins proc_sys_reset_2/peripheral_aresetn] [get_bd_pins decode_work_heads_0/ap_rst_n]
set_property CONFIG.ASSOCIATED_BUSIF {m_axi_feature_ddr:s_axi_control} [get_bd_pins decode_work_heads_0/ap_clk]

# Feature-DDR read path: decode_work_heads_0 (clk_out2, master) -> converter
# -> smartconnect (ui_clk, as a new slave-side input) -> MIG, mirroring
# cnn_engine_0/m_axi_feature_ddr's own axi_clock_converter_0 pattern exactly.
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_clock_converter:2.1 axi_clock_converter_3
set_property CONFIG.PROTOCOL {AXI4} [get_bd_cells axi_clock_converter_3]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out2] [get_bd_pins axi_clock_converter_3/s_axi_aclk]
connect_bd_net [get_bd_pins proc_sys_reset_2/peripheral_aresetn] [get_bd_pins axi_clock_converter_3/s_axi_aresetn]
connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins axi_clock_converter_3/m_axi_aclk]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins axi_clock_converter_3/m_axi_aresetn]
connect_bd_intf_net [get_bd_intf_pins decode_work_heads_0/m_axi_feature_ddr] [get_bd_intf_pins axi_clock_converter_3/S_AXI]

# Control path: smartconnect (ui_clk, new master-side output) -> converter
# -> decode_work_heads_0/s_axi_control (clk_out2, slave), mirroring
# cnn_engine_0's own axi_clock_converter_2 pattern exactly -- a dedicated
# new M-side output since M01_AXI is already a point-to-point connection to
# cnn_engine's own control port, not shareable.
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_clock_converter:2.1 axi_clock_converter_4
set_property CONFIG.PROTOCOL {AXI4LITE} [get_bd_cells axi_clock_converter_4]
connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_pins axi_clock_converter_4/s_axi_aclk]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins axi_clock_converter_4/s_axi_aresetn]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out2] [get_bd_pins axi_clock_converter_4/m_axi_aclk]
connect_bd_net [get_bd_pins proc_sys_reset_2/peripheral_aresetn] [get_bd_pins axi_clock_converter_4/m_axi_aresetn]
connect_bd_intf_net [get_bd_intf_pins axi_clock_converter_4/M_AXI] [get_bd_intf_pins decode_work_heads_0/s_axi_control]

# One new slave input (decode's feature_ddr) and one new master output
# (decode's control, M02) -- decode's control port is reached via the new
# M02 output by EXISTING slaves (jtag_axi_0 at S02, pipeline_seq_0)
# automatically once assign_bd_address runs, not a new slave input of its
# own. Index matches pipeline_seq_0's own placement just above (S05
# hardware / S06 sim, since pipeline_seq_0 took the slot decode's feature
# port would otherwise have used).
set_property CONFIG.NUM_SI [expr {$sim_bypass_cal ? 7 : 6}] [get_bd_cells smartconnect_0]
set_property CONFIG.NUM_MI {3} [get_bd_cells smartconnect_0]
connect_bd_intf_net [get_bd_intf_pins axi_clock_converter_3/M_AXI] [get_bd_intf_pins smartconnect_0/[format "S%02d_AXI" [expr {$sim_bypass_cal ? 6 : 5}]]]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M02_AXI] [get_bd_intf_pins axi_clock_converter_4/S_AXI]

# jtag_axi_0 needs to reach decode_work_heads_0's control port too (manual
# JTAG-driven trigger/readback, same debug workflow as cnn_engine_0 --
# scripts/jtag_decode_test.tcl). It already reaches M00 (MIG) and M01 (cnn
# control) by topology; smartconnect routes any of its slaves to any of its
# masters by address, so jtag_axi_0 (already connected to S02_AXI) reaching
# the new M02_AXI happens automatically once assign_bd_address runs below --
# no new connection needed for jtag_axi_0 itself.

# Status outputs for cnn_subsystem_top's UART reporter (Task 4). These are
# genuine top-level ports of their own cells, so externalizing them is
# direct -- unlike cnn_engine's ap_done, which is an internal reg with no
# port at all (cnn_subsystem_top.v reaches that one via a hierarchical
# reference instead; see its header comment).
#
# make_bd_pins_external silently no-ops on these two pins in this Vivado
# version (confirmed: returns RC=0 and creates no port, reproducible even
# on a freshly reloaded design, even for an unconnected output pin like
# mmcm_locked tested the same way) -- root cause not tracked down, but the
# equivalent manual create_bd_port + connect_bd_net works reliably, so
# that's what's used instead.
create_bd_port -dir O init_calib_complete_dbg
connect_bd_net [get_bd_pins mig_7series_0/init_calib_complete] [get_bd_ports init_calib_complete_dbg]
create_bd_port -dir O copy_fsm_done_dbg
connect_bd_net [get_bd_pins copy_fsm_0/done] [get_bd_ports copy_fsm_done_dbg]
# copy_fsm_1/done (feature copy, sim-only) deliberately has no top-level
# debug port -- cnn_subsystem_top.v's port list is static and shared between
# the sim and hardware builds, and this signal only exists in the former.
# sim/tb_cnn_subsystem_top.v reaches it the same way it already reaches
# cnn_engine's true ap_done: a hierarchical reference, sim-only.
# pipeline_seq_0's done (2026-10-29 -- was ap_start_seq_0's done pre-
# pipeline_seq; port name kept for continuity). Now means "the whole
# CNN+decode+UART pipeline finished," a genuinely stronger/more meaningful
# signal than the old "one AXI-Lite write acknowledged" -- the
# synthesizable stand-in for cnn_engine's true ap_done either way. See
# cnn_subsystem_top.v's header comment for why a hierarchical reference
# to cnn_engine's internal ap_done reg isn't used directly here: it
# elaborates fine in simulation but synth_design cannot resolve it
# ("cannot resolve hierarchical name for the item 'u_bd'") -- found by
# actually running synthesis, not by inspection.
create_bd_port -dir O ap_start_issued_dbg
connect_bd_net [get_bd_pins pipeline_seq_0/done] [get_bd_ports ap_start_issued_dbg]
# ui_clk itself, so cnn_subsystem_top.v's UART status reporter can run in
# the same clock domain as everything it is reporting on, instead of
# needing a second independent clock just for status reporting.
create_bd_port -dir O ui_clk_dbg
connect_bd_net [get_bd_pins mig_7series_0/ui_clk] [get_bd_ports ui_clk_dbg]

set rc [catch {assign_bd_address} result]
if {$rc} {
    puts "ASSIGN_BD_ADDRESS FAILED: $result"
    exit 1
}
save_bd_design

set rc [catch {validate_bd_design} result]
if {$rc} {
    puts "VALIDATE_BD_DESIGN FAILED: $result"
    exit 1
}
puts "VALIDATE_BD_DESIGN OK"

# report_bd_address_map does not exist in Vivado 2023.2 (plan named it by
# mistake -- ruling: enumerate get_bd_addr_segs/OFFSET/RANGE instead, same
# information).
foreach seg [get_bd_addr_segs] {
    puts [format "ADDR_SEG %-55s OFFSET=%-20s RANGE=%s" $seg \
        [get_property OFFSET $seg] [get_property RANGE $seg]]
}
save_bd_design
puts "BD CREATED: cv_subsystem"

# ---------------------------------------------------------------------------
# Top level: generate the BD's Verilog wrapper, add cnn_subsystem_top.v
# (which instantiates it) and its uart_tx.v dependency, set
# cnn_subsystem_top as the actual synthesis top.
# ---------------------------------------------------------------------------
generate_target all [get_files cv_subsystem.bd]
make_wrapper -files [get_files cv_subsystem.bd] -top -force
add_files -norecurse [glob [file join [get_property DIRECTORY [current_project]] genesys2_cv.gen sources_1 bd cv_subsystem hdl cv_subsystem_wrapper.v]]
add_files -norecurse [list \
    [file join $root_dir rtl cnn_subsystem_top.v] \
    [file join $root_dir rtl uart_tx.v] \
]
update_compile_order -fileset sources_1
set_property top cnn_subsystem_top [current_fileset]
update_compile_order -fileset sources_1
puts "TOP SET: cnn_subsystem_top"

# User constraints (sys_clk/sys_rst/UART -- not MIG's own pins, which
# arrive automatically via its generated output-product XDC once the BD
# is a project source).
add_files -fileset constrs_1 -norecurse [file join $root_dir constraints genesys2_cv.xdc]
update_compile_order -fileset constrs_1
