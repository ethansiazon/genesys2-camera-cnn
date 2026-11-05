// -----------------------------------------------------------------------------
// vga_timing -- 640x480 @ 60 Hz industry-standard VGA timing.
//
// Pixel clock is 25.0 MHz (we derive it from the 100 MHz board clock; the ideal
// is 25.175 MHz, and 0.7% low is well inside what a monitor will lock to).
//   H: 640 active + 16 front + 96 sync + 48 back  = 800
//   V: 480 active + 10 front +  2 sync + 33 back  = 525
//   refresh = 25.0e6 / (800*525) = 59.52 Hz
// Both syncs are ACTIVE LOW.
//
// hcnt/vcnt are registered; active/hsync/vsync are combinational from them, so
// everything this module emits describes the SAME pixel in the same cycle. The
// consumer is responsible for delaying the syncs to match its own pixel-path
// latency (see top_basys3: one cycle for both the direct and BRAM paths).
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module vga_timing #(
    parameter H_ACTIVE = 640,
    parameter H_FP     = 16,
    parameter H_SYNC   = 96,
    parameter H_BP     = 48,
    parameter V_ACTIVE = 480,
    parameter V_FP     = 10,
    parameter V_SYNC   = 2,
    parameter V_BP     = 33
)(
    input  wire       clk,
    input  wire       rst,
    output reg  [9:0] hcnt,
    output reg  [9:0] vcnt,
    output wire       active,
    output wire       hsync,          // active low
    output wire       vsync,          // active low
    output wire       frame_start     // 1-cycle pulse entering vertical blank
);
    localparam H_TOTAL = H_ACTIVE + H_FP + H_SYNC + H_BP;   // 800
    localparam V_TOTAL = V_ACTIVE + V_FP + V_SYNC + V_BP;   // 525

    // Initialised at declaration so simulation matches 7-series power-up (INIT=0)
    // -- an X here would freeze every downstream case statement.
    initial begin
        hcnt = 10'd0;
        vcnt = 10'd0;
    end

    always @(posedge clk) begin
        if (rst) begin
            hcnt <= 10'd0;
            vcnt <= 10'd0;
        end else if (hcnt == H_TOTAL - 1) begin
            hcnt <= 10'd0;
            vcnt <= (vcnt == V_TOTAL - 1) ? 10'd0 : vcnt + 10'd1;
        end else begin
            hcnt <= hcnt + 10'd1;
        end
    end

    assign active = (hcnt < H_ACTIVE) && (vcnt < V_ACTIVE);

    assign hsync  = ~((hcnt >= H_ACTIVE + H_FP) &&
                      (hcnt <  H_ACTIVE + H_FP + H_SYNC));

    assign vsync  = ~((vcnt >= V_ACTIVE + V_FP) &&
                      (vcnt <  V_ACTIVE + V_FP + V_SYNC));

    assign frame_start = (hcnt == 10'd0) && (vcnt == V_ACTIVE);
endmodule

`default_nettype wire
