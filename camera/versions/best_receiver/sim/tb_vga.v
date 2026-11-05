// -----------------------------------------------------------------------------
// tb_vga -- asserts the exact 640x480@60 numbers, then spot-checks the pattern.
//
// The timing assertions are deliberately literal (800, 525, 96 @ 656, 2 @ 490,
// 307200, 420000) rather than recomputed from the parameters -- a typo in a
// parameter should FAIL here, not be silently confirmed by arithmetic that
// shares the typo.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module tb_vga;

    integer errors = 0;

    task check_i;
        input [127:0] name;
        input integer got;
        input integer want;
        begin
            if (got !== want) begin
                $display("FAIL %0s: got %0d want %0d", name, got, want);
                errors = errors + 1;
            end else begin
                $display("  ok  %0s = %0d", name, got);
            end
        end
    endtask

    task check_rgb;
        input [127:0] name;
        input [11:0]  got;
        input [11:0]  want;
        begin
            if (got !== want) begin
                $display("FAIL %0s: got %03h want %03h", name, got, want);
                errors = errors + 1;
            end else begin
                $display("  ok  %0s = %03h", name, got);
            end
        end
    endtask

    // ---------------- DUT 1: vga_timing ----------------
    reg clk = 1'b0;
    reg rst = 1'b1;
    wire [9:0] hcnt, vcnt;
    wire active, hsync, vsync, frame_start;

    vga_timing dut (
        .clk(clk), .rst(rst),
        .hcnt(hcnt), .vcnt(vcnt),
        .active(active), .hsync(hsync), .vsync(vsync),
        .frame_start(frame_start)
    );

    always #20 clk = ~clk;          // 25 MHz, 40 ns period

    // ---------------- DUT 2: pattern_gen ----------------
    reg  [8:0] px = 9'd0;
    reg  [7:0] py = 8'd0;
    reg        pmode = 1'b0;
    reg  [8:0] poff = 9'd0;
    wire [11:0] prgb;

    pattern_gen pat (.x(px), .y(py), .mode(pmode), .offset(poff), .rgb(prgb));

    task pat_check;
        input [127:0] name;
        input [8:0]   ax;
        input [7:0]   ay;
        input         amode;
        input [11:0]  want;
        begin
            px = ax; py = ay; pmode = amode; poff = 9'd0;
            #1;
            check_rgb(name, prgb, want);
        end
    endtask

    // ---------------- measurement ----------------
    integer line_len, lines, hs_low, hs_start, vs_lines, vs_start;
    integer act_cnt, frame_cycles;

    initial begin
        $display("=== tb_vga start ===");

        repeat (4) @(posedge clk);
        rst = 1'b0;

        // ---- line length -------------------------------------------------
        $display("MARK phase1 line length");
        @(negedge clk);
        while (hcnt != 10'd0) @(negedge clk);
        line_len = 0;
        @(negedge clk);
        line_len = 1;
        while (hcnt != 10'd0) begin @(negedge clk); line_len = line_len + 1; end
        check_i("H total", line_len, 800);

        // ---- hsync width and position ------------------------------------
        $display("MARK phase2 hsync");
        while (hsync !== 1'b0) @(negedge clk);
        hs_start = hcnt;
        hs_low   = 0;
        while (hsync === 1'b0) begin hs_low = hs_low + 1; @(negedge clk); end
        check_i("hsync start hcnt", hs_start, 656);
        check_i("hsync width",      hs_low,   96);

        // ---- one full frame: lines, vsync, active pixels, total cycles ----
        $display("MARK phase3 frame sweep");
        // align to the very start of a frame
        while (!(hcnt == 10'd0 && vcnt == 10'd0)) @(negedge clk);

        lines        = 0;
        vs_lines     = 0;
        vs_start     = -1;
        act_cnt      = 0;
        frame_cycles = 0;

        begin : frame_sweep
            integer prev_v;
            prev_v = -1;
            forever begin
                if (active) act_cnt = act_cnt + 1;
                if (vcnt != prev_v) begin
                    lines  = lines + 1;
                    prev_v = vcnt;
                    if (vsync === 1'b0) begin
                        vs_lines = vs_lines + 1;
                        if (vs_start < 0) vs_start = vcnt;
                    end
                end
                frame_cycles = frame_cycles + 1;
                @(negedge clk);
                if (hcnt == 10'd0 && vcnt == 10'd0) disable frame_sweep;
            end
        end

        check_i("V total lines",   lines,        525);
        check_i("vsync start vcnt",vs_start,     490);
        check_i("vsync lines",     vs_lines,     2);
        check_i("active pixels",   act_cnt,      307200);
        check_i("cycles per frame",frame_cycles, 420000);

        // ---- pattern spot checks ----------------------------------------
        $display("MARK phase4 pattern bars");
        pat_check("bar0 white",   9'd0,   8'd0,   1'b0, 12'hFFF);
        pat_check("bar1 yellow",  9'd40,  8'd0,   1'b0, 12'hFF0);
        pat_check("bar2 cyan",    9'd80,  8'd0,   1'b0, 12'h0FF);
        pat_check("bar3 green",   9'd120, 8'd0,   1'b0, 12'h0F0);
        pat_check("bar4 magenta", 9'd160, 8'd0,   1'b0, 12'hF0F);
        pat_check("bar5 red",     9'd200, 8'd0,   1'b0, 12'hF00);
        pat_check("bar6 blue",    9'd240, 8'd0,   1'b0, 12'h00F);
        pat_check("bar7 black",   9'd280, 8'd0,   1'b0, 12'h000);
        pat_check("bar7 at 319",  9'd319, 8'd175, 1'b0, 12'h000);

        $display("MARK phase5 pattern ramps");
        pat_check("grey  lvl0",  9'd32,  8'd176, 1'b0, 12'h000);
        pat_check("grey  lvl15", 9'd272, 8'd176, 1'b0, 12'hFFF);
        pat_check("red   lvl15", 9'd272, 8'd192, 1'b0, 12'hF00);
        pat_check("green lvl15", 9'd272, 8'd208, 1'b0, 12'h0F0);
        pat_check("blue  lvl15", 9'd272, 8'd224, 1'b0, 12'h00F);
        pat_check("ramp off-x",  9'd0,   8'd200, 1'b0, 12'h000);

        $display("MARK phase6 pattern geometry");
        pat_check("geo corner",   9'd0,   8'd0,   1'b1, 12'hF00);
        pat_check("geo corner br",9'd319, 8'd239, 1'b1, 12'hF00);
        pat_check("geo border",   9'd100, 8'd0,   1'b1, 12'hFFF);
        pat_check("geo cross",    9'd160, 8'd100, 1'b1, 12'h0F0);
        pat_check("geo grid",     9'd16,  8'd17,  1'b1, 12'h444);
        pat_check("geo blank",    9'd17,  8'd17,  1'b1, 12'h000);

        // ---- bar offset wraps -------------------------------------------
        $display("MARK phase7 offset wrap");
        px = 9'd300; py = 8'd0; pmode = 1'b0; poff = 9'd40; #1;
        // 300+40 = 340 -> wraps to 20 -> bar 0 (white)
        check_rgb("offset wrap 300+40", prgb, 12'hFFF);

        $display("=== TESTS COMPLETE: %0d error(s) ===", errors);
        if (errors == 0) $display("=== ALL TESTS PASS ===");
        $finish;
    end

    // watchdog: one frame is 16.8 ms, so allow well past two frames
    initial begin
        #120_000_000;
        $display("WATCHDOG: stuck, errors so far %0d", errors);
        $finish;
    end

endmodule

`default_nettype wire
