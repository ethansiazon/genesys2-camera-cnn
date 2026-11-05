// Full-chain, MIG-calibration-aware simulation of cnn_subsystem_top (Phase 2
// Task 4). Unlike Task 3's lightweight behavioral-RAM test, this drives the
// actual MIG-generated DDR3 PHY against Xilinx's own ddr3_model.sv behavioral
// memory chip, through the WireDelay buffering MIG's own example-design
// testbench (sim_tb_top.v, in the generated
// vivado/.../mig_7series_0_0/.../example_design/sim/) uses -- copied here
// (sim/mig_sim_models/) so this testbench doesn't depend on the disposable
// vivado/ directory surviving. PCB trace delays are all 0 in that reference
// (functional-only simulation, no layout yet), reused as-is.
//
// Must be built with PHASE2_SIM_BYPASS_CAL=1 in the environment (see
// bd/create_bd.tcl) -- MIG's SIM_BYPASS_INIT_CAL=FAST and the 256-word
// coefficient-count override are both gated on it. Building without it
// elaborates the real hardware configuration and this testbench's watchdogs
// (sized for the FAST/256-word case) would very likely fire on a full
// calibration + 41,600-word run -- that combination is intentionally never
// exercised in simulation; Task 5 validates the real configuration via
// synthesis/timing instead.
`timescale 1ps/100fs

module tb_cnn_subsystem_top;

    // Matches mig.prj (MT41J256M16XX-107, DataWidth=32) and the generated
    // cv_subsystem_mig_7series_0_0's own example-design testbench.
    localparam DQ_WIDTH   = 32;
    localparam DQS_WIDTH  = 4;
    localparam DM_WIDTH   = 4;
    localparam ROW_WIDTH  = 15;
    localparam CS_WIDTH   = 1;
    localparam CLKIN_PERIOD_PS = 4999; // ~200.04MHz, matches sys_clk's 200MHz
    localparam RESET_PERIOD_PS = 200000;

    reg  sys_rst_n;
    wire sys_rst;
    assign sys_rst = sys_rst_n; // active-low, matches RST_ACT_LOW=1 convention

    reg sys_clk_i;
    wire sys_clk_p = sys_clk_i;
    wire sys_clk_n = ~sys_clk_i;

    initial begin
        sys_rst_n = 1'b0;
        #RESET_PERIOD_PS sys_rst_n = 1'b1;
    end

    initial sys_clk_i = 1'b0;
    always #(CLKIN_PERIOD_PS/2.0) sys_clk_i = ~sys_clk_i;

    wire [ROW_WIDTH-1:0] ddr3_addr;
    wire [2:0]           ddr3_ba;
    wire                 ddr3_cas_n;
    wire [0:0]           ddr3_ck_n;
    wire [0:0]           ddr3_ck_p;
    wire [0:0]           ddr3_cke;
    wire [(CS_WIDTH*1)-1:0] ddr3_cs_n;
    wire [DM_WIDTH-1:0]  ddr3_dm;
    wire [DQ_WIDTH-1:0]  ddr3_dq_fpga;
    wire [DQS_WIDTH-1:0] ddr3_dqs_n_fpga;
    wire [DQS_WIDTH-1:0] ddr3_dqs_p_fpga;
    wire [0:0]           ddr3_odt;
    wire                 ddr3_ras_n;
    wire                 ddr3_reset_n;
    wire                 ddr3_we_n;

    wire init_calib_complete;
    wire copy_fsm_done;

    cnn_subsystem_top #(
        .SIM_HIERARCHICAL_AP_DONE_PROBE(1)
    ) dut (
        .sys_clk_p (sys_clk_p),
        .sys_clk_n (sys_clk_n),
        .sys_rst   (sys_rst),

        .ddr3_addr    (ddr3_addr),
        .ddr3_ba      (ddr3_ba),
        .ddr3_cas_n   (ddr3_cas_n),
        .ddr3_ck_n    (ddr3_ck_n),
        .ddr3_ck_p    (ddr3_ck_p),
        .ddr3_cke     (ddr3_cke),
        .ddr3_cs_n    (ddr3_cs_n),
        .ddr3_dm      (ddr3_dm),
        .ddr3_dq      (ddr3_dq_fpga),
        .ddr3_dqs_n   (ddr3_dqs_n_fpga),
        .ddr3_dqs_p   (ddr3_dqs_p_fpga),
        .ddr3_odt     (ddr3_odt),
        .ddr3_ras_n   (ddr3_ras_n),
        .ddr3_reset_n (ddr3_reset_n),
        .ddr3_we_n    (ddr3_we_n),

        .uart_tx_pin (/* unused by this testbench */)
    );

    // dut.init_calib_complete / dut.copy_fsm_done don't exist as DUT-level
    // signals -- cnn_subsystem_top only exposes them wrapped inside its own
    // internal wires of the same name, which ARE directly hierarchically
    // visible (no deeper path needed, unlike ap_done).
    assign init_calib_complete = dut.init_calib_complete;
    assign copy_fsm_done       = dut.copy_fsm_done;

    // C3 real-image investigation (2026-10-29): the feature copy FSM
    // (copy_fsm_1, loading a real photo row into cnn_engine's feature
    // region) is sim-only and has no top-level debug port -- same
    // hierarchical-reference approach as cnn_ap_done below, since
    // cnn_subsystem_top.v's port list is shared with the (port-less-for-this)
    // hardware build.
    wire feature_copy_fsm_done = dut.u_bd.cv_subsystem_i.copy_fsm_1.done;

    // DDR3 behavioral memory model + WireDelay buffering, same pattern as
    // the generated MIG example design's sim_tb_top.v.
    wire [DQ_WIDTH-1:0]  ddr3_dq_sdram;
    reg  [ROW_WIDTH-1:0] ddr3_addr_sdram;
    reg  [2:0]           ddr3_ba_sdram;
    reg                  ddr3_ras_n_sdram;
    reg                  ddr3_cas_n_sdram;
    reg                  ddr3_we_n_sdram;
    reg  [(CS_WIDTH*1)-1:0] ddr3_cs_n_sdram;
    // Net, not reg: dm_tdqs on ddr3_model is `inout` (DM shares the TDQS
    // function in some DDR3 modes), and Verilog requires a net on both
    // sides of an inout connection -- a reg here elaborates with "non-net
    // variable cannot be connected to inout port". Driven via a reg tmp +
    // continuous assign, same two-step the MIG reference testbench uses.
    reg  [DM_WIDTH-1:0]  ddr3_dm_sdram_tmp;
    wire [DM_WIDTH-1:0]  ddr3_dm_sdram = ddr3_dm_sdram_tmp;
    wire [DQS_WIDTH-1:0] ddr3_dqs_p_sdram;
    wire [DQS_WIDTH-1:0] ddr3_dqs_n_sdram;
    reg  [0:0]           ddr3_ck_p_sdram;
    reg  [0:0]           ddr3_ck_n_sdram;
    reg  [0:0]           ddr3_cke_sdram;
    reg  [0:0]           ddr3_odt_sdram;

    always @(*) begin
        ddr3_ck_p_sdram  <= ddr3_ck_p;
        ddr3_ck_n_sdram  <= ddr3_ck_n;
        ddr3_addr_sdram  <= ddr3_addr;
        ddr3_ba_sdram    <= ddr3_ba;
        ddr3_ras_n_sdram <= ddr3_ras_n;
        ddr3_cas_n_sdram <= ddr3_cas_n;
        ddr3_we_n_sdram  <= ddr3_we_n;
        ddr3_cke_sdram   <= ddr3_cke;
        ddr3_cs_n_sdram  <= ddr3_cs_n;
        ddr3_dm_sdram_tmp <= ddr3_dm;
        ddr3_odt_sdram   <= ddr3_odt;
    end

    genvar dqwd;
    generate
        for (dqwd = 0; dqwd < DQ_WIDTH; dqwd = dqwd + 1) begin : dq_delay
            WireDelay #(.Delay_g(0.00), .Delay_rd(0.00), .ERR_INSERT("OFF")) u_delay_dq (
                .A(ddr3_dq_fpga[dqwd]), .B(ddr3_dq_sdram[dqwd]),
                .reset(sys_rst_n), .phy_init_done(init_calib_complete)
            );
        end
    endgenerate

    genvar dqswd;
    generate
        for (dqswd = 0; dqswd < DQS_WIDTH; dqswd = dqswd + 1) begin : dqs_delay
            WireDelay #(.Delay_g(0.00), .Delay_rd(0.00), .ERR_INSERT("OFF")) u_delay_dqs_p (
                .A(ddr3_dqs_p_fpga[dqswd]), .B(ddr3_dqs_p_sdram[dqswd]),
                .reset(sys_rst_n), .phy_init_done(init_calib_complete)
            );
            WireDelay #(.Delay_g(0.00), .Delay_rd(0.00), .ERR_INSERT("OFF")) u_delay_dqs_n (
                .A(ddr3_dqs_n_fpga[dqswd]), .B(ddr3_dqs_n_sdram[dqswd]),
                .reset(sys_rst_n), .phy_init_done(init_calib_complete)
            );
        end
    endgenerate

    // DQ_WIDTH=32 is exactly 2x16 -- one ddr3_model per 16-bit component,
    // same as sim_tb_top.v's DQ_WIDTH/16 case.
    ddr3_model u_comp_ddr3_0 (
        .rst_n(ddr3_reset_n), .ck(ddr3_ck_p_sdram), .ck_n(ddr3_ck_n_sdram),
        .cke(ddr3_cke_sdram[0]), .cs_n(ddr3_cs_n_sdram[0]),
        .ras_n(ddr3_ras_n_sdram), .cas_n(ddr3_cas_n_sdram), .we_n(ddr3_we_n_sdram),
        .dm_tdqs(ddr3_dm_sdram[1:0]), .ba(ddr3_ba_sdram), .addr(ddr3_addr_sdram),
        .dq(ddr3_dq_sdram[15:0]),
        .dqs(ddr3_dqs_p_sdram[1:0]), .dqs_n(ddr3_dqs_n_sdram[1:0]),
        .tdqs_n(), .odt(ddr3_odt_sdram[0])
    );
    ddr3_model u_comp_ddr3_1 (
        .rst_n(ddr3_reset_n), .ck(ddr3_ck_p_sdram), .ck_n(ddr3_ck_n_sdram),
        .cke(ddr3_cke_sdram[0]), .cs_n(ddr3_cs_n_sdram[0]),
        .ras_n(ddr3_ras_n_sdram), .cas_n(ddr3_cas_n_sdram), .we_n(ddr3_we_n_sdram),
        .dm_tdqs(ddr3_dm_sdram[3:2]), .ba(ddr3_ba_sdram), .addr(ddr3_addr_sdram),
        .dq(ddr3_dq_sdram[31:16]),
        .dqs(ddr3_dqs_p_sdram[3:2]), .dqs_n(ddr3_dqs_n_sdram[3:2]),
        .tdqs_n(), .odt(ddr3_odt_sdram[0])
    );

    // Plain Verilog-2001 (fork/join_any are SystemVerilog-only, and this is
    // a .v file -- same lesson as sim/tb_bram_to_ddr.v in Task 3). Each
    // stage is a wait/timeout pair racing via named-block `disable`,
    // chained so a later stage's pair doesn't even start timing until the
    // previous stage actually succeeded.
    reg stage1_done = 1'b0, stage2_done = 1'b0, stage3_done = 1'b0;
    reg stage1_timeout = 1'b0, stage2_timeout = 1'b0, stage3_timeout = 1'b0;

    // All three #delay literals below are written as real numbers (trailing
    // `.0`), not plain decimal integers: an unsized Verilog integer literal
    // defaults to 32 bits even in a delay context, and 20_000_000_000 /
    // 40_000_000_000 both exceed 2^31-1 and silently wrap to garbage
    // (xelab warned "using -1474836480 instead" the first time this was
    // written without `.0` -- caught before ever running the sim, not
    // discovered by a mysteriously-wrong watchdog). Real-number delays have
    // no such width limit.

    // Stage 1: calibration. FAST bypass typically completes in low tens of
    // microseconds of simulated time; 2ms is a large margin, not a tight
    // bound.
    initial begin : s1_wait
        wait (init_calib_complete);
        stage1_done = 1'b1;
        disable s1_timeout;
    end
    initial begin : s1_timeout
        #2_000_000_000.0;
        stage1_timeout = 1'b1;
        disable s1_wait;
    end

    // Stage 2: 256-word coefficient copy through the real MIG/AXI path
    // (not Task 3's lightweight behavioral slave, which is why this margin
    // is far larger than Task 3's).
    initial begin : s2_wait
        wait (stage1_done);
        wait (copy_fsm_done);
        wait (feature_copy_fsm_done);
        stage2_done = 1'b1;
        disable s2_timeout;
    end
    initial begin : s2_timeout
        wait (stage1_done);
        #20_000_000_000.0;
        stage2_timeout = 1'b1;
        disable s2_wait;
    end

    // Stage 3: ap_start_seq programs cnn_engine's FEATURES/COEFFICIENTS
    // pointers and writes ap_start, cnn_engine begins running, and finishes
    // one pass (against whatever default feature-memory contents exist --
    // not a meaningful detection, see rtl/ap_start_seq.v's header comment,
    // just an end-to-end handshake proof).
    //
    // Cycle-count floor (code review, 2026-10-28, closing the C3 finding):
    // Phase 1 measured a REAL pass at 3,774,628 cycles
    // (PHASE1_STATUS.md). The first version of this check only waited for
    // cnn_ap_done with no lower bound -- exactly the silent-false-positive
    // pattern PHASE1_STATUS.md itself warned about ("225 cycles, zero
    // memory accesses, core effectively did nothing... always check cycle
    // count... look like REAL work"). A misconfigured address map (this
    // phase's own C2 finding: cnn_engine's pointers defaulting to 0, which
    // decodes to its own control port) would let ap_done assert almost
    // immediately. 100,000 cycles is comfortably above a trivial/broken
    // pass and comfortably below the real 3.77M-cycle figure, so it
    // distinguishes "did nothing" from "did something" without requiring
    // this all-default-data run to reproduce Phase 1's exact count.
    reg [63:0] ap_start_seq_begin_time;
    reg [63:0] ap_done_elapsed_cycles;
    localparam real UI_CLK_PERIOD_NS = 4.444;
    localparam MIN_REAL_PASS_CYCLES  = 64'd100_000;
    initial begin : s3_wait
        wait (stage2_done);
        ap_start_seq_begin_time = $time;
        wait (dut.cnn_ap_done);
        ap_done_elapsed_cycles = ($time - ap_start_seq_begin_time) / (UI_CLK_PERIOD_NS * 1000.0); // $time is in ps
        $display("STAGE 3 TIMING: %0d cycles from copy_fsm_done to cnn_ap_done (floor: %0d)",
            ap_done_elapsed_cycles, MIN_REAL_PASS_CYCLES);
        if (ap_done_elapsed_cycles < MIN_REAL_PASS_CYCLES) begin
            $display("FAIL: cnn_ap_done asserted after only %0d cycles -- this is the silent-false-positive pattern (compare Phase 1's real 3,774,628-cycle pass). Check cnn_engine's FEATURES/COEFFICIENTS pointer registers (ap_start_seq.v) and the address map.", ap_done_elapsed_cycles);
            $finish;
        end
        stage3_done = 1'b1;
        disable s3_timeout;
    end
    initial begin : s3_timeout
        wait (stage2_done);
        #40_000_000_000.0;
        stage3_timeout = 1'b1;
        disable s3_wait;
    end

    initial begin : reporter
        wait (stage1_done || stage1_timeout);
        if (stage1_timeout) begin
            $display("WATCHDOG: stuck before init_calib_complete");
            $finish;
        end
        $display("STAGE 1: init_calib_complete");

        wait (stage2_done || stage2_timeout);
        if (stage2_timeout) begin
            $display("WATCHDOG: stuck before copy_fsm_done");
            $finish;
        end
        $display("STAGE 2: copy_fsm_done");

        wait (stage3_done || stage3_timeout);
        if (stage3_timeout) begin
            $display("WATCHDOG: stuck before cnn_ap_done");
            $finish;
        end
        $display("STAGE 3: cnn_ap_done");

        $display("ALL STAGES OK");
        $finish;
    end

endmodule
