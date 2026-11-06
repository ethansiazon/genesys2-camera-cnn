`timescale 1ns/1ps
// Reuses the RGB565 integration fixture with the alternative startup profile.
// The behavioural sensor cannot predict actual imager colour or frame rate.
module tb_top_reference_readout;
    tb_top_rgb565 #(.REFERENCE_READOUT(1)) test();
endmodule
