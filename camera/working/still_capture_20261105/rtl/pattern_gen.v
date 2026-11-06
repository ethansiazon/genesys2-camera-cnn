// -----------------------------------------------------------------------------
// pattern_gen -- purely combinational test pattern in 320x240 logical space.
//
// Deliberately combinational and side-effect free so the same block can be
// instantiated twice in different clock domains: once on the VGA read side
// (direct mode) and once on the frame-buffer write side. That avoids any CDC.
//
// mode 0 -- COLOUR BARS + PER-CHANNEL RAMPS
//   y   0..175 : 8 vertical bars, 40 px each, in the same order the OV5640's
//                own test-bar mode emits (white yellow cyan green magenta red
//                blue black) so the two can be compared directly later.
//   y 176..239 : four 16-row ramp strips, 16 steps of 16 px, x 32..287:
//                grey, then red, then green, then blue.
//                This is the part that proves all 12 VGA pins work -- each
//                strip walks one channel through all 16 levels, so a dead or
//                swapped bit shows up as a missing or mis-ordered step.
//
// mode 1 -- GEOMETRY / ALIGNMENT GRID
//   1 px white border, red 8x8 corner markers, green centre crosshair, dim
//   16 px grid. Proves no rows or columns are lost at the edges and that the
//   2x pixel doubling lands square.
//
// offset shifts the bars horizontally (wraps at 320) so a live pattern can be
// told apart from a frozen one.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module pattern_gen (
    input  wire [8:0]  x,        // 0..319
    input  wire [7:0]  y,        // 0..239
    input  wire        mode,     // 0 = bars+ramps, 1 = geometry grid
    input  wire [8:0]  offset,   // 0..319, horizontal shift of the bars
    output wire [11:0] rgb       // {R[3:0], G[3:0], B[3:0]}
);
    // ---------------- mode 0: colour bars ----------------
    wire [9:0] xs_raw = {1'b0, x} + {1'b0, offset};             // max 638
    wire [8:0] xs     = (xs_raw >= 10'd320) ? (xs_raw - 10'd320) : xs_raw[8:0];

    wire [2:0] bar = (xs <  9'd40)  ? 3'd0 :
                     (xs <  9'd80)  ? 3'd1 :
                     (xs < 9'd120)  ? 3'd2 :
                     (xs < 9'd160)  ? 3'd3 :
                     (xs < 9'd200)  ? 3'd4 :
                     (xs < 9'd240)  ? 3'd5 :
                     (xs < 9'd280)  ? 3'd6 : 3'd7;

    reg [11:0] bar_rgb;
    always @* begin
        case (bar)
            3'd0: bar_rgb = 12'hFFF;   // white
            3'd1: bar_rgb = 12'hFF0;   // yellow
            3'd2: bar_rgb = 12'h0FF;   // cyan
            3'd3: bar_rgb = 12'h0F0;   // green
            3'd4: bar_rgb = 12'hF0F;   // magenta
            3'd5: bar_rgb = 12'hF00;   // red
            3'd6: bar_rgb = 12'h00F;   // blue
            3'd7: bar_rgb = 12'h000;   // black
        endcase
    end

    // ---------------- mode 0: per-channel ramps ----------------
    wire       in_ramps  = (y >= 8'd176);
    wire [7:0] ry        = y - 8'd176;        // 0..63
    wire [1:0] strip     = ry[5:4];           // which of the four strips
    wire       in_ramp_x = (x >= 9'd32) && (x < 9'd288);
    wire [8:0] rx        = x - 9'd32;         // 0..255
    wire [3:0] lvl       = rx[7:4];           // 16 steps of 16 px

    reg [11:0] ramp_rgb;
    always @* begin
        if (!in_ramp_x) begin
            ramp_rgb = 12'h000;
        end else begin
            case (strip)
                2'd0: ramp_rgb = {lvl,  lvl,  lvl };   // grey
                2'd1: ramp_rgb = {lvl,  4'h0, 4'h0};   // red
                2'd2: ramp_rgb = {4'h0, lvl,  4'h0};   // green
                2'd3: ramp_rgb = {4'h0, 4'h0, lvl };   // blue
            endcase
        end
    end

    wire [11:0] mode0_rgb = in_ramps ? ramp_rgb : bar_rgb;

    // ---------------- mode 1: geometry grid ----------------
    wire corner = ((x < 9'd8) || (x > 9'd311)) && ((y < 8'd8) || (y > 8'd231));
    wire border = (x == 9'd0) || (x == 9'd319) || (y == 8'd0) || (y == 8'd239);
    wire crosshair = (x == 9'd160) || (y == 8'd120);
    wire grid   = (x[3:0] == 4'd0) || (y[3:0] == 4'd0);

    reg [11:0] geo_rgb;
    always @* begin
        if      (corner) geo_rgb = 12'hF00;   // red 8x8 corner markers
        else if (border) geo_rgb = 12'hFFF;   // white 1 px border
        else if (crosshair) geo_rgb = 12'h0F0; // green centre crosshair
        else if (grid)   geo_rgb = 12'h444;   // dim 16 px grid
        else             geo_rgb = 12'h000;
    end

    assign rgb = mode ? geo_rgb : mode0_rgb;
endmodule

`default_nettype wire
