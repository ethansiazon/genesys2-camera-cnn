// Bursts WORDS 128-bit words from coeff_bram_stage out over a single-ID
// AXI4 master write channel, one AW/W/B transaction per word (no attempt at
// burst-length optimization in this bring-up phase -- see
// docs/superpowers/plans/2026-10-28-phase2-ddr-axi-timing.md Task 3).
//
// Port names/widths mirror cnn_engine's m_axi_coefficient_ddr_* convention
// (rtl/cnn_core/cnn_engine.v: ID_WIDTH=1, ADDR_WIDTH=64, DATA_WIDTH=128,
// WSTRB_WIDTH=16, AWLOCK width 2) so Task 4 can wire this into the same
// smartconnect slave shape.
//
// BASE_ADDR defaults to 0x80300000 -- the real system offset pinned in
// docs/PHASE2_LOG.md's Task 2 address-map finding, clear of the feature
// region's 0x240000 bytes at the shared 0x80000000 DDR base. Task 3's own
// testbench overrides this to 0 because its behavioral axi_ram.sv slave is
// sized far smaller than the real 1GB DDR window.
//
// `err` (code review, 2026-10-28): the first version of this FSM completed
// on BVALID alone and never read BRESP, so a DECERR/SLVERR response (e.g.
// from a misconfigured address map) would still assert `done`. See `err`.
//
// DATA_WIDTH (C3 real-image investigation, 2026-10-29): parameterized from
// the original hardcoded 128 so the same FSM can also drive cnn_engine's
// 256-bit feature AXI master (feature_bram_stage.v + a second copy_fsm
// instance) instead of writing a near-duplicate module. AWSIZE/shift are
// derived from DATA_WIDTH via a ternary rather than $clog2, since only
// 128 and 256 are ever instantiated here.
`timescale 1ns/1ps
module copy_fsm #(
    parameter WORDS       = 41600,
    parameter ADDR_W      = 16,       // >= $clog2(WORDS)
    parameter DATA_WIDTH  = 128,      // 128 (coefficients) or 256 (features)
    parameter [63:0] BASE_ADDR = 64'h0000000080300000
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    output reg         done,
    // Sticky: latched high if any write got a non-OKAY BRESP. The first
    // version of this FSM ignored BRESP entirely -- `done` means "41,600
    // writes completed", not "41,600 writes succeeded". Code review,
    // 2026-10-28.
    output reg         err,

    output wire [ADDR_W-1:0] bram_addr,
    input  wire [DATA_WIDTH-1:0] bram_data,

    output reg          m_axi_AWVALID,
    input  wire         m_axi_AWREADY,
    output reg  [63:0]  m_axi_AWADDR,
    output reg  [0:0]   m_axi_AWID,
    output reg  [7:0]   m_axi_AWLEN,
    output reg  [2:0]   m_axi_AWSIZE,
    output reg  [1:0]   m_axi_AWBURST,
    output reg  [1:0]   m_axi_AWLOCK,
    output reg  [3:0]   m_axi_AWCACHE,
    output reg  [2:0]   m_axi_AWPROT,
    output reg  [3:0]   m_axi_AWQOS,
    output reg  [3:0]   m_axi_AWREGION,
    output reg  [0:0]   m_axi_AWUSER,

    output reg          m_axi_WVALID,
    input  wire         m_axi_WREADY,
    output reg  [DATA_WIDTH-1:0] m_axi_WDATA,
    output reg  [(DATA_WIDTH/8)-1:0] m_axi_WSTRB,
    output reg          m_axi_WLAST,
    output reg  [0:0]   m_axi_WID,
    output reg  [0:0]   m_axi_WUSER,

    input  wire         m_axi_BVALID,
    output reg          m_axi_BREADY,
    input  wire [1:0]   m_axi_BRESP,
    input  wire [0:0]   m_axi_BID,
    input  wire [0:0]   m_axi_BUSER
);
    // 16 bytes/beat (AWSIZE=4) for 128-bit, 32 bytes/beat (AWSIZE=5) for
    // 256-bit. ADDR_W-bit word index idx is byte-addressed by shifting left
    // by log2(bytes-per-beat).
    localparam [2:0] AWSIZE_VAL   = (DATA_WIDTH == 256) ? 3'd5 : 3'd4;
    localparam       ADDR_SHIFT   = (DATA_WIDTH == 256) ? 5 : 4;
    localparam S_IDLE   = 3'd0;
    localparam S_FETCH  = 3'd1;
    localparam S_AW     = 3'd2;
    localparam S_W      = 3'd3;
    localparam S_B      = 3'd4;
    localparam S_DONE   = 3'd5;

    reg [2:0]        state;
    reg [ADDR_W-1:0] idx;

    assign bram_addr = idx;

    always @(posedge clk) begin
        if (!rst_n) begin
            state         <= S_IDLE;
            idx           <= {ADDR_W{1'b0}};
            done          <= 1'b0;
            err           <= 1'b0;
            m_axi_AWVALID <= 1'b0;
            m_axi_WVALID  <= 1'b0;
            m_axi_BREADY  <= 1'b0;
        end else begin
            case (state)
                S_IDLE: begin
                    done <= 1'b0;
                    if (start) begin
                        idx   <= {ADDR_W{1'b0}};
                        state <= S_FETCH;
                    end
                end

                // coeff_bram_stage registers its output one cycle after
                // bram_addr is driven -- idx is already on bram_addr, so
                // one clock here is exactly that latency.
                S_FETCH: begin
                    state <= S_AW;
                end

                S_AW: begin
                    m_axi_AWVALID  <= 1'b1;
                    m_axi_AWADDR   <= BASE_ADDR + ({{(64-ADDR_W-ADDR_SHIFT){1'b0}}, idx} << ADDR_SHIFT);
                    m_axi_AWID     <= 1'b0;
                    m_axi_AWLEN    <= 8'd0;
                    m_axi_AWSIZE   <= AWSIZE_VAL; // 16 or 32 bytes/beat, see DATA_WIDTH
                    m_axi_AWBURST  <= 2'b01;  // INCR
                    m_axi_AWLOCK   <= 2'b00;
                    m_axi_AWCACHE  <= 4'b0000;
                    m_axi_AWPROT   <= 3'b000;
                    m_axi_AWQOS    <= 4'b0000;
                    m_axi_AWREGION <= 4'b0000;
                    m_axi_AWUSER   <= 1'b0;
                    // m_axi_AWVALID read here is its value from before this
                    // edge -- i.e. whatever was actually driven to the slave
                    // last cycle. Gating on it (not just AWREADY) avoids
                    // completing the handshake on the very first cycle of
                    // this state, before AWVALID has been presented at all.
                    if (m_axi_AWVALID && m_axi_AWREADY) begin
                        m_axi_AWVALID <= 1'b0;
                        m_axi_WVALID  <= 1'b1;
                        m_axi_WDATA   <= bram_data;
                        m_axi_WSTRB   <= {(DATA_WIDTH/8){1'b1}};
                        m_axi_WLAST   <= 1'b1;
                        m_axi_WID     <= 1'b0;
                        m_axi_WUSER   <= 1'b0;
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
                        if (idx == WORDS - 1) begin
                            state <= S_DONE;
                        end else begin
                            idx   <= idx + 1'b1;
                            state <= S_FETCH;
                        end
                    end
                end

                S_DONE: begin
                    done <= 1'b1;
                    if (!start) state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end
endmodule
