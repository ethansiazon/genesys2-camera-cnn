`timescale 1ns/1ps
// Checks register programming and RGB565 capture at the expected DVP clock.
module tb_top_reference_readout_20fps_even;
    tb_top_rgb565 #(.REFERENCE_READOUT(4)) test();
endmodule
