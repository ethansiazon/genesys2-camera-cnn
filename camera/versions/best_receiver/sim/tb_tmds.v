// -----------------------------------------------------------------------------
// tb_tmds -- the DVI encoder, checked four ways.
//
// This module has no working precedent in the project and cannot be debugged on
// the bench: a wrong symbol produces "no signal" on the monitor and nothing
// else. So it is tested against the specification rather than against a picture.
//
//  A) ROUND TRIP. All 256 byte values, encoded then decoded by the inverse
//     algorithm, must come back identical. This is the complete correctness
//     check -- a receiver does exactly this.
//  B) CONTROL SYMBOLS. The four blanking codes must be bit-exact. They are what
//     the sink locks to; wrong here means no sync regardless of the data path.
//  C) TRANSITION COUNT. Data symbols must have at most 5 transitions. Control
//     symbols have 7, deliberately more than any data symbol can have, which is
//     how a receiver finds symbol boundaries. If a data symbol reached 7 the
//     sink could mistake it for control.
//  D) DC BALANCE. Running disparity over a long random stream must stay bounded
//     and end near zero. An encoder that balances wrongly still produces a
//     picture on a scope but drifts an AC-coupled receiver out of lock.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module tb_tmds;
    integer errors = 0;
    task ck; input [255:0] n; input integer got; input integer want; begin
        if (got !== want) begin
            $display("FAIL %0s: got %0d want %0d", n, got, want); errors=errors+1;
        end else $display("  ok  %0s = %0d", n, got);
    end endtask

    reg clk = 1'b0;  always #5 clk = ~clk;
    reg rst = 1'b1;
    reg [7:0] d = 8'h00;
    reg [1:0] c = 2'b00;
    reg       de = 1'b0;
    wire [9:0] q;

    tmds_encoder dut (.clk(clk), .rst(rst), .d(d), .c(c), .de(de), .q(q));

    // ---- the inverse algorithm, as a receiver would implement it ----
    function [7:0] tmds_decode;
        input [9:0] sym;
        reg [7:0] dm;
        reg [7:0] o;
        integer i;
        begin
            dm = sym[9] ? ~sym[7:0] : sym[7:0];
            o[0] = dm[0];
            for (i = 1; i < 8; i = i + 1)
                o[i] = sym[8] ? (dm[i] ^ dm[i-1]) : ~(dm[i] ^ dm[i-1]);
            tmds_decode = o;
        end
    endfunction

    function integer transitions;
        input [9:0] sym;
        integer i, n;
        begin
            n = 0;
            for (i = 1; i < 10; i = i + 1) if (sym[i] !== sym[i-1]) n = n + 1;
            transitions = n;
        end
    endfunction

    function integer ones10;
        input [9:0] sym;
        integer i, n;
        begin
            n = 0;
            for (i = 0; i < 10; i = i + 1) if (sym[i]) n = n + 1;
            ones10 = n;
        end
    endfunction

    integer i, bad_rt, bad_tr, disp, worst_disp;
    reg [7:0] back;
    reg [31:0] lfsr;

    initial begin
        $display("=== tb_tmds start ===");
        repeat (4) @(posedge clk); rst = 1'b0; @(posedge clk);

        // ---------------- A: round trip, every byte ----------------
        $display("MARK A: round trip over all 256 byte values");
        bad_rt = 0; bad_tr = 0;
        de = 1'b1;
        for (i = 0; i < 256; i = i + 1) begin
            d = i[7:0];
            @(posedge clk);
            #1;
            back = tmds_decode(q);
            if (back !== d) begin
                if (bad_rt < 5)
                    $display("FAIL round trip: in %02h -> %010b -> %02h", d, q, back);
                bad_rt = bad_rt + 1;
            end
            if (transitions(q) > 5) begin
                if (bad_tr < 5)
                    $display("FAIL transitions: %02h -> %010b has %0d",
                             d, q, transitions(q));
                bad_tr = bad_tr + 1;
            end
        end
        ck("bytes that failed round trip", bad_rt, 0);
        ck("data symbols over 5 transitions", bad_tr, 0);

        // ---------------- B: the four control symbols ----------------
        $display("MARK B: control symbols");
        de = 1'b0;
        c = 2'b00; @(posedge clk); #1; ck("control c=00", q, 10'b1101010100);
        c = 2'b01; @(posedge clk); #1; ck("control c=01", q, 10'b0010101011);
        c = 2'b10; @(posedge clk); #1; ck("control c=10", q, 10'b0101010100);
        c = 2'b11; @(posedge clk); #1; ck("control c=11", q, 10'b1010101011);
        // 7 transitions is what makes these findable in the bit stream
        c = 2'b00; @(posedge clk); #1;
        ck("control symbol transition count", transitions(q), 7);

        // ---------------- D: DC balance over a long stream ----------------
        $display("MARK D: running disparity over 20000 random bytes");
        de = 1'b1;
        disp = 0; worst_disp = 0;
        lfsr = 32'hACE1_2345;
        for (i = 0; i < 20000; i = i + 1) begin
            lfsr = {lfsr[30:0], lfsr[31] ^ lfsr[21] ^ lfsr[1] ^ lfsr[0]};
            d = lfsr[7:0];
            @(posedge clk);
            #1;
            disp = disp + (2 * ones10(q) - 10);
            if (disp > worst_disp)  worst_disp = disp;
            if (-disp > worst_disp) worst_disp = -disp;
        end
        // The spec bounds the excursion tightly; anything past a few tens of
        // bits means the balance branches are wrong even if the picture decodes.
        if (worst_disp > 20) begin
            $display("FAIL disparity excursion %0d exceeds 20", worst_disp);
            errors = errors + 1;
        end else $display("  ok  worst disparity excursion = %0d", worst_disp);
        if (disp > 20 || disp < -20) begin
            $display("FAIL final disparity %0d not near zero", disp);
            errors = errors + 1;
        end else $display("  ok  final disparity = %0d", disp);

        $display("=== TESTS COMPLETE: %0d error(s) ===", errors);
        if (errors == 0) $display("=== ALL TESTS PASS ===");
        $finish;
    end

    initial begin
        #5_000_000; $display("WATCHDOG: stuck, errors so far %0d", errors); $finish;
    end
endmodule

`default_nettype wire
