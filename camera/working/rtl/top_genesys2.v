// Qualified sampled-input receiver: PCLK JA physical 1, D6 JB physical 8.
// Nov 4 diagnostic: manual 128-line exposure/1x gain preserved; SW7 records raw
// YUYV instead of converted RGB565. HDMI and the receiver datapath are unchanged.
// Slow divider 4; explicit rising-PCLK/active-high-HREF configuration.
// SCCB reader uses JB[3] SDA. 320x240 capture, 2x display over DVI-compatible
// TMDS on HDMI OUT. No temporal/median blur in this reference bring-up build.
`timescale 1ns / 1ps
`default_nettype none

module top_genesys2 #(
    parameter integer SIM_FAST_INIT = 0, // Testbench only; keep zero on board.
    parameter integer RGB565 = 0, // Build-time format selection, never a live switch.
    parameter integer REFERENCE_READOUT = 0
)(
    input  wire       sysclk_p,          // AD12, 200 MHz LVDS
    input  wire       sysclk_n,          // AD11
    input  wire [7:0] sw,
    input  wire       btnc,
    output wire [7:0] led,

    // ---- camera: order fixed by the PCB's male headers ----
    // This is NOT a layout choice. The camera board plugs straight into the
    // Pmod headers, so the signal at each position is whatever that PCB wires
    // there -- the same order the Basys 3 XDC records. In particular the data
    // bus is split across both connectors, so the "all data on one ribbon"
    // isolation that would remove the documented crosstalk path is not
    // available and the filters in cam_capture stay load-bearing.
    inout  wire [7:0] ja,
    inout  wire [7:0] jb,

    // ---- HDMI ----
    output wire [2:0] hdmi_tx_p,
    output wire [2:0] hdmi_tx_n,
    output wire       hdmi_tx_clk_p,
    output wire       hdmi_tx_clk_n,

    // ---- USB-UART bridge ----
    input wire        uart_tx_in,        // Y20, from USB bridge; FPGA INPUT
    output wire       uart_rx_out        // FPGA transmit; see README if silent
);
    // ---------------- clocking ----------------
    wire clk200, clk24, clk_pix, clk_pix5x, locked;
    wire clk_cam=clk200; // All capture writes use fabric clock enables.
    clk_gen clk_gen_i (
        .sysclk_p(sysclk_p), .sysclk_n(sysclk_n),
        .clk200(clk200), .clk24(clk24),
        .clk_pix(clk_pix), .clk_pix5x(clk_pix5x), .locked(locked)
    );

    // ---------------- camera pin map ----------------
    // Positions are Pmod 1,2,3,4,7,8,9,10 -> index 0..7.
    //   JA   D6  D8  XC  HS  |  D4  D2  PD  RT
    //   JB   D7  D5  D3  SDA |  D9  PC  VS  SCL
    // cam_d[7:0] = D9 D8 D7 D6 D5 D4 D3 D2, the upper 8 of the sensor's 10.
    wire        cam_pclk_raw = ja[0];
    wire        cam_vsync    = jb[6];
    wire        cam_href     = ja[3];
    wire [7:0]  cam_d = { jb[4],  // D9 -> d[7]
                          ja[1],  // D8 -> d[6]
                          jb[0],  // D7 -> d[5]
                          jb[5],  // D6 -> d[4], swapped with PCLK
                          jb[1],  // D5 -> d[3]
                          ja[4],  // D4 -> d[2]
                          jb[2],  // D3 -> d[1]
                          ja[5] };// D2 -> d[0]
    wire        cam_pwdn, cam_reset_n;
    wire        scl_low, sda_low;
    wire        cam_xclk;

    assign ja[2] = cam_xclk;
    assign ja[6] = cam_pwdn;
    assign ja[7] = cam_reset_n;
    assign jb[3] = sda_low ? 1'b0 : 1'bz;   // breakout has built-in pull-ups
    assign jb[7] = scl_low ? 1'b0 : 1'bz;

    // Historical baseline description (superseded by dedicated-PCLK wiring):
    // No BUFG on PCLK: it is sampled as data. Connector position 8 lands on
    // jb[5] = U25 = IO_L14N_T2_SRCC_14, the N side of a pair, and 7-series
    // accepts a single-ended clock input only on the P side. That rule is not
    // overridable by CLOCK_DEDICATED_ROUTE, which governs routing instead.

    // ODDR, not a plain assign: the correct way to drive a clock off-chip, and
    // it keeps XCLK off general fabric routing.
    ODDR #(.DDR_CLK_EDGE("SAME_EDGE"), .INIT(1'b0), .SRTYPE("ASYNC")) xclk_oddr (
        .Q(cam_xclk), .C(clk24), .CE(1'b1), .D1(1'b1), .D2(1'b0), .R(1'b0), .S(1'b0)
    );

    // ---------------- switches ----------------
    // sw0 overlay   sw1 sensor test bar   sw2 UYVY byte order
    // sw3 full-range colour               sw4 YVYU (U/V order)
    reg [1:0] s0 = 0, s1 = 0, s2 = 0, s3 = 0, s4 = 0, s5 = 0;
    always @(posedge clk200) begin
        s1 <= {s1[0], sw[1]}; s2 <= {s2[0], sw[2]};
        s3 <= {s3[0], sw[3]}; s4 <= {s4[0], sw[4]};
    end
    always @(posedge clk_pix) begin
        s0 <= {s0[0], sw[0]};
        s5 <= {s5[0], sw[5]};
    end
    wire overlay_en = s0[1];
    wire testbar    = s1[1];
    wire uyvy_sel   = s2[1];
    wire full_range = s3[1];
    wire vyuy_sel   = s4[1];
    wire testpat_en = s5[1];

    // ---------------- reset + camera watchdog ----------------
    // The init sequence runs once at power-up. If the sensor loses power (a hot
    // unplug during bring-up is routine) it comes back with DEFAULT registers
    // and nothing reconfigures it: stable PCLK, VSYNC at ~178 kHz, no frames.
    // Re-run init when a sane VSYNC is absent for about a second.
    reg [3:0]  rst200_sr = 4'hF;
    reg [1:0]  btn_s     = 2'b00;
    reg [27:0] wd_cnt    = 28'd0;
    reg [15:0] wd_vs     = 16'd0;
    reg        wd_reinit = 1'b0;
    reg [2:0]  wd_hold   = 3'd5;
    reg [1:0]  wd_vsync  = 2'b00;

    always @(posedge clk200) btn_s <= {btn_s[0], btnc};
    always @(posedge clk200) wd_vsync <= {wd_vsync[0], cam_vsync};

    always @(posedge clk200) begin
        wd_reinit <= 1'b0;
        if (!locked) begin
            wd_cnt <= 0; wd_vs <= 0; wd_hold <= 3'd5;
        end else begin
            if (wd_vsync[0] ^ wd_vsync[1]) wd_vs <= wd_vs + 16'd1;
            if (wd_cnt == 28'd200_000_000) begin        // 1 s at 200 MHz
                wd_cnt <= 0;
                // COOLDOWN is essential. Without it the watchdog self-sustains:
                // during the ~150 ms re-init the sensor sits in reset with
                // indeterminate outputs, the next window reads that as a fault,
                // and it re-inits forever. Observed exactly that on the Basys 3.
                if (wd_hold != 3'd0)      wd_hold <= wd_hold - 3'd1;
                else if (wd_vs == 16'd0) begin
                    wd_reinit <= 1'b1; wd_hold <= 3'd5;
                end
                wd_vs <= 0;
            end else wd_cnt <= wd_cnt + 28'd1;
        end
    end

    always @(posedge clk200) begin
        if (!locked || btn_s[1] || wd_reinit) rst200_sr <= 4'hF;
        else                                  rst200_sr <= {rst200_sr[2:0], 1'b0};
    end
    wire rst200 = rst200_sr[3];

    // Reset camera domain even when its clock is stopped during sensor reset.
    (* ASYNC_REG = "TRUE" *) reg [3:0] rstcam_sr = 4'hF;
    always @(posedge clk_cam or posedge rst200) begin
        if (rst200) rstcam_sr <= 4'hF;
        else rstcam_sr <= {rstcam_sr[2:0],1'b0};
    end
    wire rst_cam = rstcam_sr[3];
    // Historical baseline description:
    // No separate capture reset: capture oversamples PCLK, so it lives in the
    // clk200 domain alongside SCCB, the probe and the UART. One domain, one
    // reset, and no clock crossing between capture and control at all.

    reg [3:0] rstpix_sr = 4'hF;
    always @(posedge clk_pix) rstpix_sr <= {rstpix_sr[2:0], ~locked};
    wire rst_pix = rstpix_sr[3];

    // ---------------- SCCB + init ----------------
    wire        sccb_busy, sccb_done, sccb_nack, sccb_start, sccb_rw;
    wire [7:0]  sccb_rdata, sccb_wdata;
    wire [15:0] sccb_addr;
    wire [15:0] chip_id;
    wire        id_valid, init_done, nack_seen;
    wire [7:0]  table_index;

    // 10 kHz, not 100 kHz. Costs ~150 ms of init instead of ~16 ms, which is
    // irrelevant, and buys 10x the settling margin on a capacitive bus. On a
    // ribbon at 100 kHz every read bit sampled before SDA had risen and the
    // chip ID came back a consistent 0x0000 -- indistinguishable from a short
    // to ground. 10 kHz read it correctly over the same cable.
    sccb_master #(.CLK_HZ(200_000_000), .SCL_HZ(SIM_FAST_INIT ? 2_000_000 : 10_000)) sccb_i (
        .clk(clk200), .rst(rst200),
        .start(sccb_start), .rw(sccb_rw),
        .reg_addr(sccb_addr), .wr_data(sccb_wdata), .rd_data(sccb_rdata),
        .busy(sccb_busy), .done(sccb_done), .nack(sccb_nack),
        .scl_low(scl_low), .sda_low(sda_low), .sda_in(jb[3])
    );

    wire [383:0] config_readback;
    wire [47:0] config_read_nack;
    // SW0 still controls the overlay; its rising edge also refreshes read-only
    // diagnostics after the camera settles. It never changes sensor settings.
    (* ASYNC_REG="TRUE" *) reg [1:0] debug_refresh_sync = 0;
    always @(posedge clk200) begin
        if (rst200) debug_refresh_sync <= 0;
        else debug_refresh_sync <= {debug_refresh_sync[0],sw[0]};
    end
    wire ctrl_valid,ctrl_rw,ctrl_ready,ctrl_done,ctrl_nack;
    wire [15:0] ctrl_addr; wire [7:0] ctrl_wdata,ctrl_rdata;
    ov5640_init #(.CLK_HZ(SIM_FAST_INIT ? 10_000 : 200_000_000),.RGB565(RGB565),.REFERENCE_READOUT(REFERENCE_READOUT)) init_i (
        .clk(clk200), .rst(rst200), .debug_refresh(debug_refresh_sync[1]), .testbar(testbar), .vyuy(vyuy_sel),
        .host_valid(ctrl_valid),.host_rw(ctrl_rw),.host_addr(ctrl_addr),
        .host_wdata(ctrl_wdata),.host_ready(ctrl_ready),.host_done(ctrl_done),
        .host_rdata(ctrl_rdata),.host_nack(ctrl_nack),
        .sccb_start(sccb_start), .sccb_rw(sccb_rw),
        .sccb_addr(sccb_addr), .sccb_wdata(sccb_wdata),
        .sccb_rdata(sccb_rdata), .sccb_busy(sccb_busy),
        .sccb_done(sccb_done), .sccb_nack(sccb_nack),
        .cam_pwdn(cam_pwdn), .cam_reset_n(cam_reset_n),
        .chip_id(chip_id), .id_valid(id_valid),
        .init_done(init_done), .nack_seen(nack_seen), .table_index(table_index),
        .debug_readback(config_readback), .debug_read_nack(config_read_nack)
    );

    // ---------------- liveness (clk200, async sampling) ----------------
    localparam integer ALIVE_LIMIT = 1_000_000;    // 10 ms at 100 MHz

    wire [7:0] d_alive;
    genvar gi;
    generate
        for (gi = 0; gi < 8; gi = gi + 1) begin : g_dalive
            reg [1:0]  s   = 2'b00;
            reg [19:0] cnt = 20'd0;
            reg        alv = 1'b0;
            always @(posedge clk200) begin
                s <= {s[0], cam_d[gi]};
                if (s[0] ^ s[1]) begin cnt <= 20'd0; alv <= 1'b1; end
                else if (cnt >= ALIVE_LIMIT) alv <= 1'b0;
                else cnt <= cnt + 20'd1;
            end
            assign d_alive[gi] = alv;
        end
    endgenerate

    reg [1:0]  p_s = 0, v_s = 0;
    reg [19:0] p_cnt = 0, v_cnt = 0;
    reg        pclk_alive = 1'b0, vs_moving = 1'b0;
    always @(posedge clk200) begin
        p_s <= {p_s[0], cam_pclk_raw};
        v_s <= {v_s[0], cam_vsync};
        if (p_s[0] ^ p_s[1]) begin p_cnt <= 0; pclk_alive <= 1'b1; end
        else if (p_cnt >= ALIVE_LIMIT) pclk_alive <= 1'b0; else p_cnt <= p_cnt + 1;
        if (v_s[0] ^ v_s[1]) begin v_cnt <= 0; vs_moving <= 1'b1; end
        else if (v_cnt >= ALIVE_LIMIT) vs_moving <= 1'b0; else v_cnt <= v_cnt + 1;
    end

    // ---------------- capture (200 MHz oversampling domain) ----------------
    wire [48:0] capture_debug;
    wire clean_tick,clean_href,clean_vsync;
    wire[7:0]clean_data;
    dvp_clean_sampler #(.MAJORITY_FILTER(REFERENCE_READOUT == 5)) sampler_i(.clk(clk200),.rst(rst200),
      .pclk(cam_pclk_raw),.href(cam_href ^ href_invert_c[1]),.vsync(cam_vsync),.data(cam_d),
      .tick(clean_tick),.sample_data(clean_data),.sample_href(clean_href),.sample_vsync(clean_vsync));
    wire [16:0] cwr_addr;
    wire [23:0] cwr_data, fb_old;
    wire        cwr_en;
    wire [15:0] cam_frame_cnt, shlines;
    wire        href_seen, pix_seen, vs_clean;
    wire [19:0] pix_pf;
    wire [9:0]  xmax_raw, ymax_raw;
    wire [7:0]  lmin, lmax;
    wire [31:0] lsad, tdiff;

    (* ASYNC_REG = "TRUE" *) reg [1:0] uyvy_c=0, full_c=0, href_invert_c=0;
    always @(posedge clk_cam) begin
        uyvy_c <= {uyvy_c[0],uyvy_sel}; full_c <= {full_c[0],full_range};
        href_invert_c <= {href_invert_c[0],sw[6]};
    end
    cam_capture #(
        .H(320), .V(240), .RGB565(RGB565), .SOURCE_SYNC(0), .SAMPLE_TICK_MODE(1), .SYNC_FILTER(0), .VSYNC_ACTIVE_HIGH(1),
        .MIN_LINE_PX(280), .MEDIAN3(0), .TEMPORAL(0)
    ) cap_i (
        .clk(clk_cam), .rst(rst_cam), .pclk_i(cam_pclk_raw),
        .vsync_i(clean_vsync), .href_i(clean_href), .d_i(clean_data), .sample_strobe(clean_tick),
        .uyvy(uyvy_c[1]), .full_range(full_c[1]),
        .wr_addr(cwr_addr), .wr_data(cwr_data), .wr_en(cwr_en), .fb_old(fb_old),
        .frame_cnt(cam_frame_cnt), .href_seen(href_seen), .pix_seen(pix_seen),
        .pix_per_frame(pix_pf), .x_max(xmax_raw), .y_max(ymax_raw),
        .luma_min(lmin), .luma_max(lmax), .luma_sad(lsad),
        .temporal_diff(tdiff), .short_lines(shlines), .vsync_clean(vs_clean), .debug_state(capture_debug)
    );


    wire [159:0] cam_snapshot;
    camera_status_snapshot #(.WIDTH(160)) telemetry_i (
        .src_clk(clk_cam),.src_rst(rst_cam),
        .src_data({6'd0,cam_frame_cnt,shlines,lmin,lmax,xmax_raw,ymax_raw,pix_pf,lsad,tdiff,href_seen,pix_seen}),
        .dst_clk(clk200),.dst_rst(rst200),.request(m_tick),.dst_data(cam_snapshot));
    wire [15:0] fc_200, shl_200;
    wire [7:0] lmin_200,lmax_200;
    wire [9:0] xm_200,ym_200;
    wire [19:0] pf_200;
    wire [31:0] sad_200,tdiff_200;
    wire href_200,pix_200;
    assign {fc_200,shl_200,lmin_200,lmax_200,xm_200,ym_200,pf_200,sad_200,tdiff_200,href_200,pix_200}=cam_snapshot[153:0];

    // Snapshot bridges new camera-clock counters coherently into clk200.
    // Historical baseline description:
    // No synchronisers into the UART domain any more: capture and control are
    // both clk200 now, so these are plain wires. The only crossing left is
    // into clk_pix for the on-screen overlay.
    // and into clk_pix for the on-screen overlay
    reg [19:0] pf_p0 = 0, pf_p1 = 0;
    reg [9:0]  xm_p0 = 0, xm_p1 = 0, ym_p0 = 0, ym_p1 = 0;
    reg [1:0]  href_s = 0, pix_s = 0;
    always @(posedge clk_pix) begin
        pf_p0 <= pf_200;   pf_p1 <= pf_p0;
        xm_p0 <= xm_200; xm_p1 <= xm_p0;
        ym_p0 <= ym_200; ym_p1 <= ym_p0;
        href_s <= {href_s[0], href_200};
        pix_s  <= {pix_s[0],  pix_200};
    end

    // ---------------- display ----------------
    wire [9:0] hcnt, vcnt;
    wire       active, hsync_n, vsync_n, frame_start;
    vga_timing vga_i (
        .clk(clk_pix), .rst(rst_pix), .hcnt(hcnt), .vcnt(vcnt),
        .active(active), .hsync(hsync_n), .vsync(vsync_n),
        .frame_start(frame_start)
    );

    // 320x240 buffer shown 2x into 640x480: each stored pixel is a 2x2 block.
    wire [8:0]  lx = hcnt[9:1];
    wire [7:0]  ly = vcnt[8:1];
    wire [16:0] rd_addr = active ? (ly * 17'd320 + {8'd0, lx}) : 17'd0;
    wire [23:0] fb_dout;

    frame_buffer fb_i (
        .wr_clk(clk_cam), .wr_en(cwr_en), .wr_addr(cwr_addr),
        .wr_data(cwr_data), .wr_dout(fb_old),
        .rd_clk(clk_pix), .rd_addr(rd_addr), .rd_data(fb_dout)
    );

    // bit7 is a constant marker: it confirms the right stripe is being read
    wire [7:0] status = {1'b1, pix_s[1], vs_moving, href_s[1],
                         ~nack_seen, id_valid, init_done, pclk_alive};

    wire        ov_sel;
    wire [11:0] ov_rgb;
    debug_overlay ov_i (
        .x(lx), .y(ly), .chip_id(chip_id), .d_alive(d_alive), .status(status),
        .pix_per_frame(pf_p1[19:4]),
        .x_max({6'b0, xm_p1}), .y_max({6'b0, ym_p1}),
        .is_overlay(ov_sel), .rgb(ov_rgb)
    );

    // The overlay is RGB444, carried over unchanged from the Basys 3 where that
    // was the display's native depth. Nibble replication (0xA -> 0xAA) rather
    // than a left shift, so full scale stays full scale.
    wire [23:0] ov_rgb888 = {{2{ov_rgb[11:8]}}, {2{ov_rgb[7:4]}}, {2{ov_rgb[3:0]}}};

    reg [23:0] ov_q  = 24'h0;
    reg        ovs_q = 1'b0;
    reg        hs_q = 1'b1, vs_q = 1'b1, act_q = 1'b0;
    always @(posedge clk_pix) begin
        ov_q  <= ov_rgb888;
        ovs_q <= ov_sel;
        hs_q  <= hsync_n;
        vs_q  <= vsync_n;
        act_q <= active;
    end

    // SW5: an internal colour-bar source that never touches the camera. This
    // is the first thing to try on a board that shows nothing: bars on screen
    // mean clocking, TMDS encoding, serialisation and the cable are all good
    // and the fault is upstream in capture. Without it, "no picture" is one
    // undifferentiated failure spanning six modules.
    wire [11:0] pat_rgb;
    pattern_gen pat_i (.x(lx), .y(ly), .mode(1'b0), .offset(9'd0), .rgb(pat_rgb));
    wire [23:0] pat_rgb888 =
        {{2{pat_rgb[11:8]}}, {2{pat_rgb[7:4]}}, {2{pat_rgb[3:0]}}};

    reg [23:0] pat_q = 24'h0;
    always @(posedge clk_pix) pat_q <= pat_rgb888;

    wire [23:0] src_q   = testpat_en ? pat_q : fb_dout;
    wire [23:0] pix_sel = (ovs_q && overlay_en) ? ov_q : src_q;
    wire [23:0] rgb     = act_q ? pix_sel : 24'h000000;

    // TMDS carries actual sync levels. Preserve negative VGA sync polarity.
    hdmi_out hdmi_i (
        .clk_pix(clk_pix), .clk_pix5x(clk_pix5x), .rst(rst_pix),
        .red(rgb[23:16]), .green(rgb[15:8]), .blue(rgb[7:0]),
        .hsync(hs_q), .vsync(vs_q), .de(act_q),
        .tmds_p(hdmi_tx_p), .tmds_n(hdmi_tx_n),
        .tmds_clk_p(hdmi_tx_clk_p), .tmds_clk_n(hdmi_tx_clk_n)
    );

    // ---------------- DVP measurement over UART ----------------
    wire [31:0] m_pclk_hz, m_vs_hz, m_href_ln, m_href_len, m_hi_len;
    wire        m_tick;
    dvp_probe #(.CLK_HZ(200_000_000)) probe_i (
        .clk(clk200), .rst(rst200), .pclk_i(cam_pclk_raw),
        .vsync_i(cam_vsync), .href_i(cam_href),
        .pclk_hz(m_pclk_hz), .vs_hz(m_vs_hz), .href_ln(m_href_ln),
        .href_len(m_href_len), .hi_len(m_hi_len), .tick_1s(m_tick)
    );

    wire [31:0] hp_vraw,hp_hraw,hp_vclean,hp_hclean;
    wire [31:0] hp_vhigh,hp_vmaxhi,hp_vmaxlo,hp_hhigh,hp_hmaxhi,hp_hmaxlo;
    sync_health_probe #(.CLK_HZ(200_000_000)) health_i (
        .clk(clk200),.rst(rst200),.v_i(cam_vsync),.h_i(cam_href),
        .vraw(hp_vraw),.hraw(hp_hraw),.vclean(hp_vclean),.hclean(hp_hclean),
        .vhigh(hp_vhigh),.vmaxhi(hp_vmaxhi),.vmaxlo(hp_vmaxlo),
        .hhigh(hp_hhigh),.hmaxhi(hp_hmaxhi),.hmaxlo(hp_hmaxlo));
    reg [2:0] diagnostic_page = 0;
    always @(posedge clk200) begin
        if (rst200) diagnostic_page <= 0;
        else if (m_tick) diagnostic_page <= diagnostic_page == 4 ? 0 : diagnostic_page+1'b1;
    end
    reg [255:0] diagnostic_words;
    always @* begin
        case (diagnostic_page)
        0: diagnostic_words = {hp_hclean,hp_vclean,hp_hraw,hp_vraw,m_pclk_hz,
                              {16'd0,sw,led},{16'd0,chip_id},32'hD1640000};
        1: diagnostic_words = {32'd200000000,hp_hmaxlo,hp_hmaxhi,hp_hhigh,
                              hp_vmaxlo,hp_vmaxhi,hp_vhigh,32'hD1640001};
        2: diagnostic_words = {{8'd0,config_read_nack[23:0]},config_readback[191:0],32'hD1640002};
        4: diagnostic_words = {{8'd0,config_read_nack[47:24]},config_readback[383:192],32'hD1640004};
        default: diagnostic_words = {m_href_ln,m_hi_len,m_href_len,
                              {6'd0,ym_200,6'd0,xm_200},{12'd0,pf_200},
                              {16'd0,fc_200},{lmin_200,lmax_200,shl_200},32'hD1640003};
        endcase
    end
    wire [7:0] u_data; wire u_stb, u_busy;
    (* ASYNC_REG="TRUE" *)reg[1:0] record_mode_sync=0;
    always @(posedge clk200)record_mode_sync<={record_mode_sync[0],sw[7]};
    wire record_mode=record_mode_sync[1];
    wire report_busy,record_go;wire[255:0] record_words;
    wire raw_we;wire[16:0]raw_addr;wire[15:0]raw_word;
    yuv_word_observer raw_observer(.clk(clk_cam),.rst(rst_cam),.state(capture_debug),
      .wr_en(raw_we),.wr_addr(raw_addr),.wr_data(raw_word));
    frame_snapshot #(.RAW_WORDS(1),.RAW_MAGIC(RGB565 ? 32'h52353635 : 32'h59555630)) record_i(.src_clk(clk_cam),.src_rst(rst_cam),
       .dst_clk(clk200),.dst_rst(rst200),.arm(sw[7]&&init_done),
       .pixel_we(raw_we),.pixel_addr(raw_addr),.pixel_rgb({8'd0,raw_word}),
       .frame_count(cam_frame_cnt),.report_busy(report_busy),
       .words(record_words),.go(record_go));
    // Commands are blocked while SW7 raw recording is active. During recording
    // the original report path has sole ownership; no response can consume a
    // snapshot's packet handshake. Outside recording, replies get packet priority.
    localparam integer CONTROL_BAUD = SIM_FAST_INIT ? 20_000_000 : 115200;
    wire [7:0] rx_byte; wire rx_valid,rx_error;
    wire reply_valid,reply_take; wire [255:0] reply_words;
    uart_rx #(.CLK_HZ(200_000_000),.BAUD(CONTROL_BAUD)) urx_i(
      .clk(clk200),.rst(rst200),.rx(uart_tx_in),.data(rx_byte),
      .valid(rx_valid),.error(rx_error));
    camera_uart_control #(.CLK_HZ(200_000_000)) control_i(
      .clk(clk200),.rst(rst200),.rx_data(rx_byte),.rx_valid(rx_valid),
      .rx_error(rx_error),.blocked(record_mode),
      .cfg_valid(ctrl_valid),.cfg_rw(ctrl_rw),.cfg_addr(ctrl_addr),
      .cfg_wdata(ctrl_wdata),.cfg_ready(ctrl_ready),.cfg_done(ctrl_done),
      .cfg_rdata(ctrl_rdata),.cfg_nack(ctrl_nack),
      .reply_valid(reply_valid),.reply_words(reply_words),.reply_take(reply_take));
    assign reply_take = reply_valid && !record_mode && !report_busy && !u_busy && !u_stb;
    wire report_go = record_mode ? record_go : (reply_take || (!reply_valid && m_tick));
    wire [255:0] report_words = record_mode ? record_words :
                                (reply_valid ? reply_words : diagnostic_words);
    uart_report rpt_i (
        .clk(clk200), .rst(rst200), .go(report_go),
        .words(report_words),
        .tx_data(u_data), .tx_stb(u_stb), .tx_busy(u_busy), .busy(report_busy)
    );
    uart_tx #(.CLK_HZ(200_000_000), .BAUD(CONTROL_BAUD)) utx_i (
        .clk(clk200), .rst(rst200), .data(u_data), .stb(u_stb),
        .tx(uart_rx_out), .busy(u_busy)
    );

    assign led[0] = pclk_alive;
    assign led[1] = locked;
    assign led[2] = id_valid;
    assign led[3] = init_done;
    assign led[4] = nack_seen;
    assign led[5] = vs_moving;
    assign led[6] = pix_200;
    assign led[7] = |d_alive;
endmodule

`default_nettype wire
