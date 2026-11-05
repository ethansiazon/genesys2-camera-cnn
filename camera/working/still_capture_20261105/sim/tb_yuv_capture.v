// -----------------------------------------------------------------------------
// tb_yuv_capture -- the whole capture path, byte stream to stored RGB.
//
// Checks the PLUMBING, not the colour maths -- tb_ycbcr already proves the
// conversion against reference points. What this proves is harder to eyeball
// and easier to get wrong: that the right luma meets the right chroma at the
// right address, that both byte orders work, that the four-phase read/write
// schedule never collides, and above all that the LAST GROUP OF EVERY LINE is
// emitted. That last one is the bug this testbench was written to catch: the
// emit lags the receive by one group, so tying it to HREF drops two pixels on
// every line -- 480 a frame, which reads as a ragged right edge and is easy to
// mistake for a windowing error.
//
// TEMPORAL and MEDIAN3 are off so stored values are exactly predictable. Both
// are tested for their own behaviour elsewhere; mixing them in here would turn
// an exact comparison into a tolerance.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module tb_yuv_capture;
    localparam integer H = 16, V = 4;

    integer errors = 0;
    task ck; input [255:0] n; input integer got; input integer want; begin
        if (got !== want) begin
            $display("FAIL %0s: got %0d want %0d", n, got, want); errors=errors+1;
        end else $display("  ok  %0s = %0d", n, got);
    end endtask

    // Two clocks now: the fabric clock the design runs on, and PCLK as an
    // asynchronous DATA signal. 5 ns and 70 ns gives 14 fabric samples per PCLK
    // period -- the same ratio the real board sees at 200 MHz and 14.4 MHz.
    reg clk  = 1'b0;  always #2.5 clk  = ~clk;      // 200 MHz fabric
    reg pclk = 1'b0;  always #35  pclk = ~pclk;     // ~14.3 MHz DVP clock
    reg rst = 1'b1;
    reg vsync = 1'b0, href = 1'b0;
    reg [7:0] d = 8'h00;
    reg uyvy = 1'b0;
    integer frames = 0, gx, gy, k;

    // ---- the source pattern ----
    function [7:0] src_y;  input integer x; input integer yy;
        begin src_y = 8'd16 + ((x * 7 + yy * 13) % 180); end endfunction
    function [7:0] src_cb; input integer x; input integer yy;
        begin src_cb = 8'd64 + ((x * 3 + yy * 5) % 120); end endfunction
    function [7:0] src_cr; input integer x; input integer yy;
        begin src_cr = 8'd70 + ((x * 11 + yy * 2) % 110); end endfunction

    // ---- the reference conversion, same integer maths as the RTL ----
    function [7:0] clamp8; input integer v;
        begin
            if (v < 0)        clamp8 = 8'h00;
            else if (v > 255) clamp8 = 8'hFF;
            else              clamp8 = v[7:0];
        end
    endfunction
    function [23:0] ref_rgb; input integer yv; input integer cbv; input integer crv;
        integer yd, cbd, crd;
        begin
            yd = 298 * (yv - 16); cbd = cbv - 128; crd = crv - 128;
            ref_rgb = { clamp8((yd + 409*crd + 128) >>> 8),
                        clamp8((yd - 208*crd - 100*cbd + 128) >>> 8),
                        clamp8((yd + 516*cbd + 128) >>> 8) };
        end
    endfunction

    // ---- DVP generator: four bytes per pixel pair ----
    task emit_group; input integer x; input integer yy;
        reg [7:0] b0, b1, b2, b3;
        begin
            if (!uyvy) begin
                b0 = src_y(x, yy);   b1 = src_cb(x, yy);
                b2 = src_y(x+1, yy); b3 = src_cr(x, yy);
            end else begin
                b0 = src_cb(x, yy);  b1 = src_y(x, yy);
                b2 = src_cr(x, yy);  b3 = src_y(x+1, yy);
            end
            d = b0; @(negedge pclk);
            d = b1; @(negedge pclk);
            d = b2; @(negedge pclk);
            d = b3; @(negedge pclk);
        end
    endtask

    initial begin
        forever begin
            // VSYNC must outlast the integrator's VS_HI of 48 PCLK cycles
            // VSYNC must outlast the integrator's VS_HI, which is now counted
            // in FABRIC cycles (96 by default). 24 PCLK periods is 336 of them.
            vsync = 1'b1; repeat (24) @(negedge pclk);
            vsync = 1'b0; repeat (24) @(negedge pclk);
            for (gy = 0; gy < V; gy = gy + 1) begin
                href = 1'b1;
                for (gx = 0; gx < H; gx = gx + 2) emit_group(gx, gy);
                href = 1'b0; repeat (24) @(negedge pclk);
            end
            frames = frames + 1;
        end
    end

    // ---- DUT + a real frame buffer ----
    wire [16:0] wa; wire [23:0] wd, fb_old; wire we;
    wire [15:0] fc, shl; wire hs, ps;
    wire [19:0] ppf; wire [9:0] xm, ym;
    wire [7:0] lmn, lmx; wire [31:0] lsad, tdiff; wire vsc;

    cam_capture #(.H(H), .V(V), .VSYNC_ACTIVE_HIGH(1), .MIN_LINE_PX(12),
                  .MEDIAN3(0), .TEMPORAL(0)) dut (
        .clk(clk), .rst(rst), .pclk_i(pclk),
        .vsync_i(vsync), .href_i(href), .d_i(d),
        .uyvy(uyvy), .full_range(1'b0),
        .wr_addr(wa), .wr_data(wd), .wr_en(we), .fb_old(fb_old),
        .frame_cnt(fc), .href_seen(hs), .pix_seen(ps), .pix_per_frame(ppf),
        .x_max(xm), .y_max(ym), .luma_min(lmn), .luma_max(lmx),
        .luma_sad(lsad), .temporal_diff(tdiff), .short_lines(shl),
        .vsync_clean(vsc));

    frame_buffer #(.H(H), .V(V), .DEPTH(H*V), .AW(17), .DW(24)) fb (
        .wr_clk(clk), .wr_en(we), .wr_addr(wa), .wr_data(wd), .wr_dout(fb_old),
        .rd_clk(clk), .rd_addr(17'd0), .rd_data());

    // real BRAM powers up to zero; an uninitialised sim array is X
    // Each physical memory bank initializes itself to zero.

    // shadow, to tell "never written" apart from "written wrong"
    reg        wrote [0:H*V-1];
    reg [23:0] shadow[0:H*V-1];
    integer    oob = 0;
    always @(posedge clk) if (we) begin
        if (wa < H*V) begin wrote[wa] <= 1'b1; shadow[wa] <= wd; end
        else oob = oob + 1;
    end

    integer target, x, yy, bad, missing;
    task wait_frames; input integer n; begin
        target = frames + n; wait (frames >= target); repeat (200) @(posedge clk);
    end endtask

    // The expected value is hoisted into a variable rather than called inside
    // the comparison. With the call inline, xsim reported every pixel as wrong
    // while printing got and want as bit-identical -- a function-evaluation
    // quirk, not a data problem. Hoisting is clearer anyway.
    reg [23:0] expct;
    task check_image; input [255:0] label;
        begin
            bad = 0; missing = 0;
            for (yy = 0; yy < V; yy = yy + 1)
              for (x = 0; x < H; x = x + 1) begin
                expct = ref_rgb(src_y(x, yy), src_cb(x & ~1, yy), src_cr(x & ~1, yy));
                if (!wrote[yy*H + x]) begin
                    if (missing < 5) $display("FAIL %0s: pixel (%0d,%0d) never written",
                                               label, x, yy);
                    missing = missing + 1;
                end else if (shadow[yy*H + x] !== expct) begin
                    if (bad < 5) $display("FAIL %0s: pixel (%0d,%0d) got %06h want %06h",
                                           label, x, yy, shadow[yy*H+x], expct);
                    bad = bad + 1;
                end
              end
        end
    endtask

    initial begin
        $display("=== tb_yuv_capture start ===");
        for (k = 0; k < H*V; k = k + 1) wrote[k] = 1'b0;
        repeat (20) @(posedge clk); rst = 1'b0;

        $display("MARK A: YUYV byte order");
        wait_frames(3);
        ck("pixels per frame", ppf, H*V);
        ck("x_max (last pixel index)", xm, H-1);
        ck("y_max", ym, V-1);
        ck("short lines on clean HREF", shl, 0);
        ck("writes outside the buffer", oob, 0);
        check_image("YUYV");
        ck("YUYV pixels never written", missing, 0);
        ck("YUYV pixels wrong", bad, 0);

        $display("MARK B: UYVY byte order");
        for (k = 0; k < H*V; k = k + 1) wrote[k] = 1'b0;
        uyvy = 1'b1;
        wait_frames(3);
        check_image("UYVY");
        ck("UYVY pixels never written", missing, 0);
        ck("UYVY pixels wrong", bad, 0);

        $display("=== TESTS COMPLETE: %0d error(s) ===", errors);
        if (errors == 0) $display("=== ALL TESTS PASS ===");
        $finish;
    end

    initial begin
        #60_000_000; $display("WATCHDOG: stuck, errors so far %0d", errors); $finish;
    end
endmodule

`default_nettype wire
