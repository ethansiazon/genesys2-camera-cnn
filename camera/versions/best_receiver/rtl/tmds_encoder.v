// -----------------------------------------------------------------------------
// tmds_encoder -- the DVI 1.0 / HDMI transition-minimised encoder, one channel.
//
// 8 bits of pixel data in, 10 bits of serial symbol out, one pixel clock of
// latency. Two stages, exactly as the spec defines them:
//
//   1. TRANSITION MINIMISATION. XOR or XNOR chain across the byte, whichever
//      produces fewer transitions on the wire. q_m[8] records which was used,
//      so the receiver can undo it.
//   2. DC BALANCE. A running disparity counter decides whether to send the
//      9-bit word as-is or inverted, keeping the average number of ones near
//      half. Without this the AC-coupled receiver drifts and loses lock.
//
// During blanking (de == 0) the data path is bypassed entirely and one of four
// fixed control symbols is sent, carrying the two control bits. These symbols
// have 7 transitions each -- deliberately MORE than any data symbol can have,
// which is how the receiver finds symbol boundaries and distinguishes control
// periods from active video. The running disparity resets during control.
//
// Channel/control mapping for DVI, set by the instantiating module:
//   channel 0 (blue)  c1 = vsync, c0 = hsync
//   channel 1 (green) c1 = 0,     c0 = 0
//   channel 2 (red)   c1 = 0,     c0 = 0
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module tmds_encoder (
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] d,       // pixel data for this channel
    input  wire [1:0] c,       // control bits, used only while !de
    input  wire       de,      // 1 = active video, 0 = blanking
    output reg  [9:0] q        // encoded symbol
);
    // ---- stage 1: transition minimisation ----
    wire [3:0] n1_d = d[0] + d[1] + d[2] + d[3] + d[4] + d[5] + d[6] + d[7];

    // XNOR when the byte is mostly ones, XOR when mostly zeros. The tie at
    // exactly four ones is broken by d[0], which the spec fixes so that encoder
    // and decoder agree; picking the other way here still "works" visually but
    // violates the standard and can fail on a strict sink.
    wire use_xnor = (n1_d > 4'd4) || ((n1_d == 4'd4) && (d[0] == 1'b0));

    wire [8:0] q_m;
    assign q_m[0] = d[0];
    assign q_m[1] = use_xnor ? ~(q_m[0] ^ d[1]) : (q_m[0] ^ d[1]);
    assign q_m[2] = use_xnor ? ~(q_m[1] ^ d[2]) : (q_m[1] ^ d[2]);
    assign q_m[3] = use_xnor ? ~(q_m[2] ^ d[3]) : (q_m[2] ^ d[3]);
    assign q_m[4] = use_xnor ? ~(q_m[3] ^ d[4]) : (q_m[3] ^ d[4]);
    assign q_m[5] = use_xnor ? ~(q_m[4] ^ d[5]) : (q_m[4] ^ d[5]);
    assign q_m[6] = use_xnor ? ~(q_m[5] ^ d[6]) : (q_m[5] ^ d[6]);
    assign q_m[7] = use_xnor ? ~(q_m[6] ^ d[7]) : (q_m[6] ^ d[7]);
    assign q_m[8] = use_xnor ? 1'b0 : 1'b1;

    // ---- stage 2: DC balance ----
    wire [3:0] n1_qm = q_m[0] + q_m[1] + q_m[2] + q_m[3]
                     + q_m[4] + q_m[5] + q_m[6] + q_m[7];

    // ones minus zeros over the 8 data bits. n0 = 8 - n1, so the difference is
    // 2*n1 - 8. Written out rather than as (n1 - n0) because the subtraction of
    // two unsigned 4-bit values underflows and widens instead of going negative
    // -- the same class of bug that once made the luma SAD read 14x its maximum.
    wire signed [5:0] imbalance = $signed({2'b00, n1_qm}) - 6'sd4; // (n1-n0)/2
    wire              balanced  = (n1_qm == 4'd4);

    reg signed [5:0] cnt = 6'sd0;   // running disparity, in units of 1 bit

    wire take_branch1 = (cnt == 6'sd0) || balanced;
    wire take_invert  = ((cnt > 6'sd0) && (n1_qm > 4'd4)) ||
                        ((cnt < 6'sd0) && (n1_qm < 4'd4));

    always @(posedge clk) begin
        if (rst) begin
            q   <= 10'b0;
            cnt <= 6'sd0;
        end else if (!de) begin
            // Control period. Fixed symbols, disparity reset.
            case (c)
                2'b00: q <= 10'b1101010100;
                2'b01: q <= 10'b0010101011;
                2'b10: q <= 10'b0101010100;
                2'b11: q <= 10'b1010101011;
            endcase
            cnt <= 6'sd0;
        end else if (take_branch1) begin
            q[9]   <= ~q_m[8];
            q[8]   <=  q_m[8];
            q[7:0] <=  q_m[8] ? q_m[7:0] : ~q_m[7:0];
            // +2*imbalance is (n1-n0); sign depends on whether we inverted
            cnt <= q_m[8] ? (cnt + (imbalance <<< 1))
                          : (cnt - (imbalance <<< 1));
        end else if (take_invert) begin
            q[9]   <= 1'b1;
            q[8]   <= q_m[8];
            q[7:0] <= ~q_m[7:0];
            cnt <= cnt + {4'b0, q_m[8], 1'b0} - (imbalance <<< 1);
        end else begin
            q[9]   <= 1'b0;
            q[8]   <= q_m[8];
            q[7:0] <= q_m[7:0];
            cnt <= cnt - {4'b0, ~q_m[8], 1'b0} + (imbalance <<< 1);
        end
    end
endmodule

`default_nettype wire
