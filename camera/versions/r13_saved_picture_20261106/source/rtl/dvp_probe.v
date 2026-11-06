// -----------------------------------------------------------------------------
// dvp_probe -- measures the raw DVP stream in hardware, in the 100 MHz domain.
//
// This exists because inferring sensor behaviour from a webcam photo of a
// monitor proved unreliable: it produced one outright misread and one falsified
// hypothesis. These are direct counts, reported over UART as text.
//
//   pclk_hz : PCLK rising edges in a 1 s window -- the ACTUAL pixel clock rate
//   vs_hz   : VSYNC rising edges per second     -- the ACTUAL frame rate
//   href_ln : HREF rising edges per frame       -- lines per frame
//   href_len: PCLK edges while HREF high, on one line -- line length in BYTES
//   hi_len  : the largest href_len seen         -- catches ragged lines
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module dvp_probe #(
    parameter integer CLK_HZ = 100_000_000
)(
    input  wire        clk,
    input  wire        rst,
    input  wire        pclk_i,
    input  wire        vsync_i,
    input  wire        href_i,
    output reg  [31:0] pclk_hz,
    output reg  [31:0] vs_hz,
    output reg  [31:0] href_ln,
    output reg  [31:0] href_len,
    output reg  [31:0] hi_len,
    output reg         tick_1s      // 1-cycle pulse each second
);
    reg [2:0] p_s = 0, v_s = 0, h_s = 0;
    always @(posedge clk) begin
        p_s <= {p_s[1:0], pclk_i};
        v_s <= {v_s[1:0], vsync_i};
        h_s <= {h_s[1:0], href_i};
    end
    wire p_rise = (p_s[2:1] == 2'b01);
    wire v_rise = (v_s[2:1] == 2'b01);
    wire h_rise = (h_s[2:1] == 2'b01);
    wire h_fall = (h_s[2:1] == 2'b10);
    wire h_high =  h_s[2];

    reg [31:0] sec   = 0;
    reg [31:0] pcnt  = 0, vcnt = 0;
    reg [31:0] lcnt  = 0, cur = 0, hi = 0;

    always @(posedge clk) begin
        tick_1s <= 1'b0;
        if (rst) begin
            sec<=0; pcnt<=0; vcnt<=0; lcnt<=0; cur<=0; hi<=0;
            pclk_hz<=0; vs_hz<=0; href_ln<=0; href_len<=0; hi_len<=0;
        end else begin
            if (p_rise) pcnt <= pcnt + 1;
            if (v_rise) vcnt <= vcnt + 1;
            if (h_rise) begin lcnt <= lcnt + 1; cur <= 0; end
            else if (h_high && p_rise) cur <= cur + 1;
            if (h_fall) begin
                href_len <= cur;
                if (cur > hi) hi <= cur;
            end

            if (sec == CLK_HZ-1) begin
                sec     <= 0;
                pclk_hz <= pcnt;  pcnt <= 0;
                vs_hz   <= vcnt;  vcnt <= 0;
                href_ln <= lcnt;  lcnt <= 0;
                hi_len  <= hi;    hi   <= 0;
                tick_1s <= 1'b1;
            end else sec <= sec + 1;
        end
    end
endmodule

`default_nettype wire
