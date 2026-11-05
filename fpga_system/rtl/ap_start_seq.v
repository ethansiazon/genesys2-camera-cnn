// Programs cnn_engine's AXI-M base-address pointers, then writes ap_start=1,
// via a sequence of one-shot AXI-Lite writes to s_axi_control, triggered
// once by `trigger` going high (copy_fsm_0/done in cnn_subsystem_top).
//
// CRITICAL FIX (code review, 2026-10-28): the first version of this module
// wrote ONLY ap_start and left cnn_engine's FEATURES/COEFFICIENTS pointer
// registers at their reset value of 0 -- meaning cnn_engine's own AXI-M
// masters addressed DDR offset 0x0, which the system address map decodes
// to cnn_engine's OWN control-register segment, not DDR. Confirmed by
// reading rtl/cnn_core/cnn_engine_control_s_axi.v: ADDR_FEATURES_DATA_0/1
// = 0x10/0x14, ADDR_COEFFICIENTS_DATA_0/1 = 0x1c/0x20, both reset to 0.
// This sequencer now writes those four registers (lower 32 bits = the real
// address, upper 32 bits = 0, since FEATURE_BASE_ADDR/COEFFICIENT_BASE_ADDR
// both fit in 32 bits) before ap_start, in the fixed order below.
//
// FEATURE_BASE_ADDR default (0x80000000) matches the shared DDR window's
// base (docs/PHASE2_LOG.md Task 2's address-map finding).
// COEFFICIENT_BASE_ADDR default (0x80300000) matches copy_fsm's own
// BASE_ADDR default -- cnn_engine must look for coefficients at the same
// place copy_fsm wrote them.
//
// Exists only because Task 4's brief calls for cnn_engine_ap_done to assert
// in simulation, and nothing else in this standalone subsystem (no
// software/processor) would ever write these registers at all -- see
// docs/PHASE2_LOG.md's Task 4 section for the full ruling. This is a real
// hardware module (not testbench-only): on actual hardware it lets the
// subsystem self-exercise one CNN pass after coefficient load, for
// AXI/handshake/timing validation -- it does not claim the result is a
// meaningful detection, since no camera feature data exists in DDR yet.
`timescale 1ns/1ps
module ap_start_seq #(
    parameter [31:0] FEATURE_BASE_ADDR     = 32'h80000000,
    parameter [31:0] COEFFICIENT_BASE_ADDR = 32'h80300000
)(
    input  wire        clk,
    input  wire         rst_n,
    input  wire         trigger,
    output reg          done,
    // Sticky: latched high if any of the 5 writes below got a non-OKAY
    // BRESP. The first version of this module ignored BRESP entirely
    // (same silent-false-positive class as the bugs documented elsewhere
    // in this phase) -- `done` now only means "5/5 writes completed",
    // not "5/5 writes succeeded"; check this bit too.
    output reg          err,

    output reg          m_axi_AWVALID,
    input  wire         m_axi_AWREADY,
    // 32 bits, not cnn_engine's internal 6-bit decode width: SmartConnect's
    // address assignment sizes this master's reachable segment generically
    // (the control port's assigned aperture is 0x1000/4096 bytes = 12 bits),
    // and a too-narrow AWADDR hard-errors address assignment regardless of
    // what the slave actually decodes internally.
    output reg  [31:0]  m_axi_AWADDR,
    output reg  [0:0]   m_axi_AWID,
    output reg  [7:0]   m_axi_AWLEN,
    output reg  [2:0]   m_axi_AWSIZE,
    output reg  [1:0]   m_axi_AWBURST,

    output reg          m_axi_WVALID,
    input  wire         m_axi_WREADY,
    output reg  [31:0]  m_axi_WDATA,
    output reg  [3:0]   m_axi_WSTRB,
    output reg          m_axi_WLAST,
    output reg  [0:0]   m_axi_WID,

    input  wire         m_axi_BVALID,
    output reg          m_axi_BREADY,
    input  wire [1:0]   m_axi_BRESP,
    input  wire [0:0]   m_axi_BID
);
    localparam S_IDLE  = 3'd0;
    localparam S_AW    = 3'd1;
    localparam S_W     = 3'd2;
    localparam S_B     = 3'd3;
    localparam S_NEXT  = 3'd4;
    localparam S_DONE  = 3'd5;

    // Fixed write sequence: FEATURES_DATA_0/1, COEFFICIENTS_DATA_0/1,
    // AP_CTRL (ap_start). ADDR_AP_CTRL etc. per
    // rtl/cnn_core/cnn_engine_control_s_axi.v.
    localparam N_WRITES = 4'd5;
    reg [5:0]  wr_addr [0:4];
    reg [31:0] wr_data [0:4];
    initial begin
        wr_addr[0] = 6'h10; wr_data[0] = FEATURE_BASE_ADDR;      // ADDR_FEATURES_DATA_0
        wr_addr[1] = 6'h14; wr_data[1] = 32'h00000000;            // ADDR_FEATURES_DATA_1
        wr_addr[2] = 6'h1c; wr_data[2] = COEFFICIENT_BASE_ADDR;   // ADDR_COEFFICIENTS_DATA_0
        wr_addr[3] = 6'h20; wr_data[3] = 32'h00000000;            // ADDR_COEFFICIENTS_DATA_1
        wr_addr[4] = 6'h00; wr_data[4] = 32'h00000001;            // ADDR_AP_CTRL: ap_start
    end

    reg [2:0] state;
    reg [2:0] idx;

    always @(posedge clk) begin
        if (!rst_n) begin
            state         <= S_IDLE;
            idx           <= 3'd0;
            done          <= 1'b0;
            err           <= 1'b0;
            m_axi_AWVALID <= 1'b0;
            m_axi_WVALID  <= 1'b0;
            m_axi_BREADY  <= 1'b0;
        end else begin
            case (state)
                S_IDLE: begin
                    done <= 1'b0;
                    if (trigger) begin
                        idx   <= 3'd0;
                        state <= S_AW;
                    end
                end

                S_AW: begin
                    m_axi_AWVALID  <= 1'b1;
                    m_axi_AWADDR   <= {26'd0, wr_addr[idx]};
                    m_axi_AWID     <= 1'b0;
                    m_axi_AWLEN    <= 8'd0;
                    m_axi_AWSIZE   <= 3'd2; // 4 bytes
                    m_axi_AWBURST  <= 2'b01;
                    if (m_axi_AWVALID && m_axi_AWREADY) begin
                        m_axi_AWVALID <= 1'b0;
                        m_axi_WVALID  <= 1'b1;
                        m_axi_WDATA   <= wr_data[idx];
                        m_axi_WSTRB   <= 4'hF;
                        m_axi_WLAST   <= 1'b1;
                        m_axi_WID     <= 1'b0;
                        state         <= S_W;
                    end
                end

                S_W: begin
                    if (m_axi_WVALID && m_axi_WREADY) begin
                        m_axi_WVALID <= 1'b0;
                        m_axi_BREADY <= 1'b1;
                        state        <= S_B;
                    end
                end

                S_B: begin
                    if (m_axi_BREADY && m_axi_BVALID) begin
                        m_axi_BREADY <= 1'b0;
                        if (m_axi_BRESP != 2'b00) err <= 1'b1;
                        state <= S_NEXT;
                    end
                end

                S_NEXT: begin
                    if (idx == N_WRITES - 1) begin
                        state <= S_DONE;
                    end else begin
                        idx   <= idx + 3'd1;
                        state <= S_AW;
                    end
                end

                S_DONE: begin
                    done <= 1'b1;
                    if (!trigger) state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end
endmodule
