// Feature staging BRAM -- same $readmemh pattern as coeff_bram_stage.v, but
// 256-bit words (cnn_engine's m_axi_feature_ddr width) carrying a real,
// letterbox-resized/Q14-quantized photo instead of coefficients. Built for
// the C3 real-image investigation (docs/PHASE2_LOG.md, 2026-10-29): is the
// 374-cycle early ap_done a benign artifact of empty/default feature memory,
// or a real integration bug? WORDS defaults to 256 (one canvas row), NOT the
// full 49,152-word INPUT_WORDS frame -- matching coeff_bram_stage_0's own
// existing sim-bypass precedent (41,600 -> 256 words) for the same reason:
// a full frame's worth of individual AXI transactions through the realistic
// DDR3 behavioral model is impractically slow in wall-clock sim time and
// isn't needed to answer the narrower question this test asks. See
// scripts/pack_image_to_hex.py for how the .hex is produced.
`timescale 1ns/1ps
module feature_bram_stage #(
    parameter WORDS   = 256,
    parameter ADDR_W  = 16,     // >= $clog2(WORDS)
    parameter HEXFILE = "rtl/feature_drone.hex"
)(
    input  wire                  clk,
    input  wire [ADDR_W-1:0]     addr,
    output reg  [255:0]          data
);
    reg [255:0] mem [0:WORDS-1];

    initial begin
        $readmemh(HEXFILE, mem);
    end

    always @(posedge clk) begin
        data <= mem[addr];
    end
endmodule
