// -----------------------------------------------------------------------------
// hdmi_out -- 24-bit RGB to three TMDS pairs plus a TMDS clock pair.
//
// DVI-compatible: video only, no audio and no infoframes. Every HDMI sink
// accepts this, because DVI is the subset HDMI was built around. Adding real
// HDMI would mean data islands and an AVI infoframe, which buys nothing here.
//
// Serialisation is 10:1 DDR. A single OSERDESE2 does at most 8:1, so each
// channel needs a MASTER/SLAVE pair joined through SHIFTIN/SHIFTOUT -- the
// slave contributes bits 8 and 9 on its D3/D4 inputs, which is the fixed
// wiring the primitive expects, not an arbitrary choice.
//
// The clock channel is serialised through an identical path carrying the
// constant pattern 1111100000 rather than being forwarded with an ODDR. Same
// primitive, same delay, so the clock stays aligned with the data instead of
// skewing by whatever the two different paths happen to differ by.
//
// Clocks: clk_pix is the pixel rate, clk_pix5x is exactly 5x it. DDR makes
// that 10 bits per pixel. At 640x480 that is 25 MHz and 125 MHz, so 250 Mb/s
// per pair -- well inside Kintex-7's OSERDESE2 limits, no cascading needed
// beyond the 10:1 pair itself.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module hdmi_out (
    input  wire       clk_pix,
    input  wire       clk_pix5x,
    input  wire       rst,
    input  wire [7:0] red,
    input  wire [7:0] green,
    input  wire [7:0] blue,
    input  wire       hsync,     // actual sync level, negative polarity for VGA
    input  wire       vsync,
    input  wire       de,        // active video
    output wire [2:0] tmds_p,
    output wire [2:0] tmds_n,
    output wire       tmds_clk_p,
    output wire       tmds_clk_n
);
    // ---- encode ----
    // Only channel 0 carries the syncs. Channels 1 and 2 send c = 00 during
    // blanking; a sink that sees sync pulses on green or red will not lock.
    wire [9:0] sym_b, sym_g, sym_r;

    tmds_encoder enc_b (.clk(clk_pix), .rst(rst), .d(blue),
                        .c({vsync, hsync}), .de(de), .q(sym_b));
    tmds_encoder enc_g (.clk(clk_pix), .rst(rst), .d(green),
                        .c(2'b00),          .de(de), .q(sym_g));
    tmds_encoder enc_r (.clk(clk_pix), .rst(rst), .d(red),
                        .c(2'b00),          .de(de), .q(sym_r));

    // ---- serialise ----
    wire [9:0] sym [0:3];
    assign sym[0] = sym_b;
    assign sym[1] = sym_g;
    assign sym[2] = sym_r;
    assign sym[3] = 10'b1111100000;   // the clock channel

    wire [3:0] ser;

    genvar i;
    generate
        for (i = 0; i < 4; i = i + 1) begin : g_ser
            wire sh1, sh2;

            OSERDESE2 #(
                .DATA_RATE_OQ("DDR"), .DATA_RATE_TQ("SDR"),
                .DATA_WIDTH(10), .TRISTATE_WIDTH(1),
                .SERDES_MODE("MASTER")
            ) ser_m (
                .OQ(ser[i]),
                .CLK(clk_pix5x), .CLKDIV(clk_pix), .RST(rst),
                .D1(sym[i][0]), .D2(sym[i][1]), .D3(sym[i][2]), .D4(sym[i][3]),
                .D5(sym[i][4]), .D6(sym[i][5]), .D7(sym[i][6]), .D8(sym[i][7]),
                .SHIFTIN1(sh1), .SHIFTIN2(sh2),
                .SHIFTOUT1(), .SHIFTOUT2(),
                .OCE(1'b1), .TCE(1'b0), .TBYTEIN(1'b0), .TBYTEOUT(),
                .T1(1'b0), .T2(1'b0), .T3(1'b0), .T4(1'b0), .TQ(), .OFB(), .TFB()
            );

            OSERDESE2 #(
                .DATA_RATE_OQ("DDR"), .DATA_RATE_TQ("SDR"),
                .DATA_WIDTH(10), .TRISTATE_WIDTH(1),
                .SERDES_MODE("SLAVE")
            ) ser_s (
                .OQ(),
                .CLK(clk_pix5x), .CLKDIV(clk_pix), .RST(rst),
                // bits 8 and 9 go on D3/D4 of the slave -- fixed by the primitive
                .D1(1'b0), .D2(1'b0), .D3(sym[i][8]), .D4(sym[i][9]),
                .D5(1'b0), .D6(1'b0), .D7(1'b0), .D8(1'b0),
                .SHIFTIN1(1'b0), .SHIFTIN2(1'b0),
                .SHIFTOUT1(sh1), .SHIFTOUT2(sh2),
                .OCE(1'b1), .TCE(1'b0), .TBYTEIN(1'b0), .TBYTEOUT(),
                .T1(1'b0), .T2(1'b0), .T3(1'b0), .T4(1'b0), .TQ(), .OFB(), .TFB()
            );
        end
    endgenerate

    // ---- drive the pairs ----
    OBUFDS obuf_b   (.I(ser[0]), .O(tmds_p[0]),   .OB(tmds_n[0]));
    OBUFDS obuf_g   (.I(ser[1]), .O(tmds_p[1]),   .OB(tmds_n[1]));
    OBUFDS obuf_r   (.I(ser[2]), .O(tmds_p[2]),   .OB(tmds_n[2]));
    OBUFDS obuf_clk (.I(ser[3]), .O(tmds_clk_p),  .OB(tmds_clk_n));
endmodule

`default_nettype wire
