// Standalone test of coeff_bram_stage + copy_fsm against the behavioral
// AXI RAM model (sim/axi_ram.sv, module g2_axi_ram) -- no MIG, no real
// smartconnect; those arrive in Task 4. Asserts DDR content matches
// coefficients.hex word-for-word, not just that `done` went high (Review
// Focus item 2: a missing/misordered word must not pass silently).
`timescale 1ns/1ps
module tb_bram_to_ddr;

    localparam WORDS = 41600;
    localparam ADDR_W = 16;

    reg clk = 0;
    reg rst_n = 0;
    reg start = 0;
    wire done;

    always #5 clk = ~clk; // 10ns period

    wire [ADDR_W-1:0] bram_addr;
    wire [127:0]      bram_data;

    coeff_bram_stage #(
        .WORDS(WORDS), .ADDR_W(ADDR_W), .HEXFILE("rtl/coefficients.hex")
    ) dut_bram (
        .clk(clk), .addr(bram_addr), .data(bram_data)
    );

    wire        axi_awvalid, axi_awready;
    wire [63:0] axi_awaddr;
    wire [0:0]  axi_awid;
    wire [7:0]  axi_awlen;
    wire [2:0]  axi_awsize;
    wire [1:0]  axi_awburst;
    wire        axi_wvalid, axi_wready;
    wire [127:0] axi_wdata;
    wire [15:0]  axi_wstrb;
    wire         axi_wlast;
    wire         axi_bvalid, axi_bready;
    wire [1:0]   axi_bresp;
    wire [0:0]   axi_bid;

    // copy_fsm's BASE_ADDR is overridden to 0 here -- this testbench's
    // behavioral g2_axi_ram is sized WORDS deep (addressed 0..WORDS-1), not
    // the real 1GB DDR window Task 4 wires this into at 0x80300000.
    copy_fsm #(
        .WORDS(WORDS), .ADDR_W(ADDR_W), .BASE_ADDR(64'h0)
    ) dut_fsm (
        .clk(clk), .rst_n(rst_n), .start(start), .done(done),
        .bram_addr(bram_addr), .bram_data(bram_data),

        .m_axi_AWVALID(axi_awvalid), .m_axi_AWREADY(axi_awready),
        .m_axi_AWADDR(axi_awaddr), .m_axi_AWID(axi_awid),
        .m_axi_AWLEN(axi_awlen), .m_axi_AWSIZE(axi_awsize),
        .m_axi_AWBURST(axi_awburst),
        .m_axi_AWLOCK(), .m_axi_AWCACHE(), .m_axi_AWPROT(),
        .m_axi_AWQOS(), .m_axi_AWREGION(), .m_axi_AWUSER(),

        .m_axi_WVALID(axi_wvalid), .m_axi_WREADY(axi_wready),
        .m_axi_WDATA(axi_wdata), .m_axi_WSTRB(axi_wstrb),
        .m_axi_WLAST(axi_wlast), .m_axi_WID(), .m_axi_WUSER(),

        .m_axi_BVALID(axi_bvalid), .m_axi_BREADY(axi_bready),
        .m_axi_BRESP(axi_bresp), .m_axi_BID(axi_bid), .m_axi_BUSER(1'b0)
    );

    g2_axi_ram #(
        .WORDS(WORDS), .FILE(""), .READ_ONLY(0), .INPUT_WORDS(0), .DATA_BITS(128)
    ) dut_ram (
        .clk(clk), .resetn(rst_n),
        .arvalid(1'b0), .arready(), .araddr(64'h0), .arlen(8'h0),
        .arsize(3'h0), .arburst(2'b01), .arid(1'b0),
        .rvalid(), .rready(1'b1), .rdata(), .rlast(), .rid(), .rresp(),
        .awvalid(axi_awvalid), .awready(axi_awready), .awaddr(axi_awaddr),
        .awlen(axi_awlen), .awsize(axi_awsize), .awburst(axi_awburst),
        .awid(axi_awid),
        .wvalid(axi_wvalid), .wready(axi_wready), .wdata(axi_wdata),
        .wstrb(axi_wstrb), .wlast(axi_wlast),
        .bvalid(axi_bvalid), .bready(axi_bready), .bid(axi_bid), .bresp(axi_bresp)
    );

    integer errors;
    integer i;
    reg [127:0] ref_mem [0:WORDS-1];

    initial begin
        errors = 0;
        $readmemh("rtl/coefficients.hex", ref_mem);

        rst_n = 0;
        start = 0;
        repeat (4) @(posedge clk);
        rst_n = 1;
        repeat (2) @(posedge clk);
        start = 1;

        // 41,600 words through a deliberately-stalling behavioral slave
        // (g2_axi_ram throttles AWREADY/WREADY on cycle%11/cycle%5) realistically
        // needs several hundred thousand cycles -- scaled up from this skill's
        // illustrative #2_000_000 example, which was sized for a much smaller
        // design, not this word count against a throttling slave. Plain
        // Verilog-2001 (this file is .v, not .sv) has no fork/join_any, so
        // the watchdog is a bounded wait loop instead.
        begin : wait_for_done
            integer cycles;
            cycles = 0;
            while (!done && cycles < 2_000_000) begin
                @(posedge clk);
                cycles = cycles + 1;
            end
        end

        if (!done) begin
            $display("WATCHDOG: stuck waiting for done, errors so far %0d", errors);
            $finish;
        end

        for (i = 0; i < WORDS; i = i + 1) begin
            if (dut_ram.mem[i] !== ref_mem[i]) begin
                errors = errors + 1;
                $display("MISMATCH at word %0d: ram=%h expected=%h", i, dut_ram.mem[i], ref_mem[i]);
            end
        end

        $display("errors == %0d", errors);
        $finish;
    end

endmodule
