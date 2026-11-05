// Diagnostic supports original oversampling and dedicated-PCLK source sampling.
`timescale 1ns / 1ps
`default_nettype none

module cam_capture #(
    parameter integer H                 = 320,
    parameter integer RGB565            = 0,
    parameter integer SOURCE_SYNC       = 0,
    parameter integer SAMPLE_TICK_MODE  = 0,
    parameter integer V                 = 240,
    parameter integer VSYNC_ACTIVE_HIGH = 1,
    // Reject HREF pulses shorter than this many PIXELS. Ribbon crosstalk on
    // HREF showed up as ~270 lines per frame instead of 240. Rejected by pulse
    // LENGTH, never by a time filter: HREF gates the pixel path, so filtering
    // latency shifts every pixel by a cycle.
    parameter integer MIN_LINE_PX       = 280,
    parameter integer MEDIAN3           = 1,
    parameter integer TEMPORAL          = 1,
    parameter integer SYNC_FILTER       = 1,
    // VSYNC integrator thresholds, in FABRIC cycles. Defaults are sized for
    // 200 MHz to match the ~480 ns window that works at 100 MHz on the Basys 3.
    parameter integer VS_MAX            = 128,
    parameter integer VS_HI             = 96,
    parameter integer VS_LO             = 32
)(
    input  wire        clk,            // 200 MHz oversampling clock
    input  wire        rst,
    input  wire        pclk_i,         // DVP pixel clock, sampled as DATA
    input  wire        vsync_i,
    input  wire        href_i,
    input  wire [7:0]  d_i,
    input  wire        uyvy,           // 0 = Y0 Cb Y1 Cr, 1 = Cb Y0 Cr Y1
    input  wire        full_range,
    input  wire        sample_strobe,

    output reg  [16:0] wr_addr,
    output reg  [23:0] wr_data,
    output reg         wr_en,
    input  wire [23:0] fb_old,

    output reg  [15:0] frame_cnt,
    output reg         href_seen,
    output reg         pix_seen,
    output reg  [19:0] pix_per_frame,
    output reg  [9:0]  x_max,
    output reg  [9:0]  y_max,
    output reg  [7:0]  luma_min,
    output reg  [7:0]  luma_max,
    output reg  [31:0] luma_sad,
    output reg  [31:0] temporal_diff,
    output reg  [15:0] short_lines,
    output wire        vsync_clean,
    output wire [48:0] debug_state
);
    // ---------------- synchronise the async DVP into this domain ----------------
    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO" *)
    reg [2:0] p_s = 3'b000, v_s = 3'b000, h_s = 3'b000;
    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO" *)
    reg [7:0] d_s0 = 8'h00, d_s1 = 8'h00;
    reg qualified_tick_d=0;
    generate if (SAMPLE_TICK_MODE != 0) begin : g_qualified_samples
        always @(posedge clk) begin
            qualified_tick_d <= rst ? 1'b0 : sample_strobe;
            if(sample_strobe)begin
                d_s1<=d_i;h_s<={1'b0,href_i,1'b0};v_s<={1'b0,vsync_i,1'b0};
            end
        end
    end else if (SOURCE_SYNC != 0) begin : g_source_sync
        // DVP data/control are sampled together by the received camera clock.
        always @(posedge clk) begin
            d_s1 <= d_i;
            h_s <= {1'b0,href_i,1'b0};
            v_s <= {1'b0,vsync_i,1'b0};
        end
    end else begin : g_oversample
        always @(posedge clk) begin
            p_s <= {p_s[1:0],pclk_i};
            v_s <= {v_s[1:0],vsync_i};
            h_s <= {h_s[1:0],href_i};
            d_s0 <= d_i; d_s1 <= d_s0;
        end
    end endgenerate
    wire pclk_rise = SAMPLE_TICK_MODE != 0 ? qualified_tick_d :
                     SOURCE_SYNC != 0 ? 1'b1 : (p_s == 3'b011);

    wire href      = h_s[1];                // read at N-2, matching d_s1
    wire vs_in     = v_s[1];

    // ---------------- VSYNC integrator with hysteresis ----------------
    // NOT a "stable for N cycles" filter. That was the first attempt and it
    // failed on hardware: on a noisy line the stability counter keeps
    // resetting, so genuine edges are swallowed with the glitches and frames
    // run long. An integrator accumulates evidence instead.
    reg [7:0] vs_int = 8'd0;
    reg       vs_f   = 1'b0;
    always @(posedge clk) begin
        if (rst) begin
            vs_int <= 8'd0; vs_f <= 1'b0;
        end else begin
            if (vs_in) begin
                if (vs_int < VS_MAX[7:0]) vs_int <= vs_int + 8'd1;
            end else begin
                if (vs_int > 8'd0)        vs_int <= vs_int - 8'd1;
            end
            if      (vs_int >= VS_HI[7:0]) vs_f <= 1'b1;
            else if (vs_int <= VS_LO[7:0]) vs_f <= 1'b0;
        end
    end

    wire vs_raw = (SYNC_FILTER == 0) ? vs_in : vs_f;
    wire vs     = VSYNC_ACTIVE_HIGH ? vs_raw : ~vs_raw;
    assign vsync_clean = vs_raw;

    reg vs_d = 1'b0, href_d = 1'b0;
    wire vs_rise   =  vs && !vs_d;
    wire href_fall = !href && href_d;

    // ---------------- receive side ----------------
    reg [1:0] p    = 2'd0;
    reg [9:0] x_rx = 10'd0;
    reg [9:0] y    = 10'd0;
    reg [7:0] y0_r = 0, y1_r = 0, cb_r = 0, cr_r = 0;

    // XORing the phase LSB turns YUYV into UYVY with no second decode path.
    wire [1:0] slot = (RGB565 != 0) ? p : (p ^ {1'b0, uyvy});

    // 3-tap median on luma: impulse rejection for single-bit flips on the data
    // bus, which show up as black/white speckle. Luma only -- chroma is shared
    // between pixel pairs and already low-pass horizontally.
    reg  [7:0] m1 = 8'd0, m0 = 8'd0;
    wire [7:0] med3 = (m1 > m0) ? ((m0 > d_s1) ? m0 : ((m1 > d_s1) ? d_s1 : m1))
                                : ((m1 > d_s1) ? m1 : ((m0 > d_s1) ? d_s1 : m0));
    wire [7:0] luma_in = (MEDIAN3 != 0 && RGB565 == 0) ? med3 : d_s1;

    wire byte_now   = pclk_rise && href;
    wire group_done = byte_now && (p == 2'd3);

    // ---------------- emit side ----------------
    reg [7:0] y0_q = 0, y1_q = 0, cb_q = 0, cr_q = 0;
    reg [9:0] gx   = 10'd0, gy = 10'd0;
    reg [2:0] ecnt = 3'd4;                      // 4 = idle
    wire      e_active = (ecnt < 3'd4);
    wire [1:0] ep = ecnt[1:0];

    wire gx0_in = (gx < H[9:0]) && (gy < V[9:0]);
    wire gx1_in = ((gx + 10'd1) < H[9:0]) && (gy < V[9:0]);
    wire [16:0] addr0 = gy * H[16:0] + {7'd0, gx};
    wire [16:0] addr1 = addr0 + 17'd1;

    // Combinational feed, so valid_o lands exactly on e2 and e3. Registering
    // this slides every write one cycle late.
    wire       cvt_valid = e_active && ((ep == 2'd0 && gx0_in) ||
                                        (ep == 2'd1 && gx1_in));
    wire [7:0] cvt_y     = (ep == 2'd0) ? y0_q : y1_q;

    wire [7:0] rgb_r, rgb_g, rgb_b;
    wire       rgb_valid;
    generate if (RGB565 == 0) begin : g_yuv
    ycbcr2rgb cvt (
        .clk(clk), .rst(rst), .full_range(full_range),
        .y(cvt_y), .cb(cb_q), .cr(cr_q), .valid_i(cvt_valid),
        .r(rgb_r), .g(rgb_g), .b(rgb_b), .valid_o(rgb_valid)
    );
    end else begin : g_rgb565
        // Reuse four-byte scheduling: two independent RGB565 words per group.
        // Keep the same two-cycle valid/data latency as ycbcr2rgb.
        wire [15:0] word_in = ep == 0 ? {y0_q,cb_q} : {y1_q,cr_q};
        reg [23:0] pixels_1=0,pixels_2=0;
        reg valid_1=0,valid_2=0;
        always @(posedge clk) begin
            if(rst) begin pixels_1<=0;pixels_2<=0;valid_1<=0;valid_2<=0;end
            else begin
                pixels_1 <= {word_in[15:11],word_in[15:13],
                             word_in[10:5],word_in[10:9],
                             word_in[4:0],word_in[4:2]};
                pixels_2<=pixels_1;valid_1<=cvt_valid;valid_2<=valid_1;
            end
        end
        assign {rgb_r,rgb_g,rgb_b}=pixels_2;
        assign rgb_valid=valid_2;
    end endgenerate

    reg [7:0] luma_d1, luma_d2;
    always @(posedge clk) begin
        // Green is a diagnostic brightness proxy in RGB mode, not Y luma.
        luma_d1 <= (RGB565 != 0) ?
          (ep == 0 ? {y0_q[2:0],cb_q[7:5],y0_q[2:1]} : {y1_q[2:0],cr_q[7:5],y1_q[2:1]}) : cvt_y;
        luma_d2 <= luma_d1;
    end

    // ---------------- temporal blend ----------------
    // (3*old + new + 2) >> 2. The +2 is round-to-nearest; see header.
    function [7:0] blend;
        input [7:0] old_v; input [7:0] new_v;
        reg [9:0] s;
        begin
            s = {2'b00, old_v} + {2'b00, old_v} + {2'b00, old_v}
              + {2'b00, new_v} + 10'd2;
            blend = s[9:2];
        end
    endfunction

    wire [7:0] out_r = (TEMPORAL != 0) ? blend(fb_old[23:16], rgb_r) : rgb_r;
    wire [7:0] out_g = (TEMPORAL != 0) ? blend(fb_old[15:8],  rgb_g) : rgb_g;
    wire [7:0] out_b = (TEMPORAL != 0) ? blend(fb_old[7:0],   rgb_b) : rgb_b;

    wire [7:0] old_luma = fb_old[15:8];
    wire [7:0] tdif = (rgb_g >= old_luma) ? (rgb_g - old_luma) : (old_luma - rgb_g);

    reg  [7:0] prev_lum  = 8'd0;
    reg        have_prev = 1'b0;
    wire [7:0] lum_dif = (luma_d2 >= prev_lum) ? (luma_d2 - prev_lum)
                                               : (prev_lum - luma_d2);

    reg [31:0] tdiff_acc = 32'd0, sad_acc = 32'd0;
    reg [15:0] shl_acc   = 16'd0;
    reg [7:0]  lmin_acc  = 8'hFF, lmax_acc = 8'h00;
    reg [19:0] pix_cnt   = 20'd0;
    reg [9:0]  xm = 10'd0, ym = 10'd0;

    always @(posedge clk) begin
        wr_en <= 1'b0;

        if (rst) begin
            p <= 2'd0; x_rx <= 10'd0; y <= 10'd0; xm <= 10'd0; ym <= 10'd0;
            vs_d <= 1'b0; href_d <= 1'b0; ecnt <= 3'd4;
            frame_cnt <= 16'd0; href_seen <= 1'b0; pix_seen <= 1'b0;
            pix_cnt <= 20'd0; pix_per_frame <= 20'd0;
            x_max <= 10'd0; y_max <= 10'd0;
            tdiff_acc <= 32'd0; temporal_diff <= 32'd0;
            sad_acc <= 32'd0; luma_sad <= 32'd0;
            shl_acc <= 16'd0; short_lines <= 16'd0;
            lmin_acc <= 8'hFF; lmax_acc <= 8'h00;
            luma_min <= 8'd0; luma_max <= 8'd0;
            prev_lum <= 8'd0; have_prev <= 1'b0;
            y0_r <= 0; y1_r <= 0; cb_r <= 0; cr_r <= 0;
            y0_q <= 0; y1_q <= 0; cb_q <= 0; cr_q <= 0;
            m1 <= 0; m0 <= 0;
        end else begin
            vs_d   <= vs;
            href_d <= href;
            if (href) href_seen <= 1'b1;

            // emit counter runs on FABRIC cycles, so it always completes
            if (group_done)       ecnt <= 3'd0;
            else if (ecnt < 3'd4) ecnt <= ecnt + 3'd1;

            if (vs_rise) begin
                p <= 2'd0; x_rx <= 10'd0; y <= 10'd0;
                frame_cnt <= frame_cnt + 16'd1;
                pix_per_frame <= pix_cnt;   pix_cnt   <= 20'd0;
                x_max <= xm;                xm        <= 10'd0;
                y_max <= ym;                ym        <= 10'd0;
                temporal_diff <= tdiff_acc; tdiff_acc <= 32'd0;
                luma_sad <= sad_acc;        sad_acc   <= 32'd0;
                short_lines <= shl_acc;     shl_acc   <= 16'd0;
                luma_min <= lmin_acc;       lmin_acc  <= 8'hFF;
                luma_max <= lmax_acc;       lmax_acc  <= 8'h00;
            end else if (href_fall && (x_rx < MIN_LINE_PX[9:0])) begin
                // HREF glitch: too short to be a line. Counted, and x_rx is
                // deliberately NOT reset -- a mid-line glitch must not look
                // like a line boundary.
                shl_acc <= shl_acc + 16'd1;
            end else if (href_fall) begin
                x_rx <= 10'd0; p <= 2'd0;
                y <= y + 10'd1;
                have_prev <= 1'b0;          // SAD is per-line, not across the wrap
            end else if (byte_now) begin
                p <= p + 2'd1;

                case (slot)
                    2'd0: begin y0_r <= luma_in; m1 <= m0; m0 <= d_s1; end
                    2'd1: cb_r <= d_s1;
                    2'd2: begin y1_r <= luma_in; m1 <= m0; m0 <= d_s1; end
                    2'd3: cr_r <= d_s1;
                endcase

                if (p == 2'd3) begin
                    // The byte arriving ON this cycle has not reached its
                    // register yet, so take it from d_s1. Which byte that is
                    // depends on the order: YUYV ends on Cr, UYVY ends on Y1.
                    // Reading the register in both cases picks up the PREVIOUS
                    // group's value and corrupts every odd pixel in UYVY.
                    y0_q <= y0_r;
                    y1_q <= (slot == 2'd2) ? luma_in : y1_r;
                    cb_q <= cb_r;
                    cr_q <= (slot == 2'd3) ? d_s1    : cr_r;
                    gx   <= x_rx;
                    gy   <= y;
                    x_rx <= x_rx + 10'd2;
                    if ((x_rx + 10'd1) > xm) xm <= x_rx + 10'd1;
                    if (y > ym) ym <= y;
                end
            end

            // ---- the address port, driven by the emit phase ----
            if (e_active) begin
                case (ep)
                    2'd0: wr_addr <= addr0;   // read old pixel 0
                    2'd1: wr_addr <= addr1;   // read old pixel 1
                    2'd2: wr_addr <= addr0;   // write pixel 0
                    2'd3: wr_addr <= addr1;   // write pixel 1
                endcase
            end

            // ---- the writes ----
            if (rgb_valid) begin
                wr_data  <= {out_r, out_g, out_b};
                wr_en    <= 1'b1;
                pix_seen <= 1'b1;
                pix_cnt  <= pix_cnt + 20'd1;
                if (TEMPORAL != 0)
                    tdiff_acc <= tdiff_acc + {24'd0, tdif};
                if (luma_d2 < lmin_acc) lmin_acc <= luma_d2;
                if (luma_d2 > lmax_acc) lmax_acc <= luma_d2;
                prev_lum  <= luma_d2;
                have_prev <= 1'b1;
                if (have_prev) sad_acc <= sad_acc + {24'd0, lum_dif};
            end
        end
    end
// Observes values used on this same clock edge, no receive-path delay.
    assign debug_state={frame_cnt,y,x_rx,p,vs,href,byte_now,d_s1};
endmodule

`default_nettype wire
