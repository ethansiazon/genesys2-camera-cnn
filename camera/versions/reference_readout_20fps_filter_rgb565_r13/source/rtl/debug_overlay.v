// -----------------------------------------------------------------------------
// debug_overlay -- status readable from across the room.
//
// The Basys 3's LEDs and seven-segment display are useless when the only
// instrument pointed at the bench is a webcam that can see the monitor and
// nothing else. So every diagnostic is drawn ON SCREEN as large colour blocks.
//
// Layout in 320x240 logical space:
//   rows   0.. 23  16 blocks x 20 px : chip ID bits, MSB left. green=1 red=0.
//                                      0x5640 reads  0101 0110 0100 0000
//   rows  24.. 47   8 blocks x 40 px : per-data-line toggle. green=alive red=stuck
//   rows  48.. 71   8 blocks x 40 px : status flags, see below
//   rows  72..231                      camera image from the frame buffer
//   rows 232..239   8 bars  x 40 px  : fixed colour reference, drawn HERE and not
//                                      from the buffer, so it proves the VGA path
//                                      is alive even when capture is completely dead
//
// status[7:0] = {2'b0, frame_moving, href_seen, sccb_ok, id_valid, init_done, pclk_alive}
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module debug_overlay (
    input  wire [8:0]  x,            // 0..319
    input  wire [7:0]  y,            // 0..239
    input  wire [15:0] chip_id,
    input  wire [7:0]  d_alive,
    input  wire [7:0]  status,
    input  wire [15:0] pix_per_frame,   // pixels written per frame, [19:4]
    input  wire [15:0] x_max,           // raw sensor line length - 1
    input  wire [15:0] y_max,           // raw sensor line count  - 1
    output wire        is_overlay,   // 1 = overlay owns this pixel
    output reg  [11:0] rgb
);
    localparam [11:0] GREEN = 12'h0F0;
    localparam [11:0] RED   = 12'hF00;

    wire in_id     = (y < 8'd24);
    wire in_dlines = (y >= 8'd24)  && (y < 8'd48);
    wire in_status = (y >= 8'd48)  && (y < 8'd72);
    wire in_cnt    = (y >= 8'd72)  && (y < 8'd96);
    wire in_xmax   = (y >= 8'd96)  && (y < 8'd120);
    wire in_ymax   = (y >= 8'd120) && (y < 8'd144);
    wire in_ref    = (y >= 8'd232);

    assign is_overlay = in_id || in_dlines || in_status
                     || in_cnt || in_xmax || in_ymax || in_ref;

    // 16 cells of 20 px, MSB on the left
    wire [3:0] id_cell = x[8:0] / 9'd20;
    wire       id_bit  = chip_id[4'd15 - id_cell];

    // Proportional bars instead of binary cells. Reading 16 small cells off a
    // webcam photo of an angled screen in a dark room proved unreliable -- it
    // caused a misread earlier. A bar length is unambiguous at any angle.
    // Each is scaled so a CORRECT QVGA frame fills the full 320 px width:
    //   x_max 319  -> full      (sensor line length)
    //   y_max 239  -> 320*239/240 ~ full
    //   76800 px/frame -> full  (pix_per_frame is already >>4, so /15 ~ /240)
    wire [15:0] cnt_scaled = pix_per_frame / 16'd15;
    wire [9:0]  bar_cnt = (cnt_scaled > 16'd319) ? 10'd319 : cnt_scaled[9:0];
    wire [9:0]  bar_xm  = (x_max > 16'd319) ? 10'd319 : x_max[9:0];
    wire [15:0] ym_scaled = (y_max * 16'd4) / 16'd3;
    wire [9:0]  bar_ym  = (ym_scaled > 16'd319) ? 10'd319 : ym_scaled[9:0];

    // tick marks every 32 px so the bar can be read quantitatively
    wire tick = (x[4:0] == 5'd0);

    // 8 cells of 40 px, bit 7 on the left
    wire [2:0] cell8    = (x < 9'd40)  ? 3'd0 :
                          (x < 9'd80)  ? 3'd1 :
                          (x < 9'd120) ? 3'd2 :
                          (x < 9'd160) ? 3'd3 :
                          (x < 9'd200) ? 3'd4 :
                          (x < 9'd240) ? 3'd5 :
                          (x < 9'd280) ? 3'd6 : 3'd7;

    wire d_bit = d_alive[3'd7 - cell8];
    wire s_bit = status [3'd7 - cell8];

    reg [11:0] ref_rgb;
    always @* begin
        case (cell8)
            3'd0: ref_rgb = 12'hFFF;
            3'd1: ref_rgb = 12'hFF0;
            3'd2: ref_rgb = 12'h0FF;
            3'd3: ref_rgb = 12'h0F0;
            3'd4: ref_rgb = 12'hF0F;
            3'd5: ref_rgb = 12'hF00;
            3'd6: ref_rgb = 12'h00F;
            3'd7: ref_rgb = 12'h444;   // grey, not black -- a black cell here is
        endcase                        // indistinguishable from a dead display
    end

    // 2 px dark gutter between cells so block boundaries stay countable on camera
    wire gutter_20 = (x % 9'd20) < 9'd2;
    wire gutter_40 = ((x < 9'd40)  ? x :
                      (x < 9'd80)  ? x - 9'd40  :
                      (x < 9'd120) ? x - 9'd80  :
                      (x < 9'd160) ? x - 9'd120 :
                      (x < 9'd200) ? x - 9'd160 :
                      (x < 9'd240) ? x - 9'd200 :
                      (x < 9'd280) ? x - 9'd240 : x - 9'd280) < 9'd2;
    wire row_gap = (y[3:0] == 4'd0) && !in_ref;   // thin seam between stripes

    always @* begin
        if (in_id)           rgb = (gutter_20 || row_gap) ? 12'h000 : (id_bit  ? GREEN : RED);
        else if (in_dlines)  rgb = (gutter_40 || row_gap) ? 12'h000 : (d_bit   ? GREEN : RED);
        else if (in_status)  rgb = (gutter_40 || row_gap) ? 12'h000 : (s_bit   ? GREEN : RED);
        // three 16-bit numeric rows, tinted so they are not mistaken for flags
        else if (in_cnt)     rgb = ({1'b0,x} < bar_cnt) ? 12'h0FF : (tick ? 12'h044 : 12'h011);
        else if (in_xmax)    rgb = ({1'b0,x} < bar_xm ) ? 12'hFF0 : (tick ? 12'h440 : 12'h110);
        else if (in_ymax)    rgb = ({1'b0,x} < bar_ym ) ? 12'hF0F : (tick ? 12'h404 : 12'h101);
        else if (in_ref)     rgb = ref_rgb;
        else                 rgb = 12'h000;
    end
endmodule

`default_nettype wire
