// -----------------------------------------------------------------------------
// frame_buffer -- 320x240 x 24 bpp RGB888, true dual-clock block RAM.
//
// 320*240 = 76,800 words of 24 bits = 1,843,200 bits. The XC7K325T has
// 16,020 Kb of block RAM, so this is ~11% of it. On the Basys 3 the equivalent
// buffer at 12 bpp was 51% and double-buffering was arithmetically impossible;
// here two buffers would still be under a quarter of the device.
//
// It is nevertheless a SINGLE buffer, and that is a deliberate choice rather
// than a carried-over limitation: this is a bring-up for a board that cannot be
// iterated on quickly, and the single-buffer topology is the one already proven
// end to end. Tearing is the same mild artefact it was before. Going
// double-buffered later is an extra address bit and a swap register, not a
// redesign -- see README.
//
// Writer and reader have INDEPENDENT clocks and there is deliberately no
// handshake. The BRAM primitive handles the crossing; the only consequence of
// a collision is one stale pixel.
//
// Read-first on the write port: wr_dout gives the value stored at wr_addr
// BEFORE any write this cycle, which is what the temporal blend consumes.
// cam_capture's four-phase schedule exists precisely because this port has one
// address shared between that read and the write.
//
// Contents power up to zero (black), so the display is black until first write.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module frame_buffer #(
    parameter H     = 320,
    parameter V     = 240,
    parameter DW    = 24,
    parameter DEPTH = H * V,
    parameter AW    = 17
)(
    input  wire          wr_clk,
    input  wire          wr_en,
    input  wire [AW-1:0] wr_addr,
    input  wire [DW-1:0] wr_data,
    output wire [DW-1:0] wr_dout,
    input  wire          rd_clk,
    input  wire [AW-1:0] rd_addr,
    output wire [DW-1:0] rd_data
);
    banked_frame_memory #(.DW(DW),.DEPTH(DEPTH),.AW(AW)) storage(
      .wr_clk(wr_clk),.wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data),
      .wr_dout(wr_dout),.rd_clk(rd_clk),.rd_addr(rd_addr),.rd_data(rd_data));
    // Read-only simulation aliases for existing whole-image integration checks.
`ifndef SYNTHESIS
    wire[DW-1:0]mem[0:DEPTH-1];
    genvar bank_index,word_index;
    generate for(bank_index=0;bank_index<(DEPTH+1023)/1024;bank_index=bank_index+1)begin:dbg_bank
      for(word_index=0;word_index<1024;word_index=word_index+1)begin:dbg_word
        if(bank_index*1024+word_index<DEPTH)
          assign mem[bank_index*1024+word_index]=storage.g_bank[bank_index].memory[word_index];
      end
    end endgenerate
`endif
endmodule

`default_nettype wire
