// Coefficient staging BRAM -- synthesis-time initial values via $readmemh,
// the same pattern cnn_engine's own PROGRAM_*_ROM_AUTO_1R.v ROMs use (see
// docs/superpowers/plans/2026-10-28-phase2-ddr-axi-timing.md, Global
// Constraints). 41,600 x 128-bit words, matching COEFFICIENT_WORDS from
// cv_model/fpga/cnn_hls/program.h. coefficients.hex is copied alongside
// this file (not read from cnn_rtl_sim_work/) so $readmemh's relative path
// does not depend on the simulator's invocation directory.
`timescale 1ns/1ps
module coeff_bram_stage #(
    parameter WORDS   = 41600,
    parameter ADDR_W  = 16,     // >= $clog2(WORDS)
    parameter HEXFILE = "rtl/coefficients.hex"
)(
    input  wire                  clk,
    input  wire [ADDR_W-1:0]     addr,
    output reg  [127:0]          data
);
    reg [127:0] mem [0:WORDS-1];

    initial begin
        $readmemh(HEXFILE, mem);
    end

    always @(posedge clk) begin
        data <= mem[addr];
    end
endmodule
