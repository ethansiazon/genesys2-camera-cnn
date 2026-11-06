`timescale 1ns/1ps
// Exercises the fast startup profile at the modeled 14.3 MHz DVP clock.
module tb_top_reference_readout_fast;
    tb_top_rgb565 #(.REFERENCE_READOUT(2)) test();
endmodule
