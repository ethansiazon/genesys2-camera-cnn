// Hardware auto-sequencer: cnn_engine trigger -> poll done -> configure +
// trigger decode_work_heads_0 -> poll done -> capture its 7 BEST_O
// registers -> transmit them over UART. Built 2026-10-29 as the final
// piece toward a self-contained (no JTAG driving each step) CNN+decode+
// UART pipeline. Replaces ap_start_seq_0's role (this module supersedes
// it -- see bd/create_bd.tcl) since it needs AXI-Lite READ capability
// (poll cnn_engine's/decoder's ap_done, capture decoder's results) that
// ap_start_seq.v/copy_fsm.v never needed (write-only).
//
// One-shot, same convention as ap_start_seq.v: runs once when `trigger`
// goes high (copy_fsm_0/done, permanently high after the one-time
// coefficient load), then sits done forever. Re-triggering on a real
// camera frame-ready signal is future work once camera RTL exists (Phase
// 3) -- this proves the CNN+decode+UART chain end-to-end against whatever
// is in feature memory at the time (a JTAG-loaded test photo today, a
// real camera frame later), which is this phase's actual deliverable.
//
// Config values (DecodeConfig's 14 fields) are hardcoded to the identity/
// no-motion/no-association case (DECODER_PREPARED.json's "actualV5zero"
// query) -- appropriate for a single static frame with no ROI remap or
// frame-to-frame tracking, same config scripts/jtag_decode_test.tcl uses
// (and which was validated against the real reference decoder's output on
// real hardware, see docs/PHASE2_LOG.md).
//
// UART framing: one 0xAA sync byte, then the 7 BEST_O registers (28
// bytes), each as 4 bytes LSB-first. Receiver reads one 0xAA then 28
// bytes: bytes[0:3]=x (Q16 s32), [4:7]=y, [8:11]=w, [12:15]=h,
// [16:19]=confidence (Q16 u17 zero-extended), [20:23]=raw_objectness
// (s24 sign-extended), [24:27]={valid at bit16, index in bits[15:0]}.
`timescale 1ns/1ps
module pipeline_seq #(
    parameter [31:0] FEATURE_BASE_ADDR     = 32'h80000000,
    parameter [31:0] COEFFICIENT_BASE_ADDR = 32'h80300000,
    // cnn_engine_0's control block, as seen from this module's own AXI-M
    // master -- confirmed empirically per-master (not assumed the same
    // offset every master sees, see bd/create_bd.tcl's own address-map
    // printout for THIS module after wiring it in).
    parameter [31:0] CNN_CTRL_BASE  = 32'h00000000,
    parameter [31:0] DEC_CTRL_BASE  = 32'h00001000
)(
    input  wire        clk,
    input  wire         rst_n,
    input  wire         trigger,
    output reg          done,
    output reg          err,

    output reg          m_axi_AWVALID,
    input  wire         m_axi_AWREADY,
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
    input  wire [0:0]   m_axi_BID,

    output reg          m_axi_ARVALID,
    input  wire         m_axi_ARREADY,
    output reg  [31:0]  m_axi_ARADDR,
    output reg  [0:0]   m_axi_ARID,
    output reg  [7:0]   m_axi_ARLEN,
    output reg  [2:0]   m_axi_ARSIZE,
    output reg  [1:0]   m_axi_ARBURST,

    input  wire         m_axi_RVALID,
    output reg          m_axi_RREADY,
    input  wire [31:0]  m_axi_RDATA,
    input  wire         m_axi_RLAST,
    input  wire [1:0]   m_axi_RRESP,
    input  wire [0:0]   m_axi_RID,

    // UART byte-transmit handshake (cnn_subsystem_top.v drives uart_tx
    // itself; this module just feeds it bytes).
    output reg  [7:0]   uart_data,
    output reg          uart_stb,
    input  wire         uart_busy
);
    localparam ADDR_AP_CTRL         = 8'h00;
    localparam ADDR_FEATURES_DATA_0 = 8'h10;
    localparam ADDR_FEATURES_DATA_1 = 8'h14;
    localparam ADDR_COEFFICIENTS_DATA_0 = 8'h1c;
    localparam ADDR_COEFFICIENTS_DATA_1 = 8'h20;
    localparam ADDR_DEC_CFG_DATA_0  = 8'h1c;
    localparam ADDR_DEC_BEST_O_DATA_0 = 8'h78;

    // Program: {kind[1:0], addr[31:0], data[31:0]}. kind: 0=WRITE,
    // 1=POLL (bit1 of read data), 2=CAPTURE (store read data).
    localparam K_WRITE   = 2'd0;
    localparam K_POLL    = 2'd1;
    localparam K_CAPTURE = 2'd2;

    localparam PROG_LEN = 31;
    reg [1:0]  k_kind [0:PROG_LEN-1];
    reg [31:0] k_addr [0:PROG_LEN-1];
    reg [31:0] k_data [0:PROG_LEN-1];
    integer i;
    initial begin
        k_kind[0]=K_WRITE; k_addr[0]=CNN_CTRL_BASE+ADDR_FEATURES_DATA_0;     k_data[0]=FEATURE_BASE_ADDR;
        k_kind[1]=K_WRITE; k_addr[1]=CNN_CTRL_BASE+ADDR_FEATURES_DATA_1;     k_data[1]=32'd0;
        k_kind[2]=K_WRITE; k_addr[2]=CNN_CTRL_BASE+ADDR_COEFFICIENTS_DATA_0; k_data[2]=COEFFICIENT_BASE_ADDR;
        k_kind[3]=K_WRITE; k_addr[3]=CNN_CTRL_BASE+ADDR_COEFFICIENTS_DATA_1; k_data[3]=32'd0;
        k_kind[4]=K_WRITE; k_addr[4]=CNN_CTRL_BASE+ADDR_AP_CTRL;             k_data[4]=32'd1;
        k_kind[5]=K_POLL;  k_addr[5]=CNN_CTRL_BASE+ADDR_AP_CTRL;             k_data[5]=32'd0;

        k_kind[6]=K_WRITE;  k_addr[6]=DEC_CTRL_BASE+ADDR_FEATURES_DATA_0;      k_data[6]=FEATURE_BASE_ADDR;
        k_kind[7]=K_WRITE;  k_addr[7]=DEC_CTRL_BASE+ADDR_FEATURES_DATA_1;      k_data[7]=32'd0;
        k_kind[8]=K_WRITE;  k_addr[8]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h00; k_data[8]=32'd65536;  // sx
        k_kind[9]=K_WRITE;  k_addr[9]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h04; k_data[9]=32'd65536;  // sy
        k_kind[10]=K_WRITE; k_addr[10]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h08; k_data[10]=32'd0;     // ox
        k_kind[11]=K_WRITE; k_addr[11]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h0c; k_data[11]=32'd0;     // oy
        k_kind[12]=K_WRITE; k_addr[12]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h10; k_data[12]=32'd0;     // u
        k_kind[13]=K_WRITE; k_addr[13]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h14; k_data[13]=32'd0;     // v
        k_kind[14]=K_WRITE; k_addr[14]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h18; k_data[14]=32'd524288; // mx
        k_kind[15]=K_WRITE; k_addr[15]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h1c; k_data[15]=32'd524288; // my
        k_kind[16]=K_WRITE; k_addr[16]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h20; k_data[16]=32'd0;     // use_motion
        k_kind[17]=K_WRITE; k_addr[17]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h24; k_data[17]=32'd0;     // rx
        k_kind[18]=K_WRITE; k_addr[18]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h28; k_data[18]=32'd0;     // ry
        k_kind[19]=K_WRITE; k_addr[19]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h2c; k_data[19]=32'd0;     // rw
        k_kind[20]=K_WRITE; k_addr[20]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h30; k_data[20]=32'd0;     // rh
        k_kind[21]=K_WRITE; k_addr[21]=DEC_CTRL_BASE+ADDR_DEC_CFG_DATA_0+8'h34; k_data[21]=32'd0;     // use_association
        k_kind[22]=K_WRITE; k_addr[22]=DEC_CTRL_BASE+ADDR_AP_CTRL;             k_data[22]=32'd1;
        k_kind[23]=K_POLL;  k_addr[23]=DEC_CTRL_BASE+ADDR_AP_CTRL;             k_data[23]=32'd0;

        for (i = 0; i < 7; i = i + 1) begin
            k_kind[24+i] = K_CAPTURE;
            k_addr[24+i] = DEC_CTRL_BASE + ADDR_DEC_BEST_O_DATA_0 + i*4;
            k_data[24+i] = 32'd0;
        end
    end

    // 4'd, not 3'd: 9 states (0-8) don't fit in 3 bits. The bug this fixes
    // was in these literals themselves, not just the `state` register's
    // declared width -- a localparam's value truncates to its own literal
    // width at the point of declaration, independent of whatever register
    // it's later assigned to. `3'd8` truncated to 0 here, silently
    // colliding S_UART with S_IDLE. See `state`'s declaration comment for
    // the full real-hardware symptom this produced.
    localparam S_IDLE       = 4'd0;
    localparam S_AW         = 4'd1;
    localparam S_W          = 4'd2;
    localparam S_B          = 4'd3;
    localparam S_AR         = 4'd4;
    localparam S_R          = 4'd5;
    localparam S_NEXT       = 4'd6;
    localparam S_UART_SYNC  = 4'd7;
    localparam S_UART       = 4'd8;

    // BUG FOUND AND FIXED (2026-10-29, batch-eval fork): this was `reg
    // [2:0] state` (3 bits, states 0-7), but 9 states are defined,
    // including `S_UART = 3'd8`. The literal `3'd8`'s explicit 3-bit
    // width truncates 8 to 0 -- S_UART's encoded value collided with
    // S_IDLE's. Confirmed on real hardware, not by inspection: cnn_engine's
    // AP_CTRL was observed cycling ap_start=1 -> idle=1 (briefly) ->
    // ap_start=1 -> ... forever, completely independent of any external
    // write -- once the FSM reached the (mis-encoded) S_UART state, S_IDLE's
    // own logic saw `trigger` still permanently high (copy_fsm_0/done never
    // deasserts) and restarted the whole program from pc=0, every cycle.
    // 4 bits covers 0-8 with room to spare.
    reg [3:0] state;
    reg [5:0] pc;
    reg [31:0] capture [0:6];
    reg [2:0] uart_word;
    reg [1:0] uart_byte;
    reg       done_pulse;

    always @(posedge clk) begin
        if (!rst_n) begin
            state <= S_IDLE; pc <= 6'd0; done <= 1'b0; err <= 1'b0;
            m_axi_AWVALID <= 1'b0; m_axi_WVALID <= 1'b0; m_axi_BREADY <= 1'b0;
            m_axi_ARVALID <= 1'b0; m_axi_RREADY <= 1'b0;
            uart_stb <= 1'b0; uart_word <= 3'd0; uart_byte <= 2'd0;
        end else begin
            uart_stb <= 1'b0;
            case (state)
                S_IDLE: begin
                    done <= 1'b0;
                    if (trigger) begin pc <= 6'd0; state <= (k_kind[0]==K_WRITE) ? S_AW : S_AR; end
                end

                S_AW: begin
                    m_axi_AWVALID <= 1'b1;
                    m_axi_AWADDR  <= k_addr[pc];
                    m_axi_AWID    <= 1'b0; m_axi_AWLEN <= 8'd0; m_axi_AWSIZE <= 3'd2; m_axi_AWBURST <= 2'b01;
                    if (m_axi_AWVALID && m_axi_AWREADY) begin
                        m_axi_AWVALID <= 1'b0;
                        m_axi_WVALID  <= 1'b1;
                        m_axi_WDATA   <= k_data[pc];
                        m_axi_WSTRB   <= 4'hF; m_axi_WLAST <= 1'b1; m_axi_WID <= 1'b0;
                        state <= S_W;
                    end
                end
                S_W: begin
                    if (m_axi_WVALID && m_axi_WREADY) begin
                        m_axi_WVALID <= 1'b0; m_axi_BREADY <= 1'b1; state <= S_B;
                    end
                end
                S_B: begin
                    if (m_axi_BREADY && m_axi_BVALID) begin
                        m_axi_BREADY <= 1'b0;
                        if (m_axi_BRESP != 2'b00) err <= 1'b1;
                        state <= S_NEXT;
                    end
                end

                S_AR: begin
                    m_axi_ARVALID <= 1'b1;
                    m_axi_ARADDR  <= k_addr[pc];
                    m_axi_ARID    <= 1'b0; m_axi_ARLEN <= 8'd0; m_axi_ARSIZE <= 3'd2; m_axi_ARBURST <= 2'b01;
                    if (m_axi_ARVALID && m_axi_ARREADY) begin
                        m_axi_ARVALID <= 1'b0; m_axi_RREADY <= 1'b1; state <= S_R;
                    end
                end
                S_R: begin
                    if (m_axi_RREADY && m_axi_RVALID) begin
                        m_axi_RREADY <= 1'b0;
                        if (m_axi_RRESP != 2'b00) err <= 1'b1;
                        if (k_kind[pc] == K_POLL) begin
                            if (m_axi_RDATA[1]) state <= S_NEXT; else state <= S_AR; // retry poll
                        end else begin // K_CAPTURE
                            capture[pc-24] <= m_axi_RDATA;
                            state <= S_NEXT;
                        end
                    end
                end

                S_NEXT: begin
                    if (pc == PROG_LEN - 1) begin
                        state <= S_UART_SYNC; uart_word <= 3'd0; uart_byte <= 2'd0;
                    end else begin
                        pc <= pc + 6'd1;
                        state <= (k_kind[pc+1] == K_WRITE) ? S_AW : S_AR;
                    end
                end

                S_UART_SYNC: begin
                    if (!uart_busy && !uart_stb) begin
                        uart_data <= 8'hAA;
                        uart_stb  <= 1'b1;
                        state     <= S_UART;
                    end
                end

                S_UART: begin
                    if (uart_word == 3'd7) begin
                        done <= 1'b1;
                        if (!trigger) state <= S_IDLE;
                    end else if (!uart_busy && !uart_stb) begin
                        uart_data <= capture[uart_word][uart_byte*8 +: 8];
                        uart_stb  <= 1'b1;
                        if (uart_byte == 2'd3) begin uart_byte <= 2'd0; uart_word <= uart_word + 3'd1; end
                        else uart_byte <= uart_byte + 2'd1;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end
endmodule
