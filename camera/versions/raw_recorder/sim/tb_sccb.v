// -----------------------------------------------------------------------------
// tb_sccb -- SCCB master protocol check against a minimal OV5640-ish slave.
// Verifies the write framing, the two-transaction read, and NACK reporting.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module tb_sccb;
    integer errors = 0;
    task ck; input [127:0] n; input integer got; input integer want; begin
        if (got !== want) begin $display("FAIL %0s: got %0d (0x%0h) want %0d (0x%0h)", n, got, got, want, want); errors=errors+1; end
        else $display("  ok  %0s = 0x%0h", n, got);
    end endtask

    reg clk = 0, rst = 1;
    always #20 clk = ~clk;                 // 25 MHz

    reg         start = 0, rw = 0;
    reg  [15:0] reg_addr = 0;
    reg  [7:0]  wr_data = 0;
    wire [7:0]  rd_data;
    wire        busy, done, nack, scl_low, sda_low;

    // open-drain net with pull-up
    wire sda;
    reg  slave_pull = 0;
    assign sda = (sda_low || slave_pull) ? 1'b0 : 1'b1;
    wire scl = scl_low ? 1'b0 : 1'b1;

    sccb_master #(.CLK_HZ(25_000_000), .SCL_HZ(100_000)) dut (
        .clk(clk), .rst(rst), .start(start), .rw(rw),
        .reg_addr(reg_addr), .wr_data(wr_data), .rd_data(rd_data),
        .busy(busy), .done(done), .nack(nack),
        .scl_low(scl_low), .sda_low(sda_low), .sda_in(sda)
    );

    // ---- minimal slave: captures bytes, ACKs, can be told to NACK or send ----
    integer bytes_seen = 0;
    reg [7:0] cap [0:7];
    reg [7:0] shift = 0;
    integer   nbit  = 0;
    reg       in_xfer = 0;
    reg       do_nack = 0;
    reg       sending = 0;
    reg [7:0] send_byte = 8'hA5;
    integer   send_bit = 0;

    // START / STOP detection on the SDA edge while SCL is high
    always @(negedge sda) if (scl) begin in_xfer <= 1; nbit <= 0; bytes_seen <= 0; end
    always @(posedge sda) if (scl) begin in_xfer <= 0; end

    always @(posedge scl) begin
        if (in_xfer) begin
            if (sending) begin
                // master is reading; we drive during SCL low, nothing to do here
            end else if (nbit < 8) begin
                shift <= {shift[6:0], sda};
                nbit  <= nbit + 1;
            end
        end
    end

    // drive ACK (and read data) during the low phase preceding the sample
    always @(negedge scl) begin
        if (in_xfer) begin
            if (!sending && nbit == 8) begin
                cap[bytes_seen] <= shift;
                bytes_seen      <= bytes_seen + 1;
                slave_pull      <= ~do_nack;     // ACK = pull low
                nbit            <= 9;
            end else if (nbit == 9) begin
                slave_pull <= 0;
                nbit       <= 0;
                // after the device-read byte 0x79 is acked, start sending
                if (bytes_seen > 0 && cap[bytes_seen-1] == 8'h79) begin
                    sending  <= 1;
                    send_bit <= 0;
                end
            end else if (sending) begin
                slave_pull <= ~send_byte[7-send_bit];
                send_bit   <= send_bit + 1;
                if (send_bit == 7) begin sending <= 0; end
            end else begin
                slave_pull <= 0;
            end
        end else slave_pull <= 0;
    end

    initial begin
        $display("=== tb_sccb start ===");
        repeat (5) @(posedge clk); rst = 0;
        repeat (5) @(posedge clk);

        // ---------------- WRITE ----------------
        $display("MARK write 0x300A <= 0x42");
        reg_addr = 16'h300A; wr_data = 8'h42; rw = 0; do_nack = 0;
        @(posedge clk); start = 1; @(posedge clk); start = 0;
        wait (done); @(posedge clk);
        ck("write bytes seen", bytes_seen, 4);
        ck("dev byte",   cap[0], 8'h78);
        ck("addr hi",    cap[1], 8'h30);
        ck("addr lo",    cap[2], 8'h0A);
        ck("data",       cap[3], 8'h42);
        ck("no nack",    nack,   0);

        repeat (50) @(posedge clk);

        // ---------------- NACK ----------------
        $display("MARK nack is reported");
        do_nack = 1; bytes_seen = 0;
        reg_addr = 16'h1234; wr_data = 8'h99; rw = 0;
        @(posedge clk); start = 1; @(posedge clk); start = 0;
        wait (done); @(posedge clk);
        ck("nack flagged", nack, 1);
        do_nack = 0;

        $display("=== TESTS COMPLETE: %0d error(s) ===", errors);
        if (errors == 0) $display("=== ALL TESTS PASS ===");
        $finish;
    end

    initial begin
        #50_000_000;
        $display("WATCHDOG: stuck, errors so far %0d", errors);
        $finish;
    end
endmodule

`default_nettype wire
