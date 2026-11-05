// -----------------------------------------------------------------------------
// ov5640_init -- power-up sequencing, chip-ID readback, register table walk.
//
// Knows the sensor; knows nothing about SCCB bit timing. Owns cam_pwdn and
// cam_reset_n.
//
// Sequence (XCLK must already be running before reset is released):
//   PWDN high, RESET low   -> 10 ms
//   PWDN low (powered on)  ->  5 ms
//   RESET high             -> 50 ms
//   read 0x300A/0x300B, expect 0x56/0x40
//   walk the table
//
// Timings are generous rather than minimal: a counter is nearly free and a
// marginal power-up is expensive to debug blind.
//
// REGISTER PROVENANCE -- see the spec. Values are tagged:
//   [datasheet] from the OV5640 datasheet
//   [reference] from canonical open-source tables (esp32-camera)
//   [derived]   inferred, NOT yet validated on hardware
// This first table is deliberately minimal: bring the part out of reset, put it
// in DVP RGB565, and turn on the internal test bar. Getting a chip ID and a live
// PCLK is the whole goal of this build -- a full QVGA scaler table is worthless
// until those two things are proven.
// -----------------------------------------------------------------------------
// -----------------------------------------------------------------------------
// VERIFIED 30 fps CONFIGURATION  (measured over UART, 2026-10-07)
//   PCLK 14.46 MHz | 29-30 fps | 240 lines/frame | 640 B/line
//   76764 px/frame | x_max 319 | y_max 239 | 6.9x oversampled at 100 MHz
//
// Three things learned the hard way while tuning this:
//  1. VTS cannot go below the sensor's ARRAY READOUT height, which subsampling
//     sets -- not the 240-line output height. At /2 the readout is 971 lines, so
//     VTS 984 was already at its floor and no reduction was possible.
//  2. 0x3824 divides the DVP output clock ONLY. Doubling PCLK with it changed
//     the frame rate not at all; it just added blanking. Frame rate comes from
//     the sensor readout clock -- 0x3035 and 0x3036.
//  3. /8 subsampling reaches 22 fps but starves the vertical scaler: only 243
//     source rows for a 240-row output, and Y offset 6 ate into even that,
//     capping output at 212 lines. /4 is the usable limit here.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module ov5640_init #(
    parameter integer CLK_HZ = 100_000_000
)(
    input  wire        clk,
    input  wire        rst,
    input  wire        debug_refresh, // Rising edge: repeat READS only; no camera reset/writes.
    // SW1: run the sensor's own internal colour bar instead of the imager.
    // The DVP then carries a synthetic, noise-free, perfectly static pattern,
    // so anything speckled or flickering on screen is transport error, not
    // the sensor or the 4-bit quantisation. Sampled when the sequence starts.
    input  wire        testbar,
    // SW4: U/V order within the YUV422 pair. 0x30 = YUYV, 0x31 = YVYU.
    // Getting this wrong swaps red and blue; it is one register and there is
    // no way to know from here which the breakout actually emits.
    input  wire        vyuy,
    // Host valid/ready handshake. Initialization and refresh retain bus ownership.
    input wire host_valid, input wire host_rw,
    input wire [15:0] host_addr, input wire [7:0] host_wdata,
    output wire host_ready, output reg host_done,
    output reg [7:0] host_rdata, output reg host_nack,
    // sccb_master handshake
    output reg         sccb_start,
    output reg         sccb_rw,
    output reg  [15:0] sccb_addr,
    output reg  [7:0]  sccb_wdata,
    input  wire [7:0]  sccb_rdata,
    input  wire        sccb_busy,
    input  wire        sccb_done,
    input  wire        sccb_nack,
    // sensor control pins
    output reg         cam_pwdn,
    output reg         cam_reset_n,
    // status
    output reg  [15:0] chip_id,
    output reg         id_valid,
    output reg         init_done,
    output reg         nack_seen,
    output reg  [7:0]  table_index,
    output reg [383:0] debug_readback,
    output reg [47:0] debug_read_nack
);
    localparam integer MS = CLK_HZ / 1000;

    // ---------------- register table ----------------
    // {cmd[1:0], addr[15:0], data[7:0]}
    localparam [1:0] C_WR = 2'd0, C_DLY = 2'd1, C_END = 2'd2;

    reg [25:0] entry;
    always @* begin
        case (table_index)
        // --- canonical esp32-camera reset + BLOCK ENABLE sequence. The block
        //     clock-enables (0x3004/0x3006) and resets (0x3000/0x3002) were
        //     missing from the hand-written table -- without them the DVP output
        //     block never runs, which matches the symptom: PCLK and VSYNC present
        //     but no usable HREF / pixel stream.
        8'd0  : entry = {C_WR,  16'h3008, 8'h82};  // software reset
        8'd1  : entry = {C_DLY, 16'd20  , 8'h00};  // 20 ms
        8'd2  : entry = {C_WR,  16'h3008, 8'h42};  // power down while configuring
        8'd3  : entry = {C_WR,  16'h3103, 8'h13};  // [reference] sysclk from PLL (was 0x11/0x03)
        8'd4  : entry = {C_WR,  16'h3017, 8'hFF};  // [reference] DVP pad enable
        8'd5  : entry = {C_WR,  16'h3018, 8'hFF};  // [reference] DVP pad enable
        8'd6  : entry = {C_WR,  16'h3016, 8'hC3};  // [reference]
        8'd7  : entry = {C_WR,  16'h3020, 8'h21};  // [reference]
        8'd8  : entry = {C_WR,  16'h4713, 8'h02};  // [reference]
        8'd9  : entry = {C_WR,  16'h5001, 8'h83};  // [reference]
        8'd10 : entry = {C_WR,  16'h3000, 8'h20};  // [reference] block reset
        8'd11 : entry = {C_DLY, 16'd10  , 8'h00};  // 10 ms
        8'd12 : entry = {C_WR,  16'h3002, 8'h1C};  // [reference] block reset
        8'd13 : entry = {C_WR,  16'h3004, 8'hFF};  // [reference] BLOCK CLOCK ENABLE
        8'd14 : entry = {C_WR,  16'h3006, 8'hC3};  // [reference] BLOCK CLOCK ENABLE
        8'd15 : entry = {C_WR,  16'h5000, 8'hA7};  // [reference] ISP enable
        8'd16 : entry = {C_WR,  16'h5001, 8'hA3};  // [reference] ISP + scaling
        8'd17 : entry = {C_WR,  16'h5003, 8'h08};  // [reference]
        8'd18 : entry = {C_WR,  16'h370C, 8'h02};  // [reference]
        8'd19 : entry = {C_WR,  16'h3634, 8'h40};  // [reference]
        // --- PLL. esp32-camera sets these programmatically, so there is no table
        //     to copy. Chosen for a DELIBERATELY SLOW PCLK (~14 MHz): the 100 MHz
        //     oversampler needs PCLK well under 25 MHz, and my previous x105
        //     multiplier was almost certainly far too fast. [derived]
        8'd20 : entry = {C_WR,  16'h3039, 8'h00};  // [derived] PLL not bypassed
        8'd21 : entry = {C_WR,  16'h3034, 8'h1A};  // [reference] 10-bit mode
        8'd22 : entry = {C_WR,  16'h3035, 8'h41};  // Diagnostic: sysclk divider 4, half baseline sensor/DVP rate; measure on board.
        8'd23 : entry = {C_WR,  16'h3036, 8'h48};  // [measured] PLL multiplier x72
        8'd24 : entry = {C_WR,  16'h3037, 8'h13};  // [reference] pre-div 3
        8'd25 : entry = {C_WR,  16'h3108, 8'h01};  // [reference]
        8'd26 : entry = {C_WR,  16'h3824, 8'h04};  // [measured] DVP PCLK div /4 -- affects PCLK ONLY, not fps
        8'd27 : entry = {C_WR,  16'h460C, 8'h22};  // [derived] PCLK manual divider
        // --- windowing: 320x240 out of the full array ---
        8'd28 : entry = {C_WR,  16'h3820, 8'h41};  // [reference] flip
        8'd29 : entry = {C_WR,  16'h3821, 8'h07};  // [reference] mirror + binning
        8'd30 : entry = {C_WR,  16'h3814, 8'h71};  // [measured] X subsample /4
        8'd31 : entry = {C_WR,  16'h3815, 8'h71};  // [measured] Y subsample /4 -- sets the VTS floor
        8'd32 : entry = {C_WR,  16'h3800, 8'h00};
        8'd33 : entry = {C_WR,  16'h3801, 8'h00};  // X start 0
        8'd34 : entry = {C_WR,  16'h3802, 8'h00};
        8'd35 : entry = {C_WR,  16'h3803, 8'h04};  // Y start 4
        8'd36 : entry = {C_WR,  16'h3804, 8'h0A};
        8'd37 : entry = {C_WR,  16'h3805, 8'h3F};  // X end 2623
        8'd38 : entry = {C_WR,  16'h3806, 8'h07};
        8'd39 : entry = {C_WR,  16'h3807, 8'h9B};  // Y end 1947
        8'd40 : entry = {C_WR,  16'h3808, 8'h01};
        8'd41 : entry = {C_WR,  16'h3809, 8'h40};  // DVP width 320
        8'd42 : entry = {C_WR,  16'h380A, 8'h00};
        8'd43 : entry = {C_WR,  16'h380B, 8'hF0};  // DVP height 240
        8'd44 : entry = {C_WR,  16'h380C, 8'h07};
        8'd45 : entry = {C_WR,  16'h380D, 8'h68};  // HTS 1896
        8'd46 : entry = {C_WR,  16'h380E, 8'h02};
        8'd47 : entry = {C_WR,  16'h380F, 8'h08};  // VTS 520  (floor is the /4 readout, 486 lines)
        8'd48 : entry = {C_WR,  16'h3810, 8'h00};
        8'd49 : entry = {C_WR,  16'h3811, 8'h10};  // X offset 16
        8'd50 : entry = {C_WR,  16'h3812, 8'h00};
        8'd51 : entry = {C_WR,  16'h3813, 8'h06};  // Y offset 6
        // --- output format + polarity + internal test bar ---
        // YUV422 instead of RGB565: same two bytes per pixel on the wire, so
        // PCLK and the ribbon rate are unchanged, but luma arrives as a full
        // 8 bits per pixel instead of 6 bits of green. The 24-bit HDMI path
        // wants RGB, so ycbcr2rgb converts in fabric.
        8'd52 : entry = {C_WR,  16'h4300, vyuy ? 8'h31 : 8'h30};  // YVYU : YUYV
        8'd53 : entry = {C_WR,  16'h501F, 8'h00};  // ISP YUV422 (was 0x01, RGB)
        8'd54 : entry = {C_WR,  16'h4740, 8'h22};  // Linux OV5640 DVP: rising sample, HREF high, VSYNC high (bit0=0).
        8'd55 : entry = {C_WR,  16'h503D, testbar ? 8'h80 : 8'h00};  // internal colour bar
        // One controlled trial: manual exposure 128 lines of VTS 520,
        // gain 1x. Register encodings follow Espressif OV5640 controls.
        // White balance, receiver, clock, window and format stay unchanged.
        8'd56 : entry = {C_WR, 16'h3503, 8'h03}; // manual AEC and AGC
        8'd57 : entry = {C_WR, 16'h3500, 8'h00};
        8'd58 : entry = {C_WR, 16'h3501, 8'h08}; // 128 << 4 = 0x00800
        8'd59 : entry = {C_WR, 16'h3502, 8'h00};
        8'd60 : entry = {C_WR, 16'h350A, 8'h00};
        8'd61 : entry = {C_WR, 16'h350B, 8'h10}; // 1.0x, gain units 1/16
        8'd62 : entry = {C_WR, 16'h3008, 8'h02}; // start streaming
        8'd63 : entry = {C_DLY,16'd100, 8'h00};
        default: entry = {C_END, 16'h0000, 8'h00};
        endcase
    end

    wire [1:0]  e_cmd  = entry[25:24];
    wire [15:0] e_addr = entry[23:8];
    wire [7:0]  e_data = entry[7:0];

    // ---------------- sequencer ----------------
    localparam [3:0] P_RST0=4'd0, P_RST1=4'd1, P_RST2=4'd2,
                     P_ID_HI=4'd3, P_ID_HI_W=4'd4,
                     P_ID_LO=4'd5, P_ID_LO_W=4'd6,
                     P_TBL=4'd7,   P_TBL_W=4'd8, P_DLY=4'd9,
                     P_DONE=4'd10, P_DEBUG=4'd11, P_DEBUG_WAIT=4'd12, P_HOST_WAIT=4'd13;

    reg [5:0] debug_index;
    reg debug_refresh_q = 0;
    reg [15:0] debug_addr;
    always @* begin
        case (debug_index)
        6'd0: debug_addr=16'h4740;
        6'd1: debug_addr=16'h4300;
        6'd2: debug_addr=16'h501F;
        6'd3: debug_addr=16'h300E;
        6'd4: debug_addr=16'h3017;
        6'd5: debug_addr=16'h3018;
        6'd6: debug_addr=16'h3034;
        6'd7: debug_addr=16'h3035;
        6'd8: debug_addr=16'h3036;
        6'd9: debug_addr=16'h3037;
        6'd10: debug_addr=16'h3108;
        6'd11: debug_addr=16'h3824;
        6'd12: debug_addr=16'h3808;
        6'd13: debug_addr=16'h3809;
        6'd14: debug_addr=16'h380A;
        6'd15: debug_addr=16'h380B;
        6'd16: debug_addr=16'h3008;
        6'd17: debug_addr=16'h4713;
        6'd18: debug_addr=16'h3503;
        6'd19: debug_addr=16'h3500;
        6'd20: debug_addr=16'h3501;
        6'd21: debug_addr=16'h3502;
        6'd22: debug_addr=16'h350A;
        6'd23: debug_addr=16'h350B;
        6'd24: debug_addr=16'h5000;
        6'd25: debug_addr=16'h5001;
        6'd26: debug_addr=16'h5005;
        6'd27: debug_addr=16'h3400;
        6'd28: debug_addr=16'h3401;
        6'd29: debug_addr=16'h3402;
        6'd30: debug_addr=16'h3403;
        6'd31: debug_addr=16'h3404;
        6'd32: debug_addr=16'h3405;
        6'd33: debug_addr=16'h3406;
        6'd34: debug_addr=16'h5380;
        6'd35: debug_addr=16'h5381;
        6'd36: debug_addr=16'h5382;
        6'd37: debug_addr=16'h5383;
        6'd38: debug_addr=16'h5384;
        6'd39: debug_addr=16'h5385;
        6'd40: debug_addr=16'h5386;
        6'd41: debug_addr=16'h5387;
        6'd42: debug_addr=16'h5388;
        6'd43: debug_addr=16'h5389;
        6'd44: debug_addr=16'h538A;
        6'd45: debug_addr=16'h538B;
        6'd46: debug_addr=16'h5480;
        6'd47: debug_addr=16'h5580;
        default: debug_addr=16'h300A;
        endcase
    end
    reg [3:0]  st    = P_RST0;
    reg [31:0] timer = 32'd0;
    reg [15:0] delay_ms = 16'd0;

    assign host_ready = st == P_DONE && init_done && !sccb_busy &&
                        !(debug_refresh && !debug_refresh_q);
    always @(posedge clk) begin
        host_done <= 1'b0;
        sccb_start <= 1'b0;
        debug_refresh_q <= debug_refresh;
        if (rst) begin
            st          <= P_RST0;
            timer       <= 32'd0;
            delay_ms    <= 16'd0;
            cam_pwdn    <= 1'b1;        // powered down
            cam_reset_n <= 1'b0;        // held in reset
            host_done <= 0; host_rdata <= 0; host_nack <= 0;
            chip_id     <= 16'h0000;
            id_valid    <= 1'b0;
            init_done   <= 1'b0;
            nack_seen   <= 1'b0;
            table_index <= 8'd0;
            debug_refresh_q <= 0;
            debug_index <= 0; debug_readback <= 0; debug_read_nack <= 0;
            sccb_rw     <= 1'b0;
            sccb_addr   <= 16'h0000;
            sccb_wdata  <= 8'h00;
        end else begin
            if (sccb_done && sccb_nack) nack_seen <= 1'b1;

            case (st)
            // ---- power-up timing ----
            P_RST0: begin                       // PWDN high, RESET low, 200 ms
                // 200 ms, not 10. A brief hot-unplug left the sensor in a state
                // a short power-down would not clear: chip ID still read 0x5640
                // and PCLK came up at exactly the configured rate, but VSYNC and
                // HREF stayed at ~190 kHz / ~600 kHz of noise and no frame ever
                // completed. A long PWDN assert is the only reset authority the
                // FPGA has -- the sensor's 3.3 V comes from the Pmod header and
                // cannot be switched from here.
                cam_pwdn    <= 1'b1;
                cam_reset_n <= 1'b0;
                if (timer >= 200*MS) begin timer <= 0; st <= P_RST1; end
                else timer <= timer + 1;
            end
            P_RST1: begin                       // power on, 5 ms
                cam_pwdn <= 1'b0;
                if (timer >= 20*MS) begin timer <= 0; st <= P_RST2; end
                else timer <= timer + 1;
            end
            P_RST2: begin                       // release reset, 50 ms
                cam_reset_n <= 1'b1;
                if (timer >= 100*MS) begin timer <= 0; st <= P_ID_HI; end
                else timer <= timer + 1;
            end

            // ---- chip ID: the cheapest proof that power, XCLK and SCCB work ----
            P_ID_HI: if (!sccb_busy) begin
                sccb_rw <= 1'b1; sccb_addr <= 16'h300A; sccb_start <= 1'b1;
                st <= P_ID_HI_W;
            end
            P_ID_HI_W: if (sccb_done) begin
                chip_id[15:8] <= sccb_rdata; st <= P_ID_LO;
            end
            P_ID_LO: if (!sccb_busy) begin
                sccb_rw <= 1'b1; sccb_addr <= 16'h300B; sccb_start <= 1'b1;
                st <= P_ID_LO_W;
            end
            P_ID_LO_W: if (sccb_done) begin
                chip_id[7:0] <= sccb_rdata;
                id_valid     <= (chip_id[15:8] == 8'h56) && (sccb_rdata == 8'h40);
                st           <= P_TBL;
            end

            // ---- table walk ----
            P_TBL: begin
                case (e_cmd)
                    C_WR: if (!sccb_busy) begin
                        sccb_rw    <= 1'b0;
                        sccb_addr  <= e_addr;
                        sccb_wdata <= e_data;
                        sccb_start <= 1'b1;
                        st         <= P_TBL_W;
                    end
                    C_DLY: begin timer <= 0; delay_ms <= e_addr; st <= P_DLY; end
                    default: begin debug_index <= 0; st <= P_DEBUG; end
                endcase
            end
            P_TBL_W: if (sccb_done) begin
                table_index <= table_index + 8'd1;
                st          <= P_TBL;
            end
            P_DLY: begin
                // Avoid the ROM-address multiplication on the 200 MHz FSM path.
                if (delay_ms == 0) begin
                    timer       <= 0;
                    table_index <= table_index + 8'd1;
                    st          <= P_TBL;
                end else if (timer >= MS-1) begin
                    timer <= 0;
                    delay_ms <= delay_ms - 16'd1;
                end else timer <= timer + 1;
            end

            P_DEBUG: if (!sccb_busy) begin
                sccb_rw <= 1'b1; sccb_addr <= debug_addr; sccb_start <= 1'b1;
                st <= P_DEBUG_WAIT;
            end
            P_DEBUG_WAIT: if (sccb_done) begin
                debug_readback[debug_index*8 +: 8] <= sccb_rdata;
                debug_read_nack[debug_index] <= sccb_nack;
                if (debug_index == 47) st <= P_DONE;
                else begin debug_index <= debug_index + 1'b1; st <= P_DEBUG; end
            end
            P_DONE: begin
                init_done <= 1'b1;
                if (debug_refresh && !debug_refresh_q) begin
                    debug_index <= 0; st <= P_DEBUG;
                end else if (host_valid && host_ready) begin
                    sccb_rw <= host_rw; sccb_addr <= host_addr;
                    sccb_wdata <= host_wdata; sccb_start <= 1'b1;
                    st <= P_HOST_WAIT;
                end
            end
            P_HOST_WAIT: if (sccb_done) begin
                host_rdata <= sccb_rdata; host_nack <= sccb_nack;
                host_done <= 1'b1; st <= P_DONE;
            end
            default: st <= P_DONE;
            endcase
        end
    end
endmodule

`default_nettype wire
