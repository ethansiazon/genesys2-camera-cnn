// Standalone CNN+DDR3/AXI timing subsystem top level -- Phase 2 Task 4 (see
// docs/superpowers/plans/2026-10-28-phase2-ddr-axi-timing.md and
// docs/PHASE2_LOG.md). Instantiates the cv_subsystem block design (MIG +
// cnn_engine + decode_work_heads + smartconnect + copy_fsm/coeff_bram_stage
// + jtag_axi + pipeline_seq) and transmits the decoded detection (x,y,w,h,
// confidence,raw_objectness,valid) over UART once per pipeline run
// (2026-10-29 -- pipeline_seq_0 supersedes the old ap_start_seq_0 trigger
// and the old repeating-status-byte reporter this module used to drive
// uart_tx with). No camera RTL anywhere in this hierarchy -- deliberately
// isolates the new DDR/AXI risk from the camera risk already proven in
// ~/fpga/genesys2-ov5640-hdmi.
//
// Clock-domain note (Global Constraints / Review Focus item 5): cnn_engine's
// ap_clk is tied to MIG's ui_clk INSIDE the block design (bd/create_bd.tcl),
// and this module's own status-reporting logic runs on that same ui_clk
// (exposed here as ui_clk_dbg) rather than a second independent clock. This
// avoids a CDC in this standalone phase. Camera integration (handoff phase
// 3+) runs the pixel pipeline on a different clock and will need a real CDC
// at that boundary -- this tie does not survive past this phase unmodified.
`timescale 1ns / 1ps
`default_nettype none

module cnn_subsystem_top #(
    // Simulation-only: use the hierarchical reference to cnn_engine's true
    // internal ap_done instead of ap_start_seq's "write acknowledged" proxy.
    // MUST stay 0 for synthesis -- synth_design cannot resolve a
    // hierarchical reference into a compiled sub-module's internals
    // ("cannot resolve hierarchical name for the item 'u_bd'", found by
    // actually running synthesis, not by inspection). sim/tb_cnn_subsystem_top.v
    // overrides this to 1.
    parameter SIM_HIERARCHICAL_AP_DONE_PROBE = 0
)(
    input  wire         sys_clk_p,
    input  wire         sys_clk_n,
    input  wire         sys_rst,       // active-low board reset

    output wire [14:0]  ddr3_addr,
    output wire [2:0]   ddr3_ba,
    output wire         ddr3_cas_n,
    output wire [0:0]   ddr3_ck_n,
    output wire [0:0]   ddr3_ck_p,
    output wire [0:0]   ddr3_cke,
    output wire [0:0]   ddr3_cs_n,
    output wire [3:0]   ddr3_dm,
    inout  wire [31:0]  ddr3_dq,
    inout  wire [3:0]   ddr3_dqs_n,
    inout  wire [3:0]   ddr3_dqs_p,
    output wire [0:0]   ddr3_odt,
    output wire         ddr3_ras_n,
    output wire         ddr3_reset_n,
    output wire         ddr3_we_n,

    output wire         uart_tx_pin
);

    wire ui_clk;
    wire init_calib_complete;
    wire copy_fsm_done;
    // Now fed by pipeline_seq_0/done (see bd/create_bd.tcl) -- "the whole
    // CNN+decode+UART pipeline finished," not just "one AXI-Lite write
    // acknowledged" (the old ap_start_seq_0 meaning this port name still
    // carries for historical/debug-port-naming continuity).
    wire ap_start_issued;
    wire [7:0] pipeline_uart_data;
    wire       pipeline_uart_stb;
    wire       pipeline_uart_busy;

    cv_subsystem_wrapper u_bd (
        .DDR3_0_addr    (ddr3_addr),
        .DDR3_0_ba      (ddr3_ba),
        .DDR3_0_cas_n   (ddr3_cas_n),
        .DDR3_0_ck_n    (ddr3_ck_n),
        .DDR3_0_ck_p    (ddr3_ck_p),
        .DDR3_0_cke     (ddr3_cke),
        .DDR3_0_cs_n    (ddr3_cs_n),
        .DDR3_0_dm      (ddr3_dm),
        .DDR3_0_dq      (ddr3_dq),
        .DDR3_0_dqs_n   (ddr3_dqs_n),
        .DDR3_0_dqs_p   (ddr3_dqs_p),
        .DDR3_0_odt     (ddr3_odt),
        .DDR3_0_ras_n   (ddr3_ras_n),
        .DDR3_0_reset_n (ddr3_reset_n),
        .DDR3_0_we_n    (ddr3_we_n),
        .ap_start_issued_dbg     (ap_start_issued),
        .copy_fsm_done_dbg       (copy_fsm_done),
        .ext_reset_in            (sys_rst),      // active-low, same as sys_rst_0
        .init_calib_complete_dbg (init_calib_complete),
        .pipeline_uart_data      (pipeline_uart_data),
        .pipeline_uart_stb       (pipeline_uart_stb),
        .pipeline_uart_busy      (pipeline_uart_busy),
        .sys_clk_clk_n  (sys_clk_n),
        .sys_clk_clk_p  (sys_clk_p),
        .sys_rst_0      (sys_rst),
        .ui_clk_dbg     (ui_clk)
    );

    // cnn_engine's true ap_done has no top-level port at all (it is an
    // internal `reg` inside rtl/cnn_core/cnn_engine.v, read only via the
    // AXI-Lite control register in normal use). A hierarchical reference
    // into the generated BD hierarchy resolves fine in simulation (used by
    // sim/tb_cnn_subsystem_top.v's own verification, which is a stronger
    // check than this status bit needs to be) but synth_design cannot
    // resolve it at all -- confirmed by actually running synthesis, not
    // by inspection: "ERROR: [Synth 8-6038] cannot resolve hierarchical
    // name for the item 'u_bd'". For the real hardware build (this
    // parameter's default, 0), the third status bit is ap_start_issued
    // instead -- a real synthesizable signal, but a different, weaker
    // claim ("told to start", not "finished").
    wire cnn_ap_done;
    generate
        if (SIM_HIERARCHICAL_AP_DONE_PROBE) begin : sim_probe
            assign cnn_ap_done = u_bd.cv_subsystem_i.cnn_engine_0.inst.ap_done;
        end else begin : hw_proxy
            assign cnn_ap_done = ap_start_issued;
        end
    endgenerate

    // cnn_ap_done no longer drives a status byte here (pipeline_seq_0,
    // inside the BD, does its own AXI-Lite polling of cnn_engine's real
    // ap_done bit directly) -- kept defined only because
    // sim/tb_cnn_subsystem_top.v reaches it by hierarchical reference
    // (`dut.cnn_ap_done`); do not remove this generate block.

    // UART: driven directly by pipeline_seq_0's byte stream (sync byte +
    // 28 bytes of decoded detection, see rtl/pipeline_seq.v's header for
    // the exact framing) -- replaces the old repeating status-byte
    // reporter, which would otherwise be a second driver of the same
    // uart_tx instance.
    uart_tx #(
        .CLK_HZ(225_022_502),
        .BAUD(115200)
    ) u_uart (
        .clk  (ui_clk),
        // uart_tx's own registers all have power-on-safe declared initial
        // values (see rtl/uart_tx.v) -- no dynamic reset needed, same as
        // its existing use in genesys2-ov5640-hdmi.
        .rst  (1'b0),
        .data (pipeline_uart_data),
        .stb  (pipeline_uart_stb),
        .tx   (uart_tx_pin),
        .busy (pipeline_uart_busy)
    );

endmodule

`default_nettype wire
