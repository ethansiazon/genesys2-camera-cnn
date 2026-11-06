// -----------------------------------------------------------------------------
// tb_ycbcr -- colour conversion against hand-computable reference points.
//
// Both coefficient sets get tested, because the switch that selects them exists
// precisely because we cannot know from here which one the sensor emits. If
// only the default were tested, flipping the switch on the bench would be
// flipping into untested logic.
//
// The endpoints matter most. Studio swing maps Y=16 to black and Y=235 to
// white; getting the offset or the 1.164 gain wrong still produces a picture,
// just one with crushed shadows or clipped highlights -- the failure is subtle
// enough to be mistaken for a sensor exposure problem, which is exactly the
// kind of wrong turn worth spending a testbench to avoid.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module tb_ycbcr;
    integer errors = 0;

    task near; input [255:0] n; input integer got; input integer want;
                input integer tol;
        begin
            if (got < want - tol || got > want + tol) begin
                $display("FAIL %0s: got %0d want %0d +/-%0d", n, got, want, tol);
                errors = errors + 1;
            end else $display("  ok  %0s = %0d (want %0d +/-%0d)", n, got, want, tol);
        end
    endtask

    reg clk = 1'b0; always #5 clk = ~clk;
    reg rst = 1'b1;
    reg full_range = 1'b0;
    reg [7:0] y = 8'd0, cb = 8'd128, cr = 8'd128;
    reg valid_i = 1'b0;
    wire [7:0] r, g, b;
    wire valid_o;

    ycbcr2rgb dut (.clk(clk), .rst(rst), .full_range(full_range),
                   .y(y), .cb(cb), .cr(cr), .valid_i(valid_i),
                   .r(r), .g(g), .b(b), .valid_o(valid_o));

    task convert; input [7:0] yy; input [7:0] cbb; input [7:0] crr;
        begin
            y = yy; cb = cbb; cr = crr; valid_i = 1'b1;
            @(posedge clk);
            valid_i = 1'b0;
            @(posedge clk); @(posedge clk);   // 2-cycle pipeline
            #1;
        end
    endtask

    initial begin
        $display("=== tb_ycbcr start ===");
        repeat (4) @(posedge clk); rst = 1'b0; @(posedge clk);

        // ---------------- studio swing, ITU-R BT.601 ----------------
        $display("MARK A: studio swing (full_range = 0)");
        full_range = 1'b0;

        convert(8'd16, 8'd128, 8'd128);
        near("studio black R", r, 0, 1);
        near("studio black G", g, 0, 1);
        near("studio black B", b, 0, 1);

        convert(8'd235, 8'd128, 8'd128);
        near("studio white R", r, 255, 1);
        near("studio white G", g, 255, 1);
        near("studio white B", b, 255, 1);

        // Y below the black level must clamp, not wrap. Underflow here would
        // show as bright speckle in the shadows.
        convert(8'd0, 8'd128, 8'd128);
        near("studio sub-black clamps to 0", r, 0, 0);

        // primaries, from the standard's own reference values
        convert(8'd81, 8'd90, 8'd240);
        near("studio red R", r, 255, 3);
        near("studio red G", g, 0,   3);
        near("studio red B", b, 0,   3);

        convert(8'd145, 8'd54, 8'd34);
        near("studio green R", r, 0,   3);
        near("studio green G", g, 255, 3);
        near("studio green B", b, 0,   3);

        convert(8'd41, 8'd240, 8'd110);
        near("studio blue R", r, 0,   3);
        near("studio blue G", g, 0,   3);
        near("studio blue B", b, 255, 3);

        // ---------------- full range, JFIF ----------------
        $display("MARK B: full range (full_range = 1)");
        full_range = 1'b1;

        convert(8'd0, 8'd128, 8'd128);
        near("full black R", r, 0, 1);
        convert(8'd255, 8'd128, 8'd128);
        near("full white R", r, 255, 1);
        near("full white G", g, 255, 1);
        near("full white B", b, 255, 1);
        // neutral grey must stay neutral: any chroma leak shows as a colour cast
        convert(8'd128, 8'd128, 8'd128);
        near("full mid grey R", r, 128, 1);
        near("full mid grey G", g, 128, 1);
        near("full mid grey B", b, 128, 1);

        // ---------------- the two sets must differ ----------------
        // If the switch did nothing, every test above would still pass on
        // whichever set happened to be wired in.
        full_range = 1'b0; convert(8'd128, 8'd128, 8'd128);
        if (r == 128) begin
            $display("FAIL full_range switch has no effect: studio Y=128 gave 128");
            errors = errors + 1;
        end else $display("  ok  studio Y=128 gives %0d, distinct from full range", r);

        $display("=== TESTS COMPLETE: %0d error(s) ===", errors);
        if (errors == 0) $display("=== ALL TESTS PASS ===");
        $finish;
    end

    initial begin
        #1_000_000; $display("WATCHDOG: stuck, errors so far %0d", errors); $finish;
    end
endmodule

`default_nettype wire
