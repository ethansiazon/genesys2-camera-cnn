`timescale 1ns/1ps
// Exercises startup registers and the receiver at the expected DVP clock.
module tb_top_reference_readout_20fps;
    tb_top_rgb565 #(.REFERENCE_READOUT(3)) test();
endmodule
