// -----------------------------------------------------------------------------
// ycbcr2rgb -- ITU-R BT.601 colour space conversion, 2-cycle pipeline.
//
// The OV5640's ISP emits YUV422, which is what lets us carry 8-bit luma over
// the same 2-bytes-per-pixel DVP rate that RGB565 used. HDMI wants RGB, so the
// conversion happens here rather than on the wire.
//
// TWO COEFFICIENT SETS, selected by `full_range`:
//
//   studio swing (full_range = 0)   Y 16..235, C 16..240   ITU-R BT.601
//       R = 1.164(Y-16)                  + 1.596(Cr-128)
//       G = 1.164(Y-16) - 0.391(Cb-128)  - 0.813(Cr-128)
//       B = 1.164(Y-16) + 2.018(Cb-128)
//
//   full range  (full_range = 1)    Y 0..255               JFIF
//       R = Y                            + 1.402(Cr-128)
//       G = Y           - 0.344(Cb-128)  - 0.714(Cr-128)
//       B = Y           + 1.772(Cb-128)
//
// Which one the sensor actually emits depends on ISP registers that are not
// worth guessing at from a datasheet -- the symptom of choosing wrong is a
// picture that looks washed out (studio data decoded as full) or crushed at
// both ends (full data decoded as studio). It is wired to a switch so the
// answer can be found on the board in two seconds instead of two rebuilds.
//
// Coefficients are the conventional 8-bit-scaled integers; the +128 before the
// shift is round-to-nearest, not truncation. Truncating here would bias every
// channel downward by half a code, which on an 8-bit output is invisible but on
// a 4-bit one is not -- the same mistake measured at 1.5 codes of darkening in
// the Basys 3 temporal blend.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module ycbcr2rgb (
    input  wire        clk,
    input  wire        rst,
    input  wire        full_range,
    input  wire [7:0]  y,
    input  wire [7:0]  cb,
    input  wire [7:0]  cr,
    input  wire        valid_i,
    output reg  [7:0]  r,
    output reg  [7:0]  g,
    output reg  [7:0]  b,
    output reg         valid_o      // valid_i delayed by the 2-cycle pipeline
);
    // ---- coefficient select ----
    wire signed [10:0] k_y    = full_range ? 11'sd256 : 11'sd298;
    wire signed [10:0] k_cr_r = full_range ? 11'sd359 : 11'sd409;
    wire signed [10:0] k_cr_g = full_range ? 11'sd183 : 11'sd208;
    wire signed [10:0] k_cb_g = full_range ? 11'sd88  : 11'sd100;
    wire signed [10:0] k_cb_b = full_range ? 11'sd454 : 11'sd516;
    wire signed [10:0] y_off  = full_range ? 11'sd0   : 11'sd16;

    wire signed [10:0] yd  = $signed({3'b000, y})  - y_off;
    wire signed [10:0] cbd = $signed({3'b000, cb}) - 11'sd128;
    wire signed [10:0] crd = $signed({3'b000, cr}) - 11'sd128;

    // ---- stage 1: the multiplies ----
    reg signed [21:0] s1_y, s1_cr_r, s1_cr_g, s1_cb_g, s1_cb_b;
    reg               s1_valid;

    always @(posedge clk) begin
        if (rst) begin
            s1_y <= 0; s1_cr_r <= 0; s1_cr_g <= 0; s1_cb_g <= 0; s1_cb_b <= 0;
            s1_valid <= 1'b0;
        end else begin
            s1_y    <= k_y    * yd;
            s1_cr_r <= k_cr_r * crd;
            s1_cr_g <= k_cr_g * crd;
            s1_cb_g <= k_cb_g * cbd;
            s1_cb_b <= k_cb_b * cbd;
            s1_valid <= valid_i;
        end
    end

    // ---- stage 2: sum, round, shift, clamp ----
    wire signed [21:0] sum_r = s1_y + s1_cr_r               + 22'sd128;
    wire signed [21:0] sum_g = s1_y - s1_cr_g - s1_cb_g     + 22'sd128;
    wire signed [21:0] sum_b = s1_y + s1_cb_b               + 22'sd128;

    function [7:0] clamp8;
        input signed [21:0] v;
        reg signed [21:0] sh;
        begin
            sh = v >>> 8;
            if      (sh < 0)          clamp8 = 8'h00;
            else if (sh > 22'sd255)   clamp8 = 8'hFF;
            else                      clamp8 = sh[7:0];
        end
    endfunction

    always @(posedge clk) begin
        if (rst) begin
            r <= 8'h00; g <= 8'h00; b <= 8'h00; valid_o <= 1'b0;
        end else begin
            r <= clamp8(sum_r);
            g <= clamp8(sum_g);
            b <= clamp8(sum_b);
            valid_o <= s1_valid;
        end
    end
endmodule

`default_nettype wire
