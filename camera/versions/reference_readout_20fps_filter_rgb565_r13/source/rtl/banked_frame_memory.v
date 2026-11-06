`timescale 1ns/1ps
`default_nettype none
// One-cycle dual-clock memory, split into <=1024-word banks so no 7-series
// RAMB36 cascade primitive is required. Registered bank selector matches data.
module banked_frame_memory #(parameter integer DW=24,DEPTH=76800,AW=17)(
 input wire wr_clk,wr_en,input wire[AW-1:0]wr_addr,input wire[DW-1:0]wr_data,
 output wire[DW-1:0]wr_dout,
 input wire rd_clk,input wire[AW-1:0]rd_addr,output wire[DW-1:0]rd_data
);
 localparam integer BANK_WORDS=1024,BANKS=(DEPTH+BANK_WORDS-1)/BANK_WORDS;
 wire[DW-1:0]rbank[0:BANKS-1],wbank[0:BANKS-1];
 reg[AW-1:0]rsel=0,wsel=0;
 always @(posedge rd_clk)rsel<=rd_addr>>10;
 always @(posedge wr_clk)wsel<=wr_addr>>10;
 assign rd_data=rbank[rsel];assign wr_dout=wbank[wsel];
 genvar b;
 generate for(b=0;b<BANKS;b=b+1)begin:g_bank
  (* ram_style="block" *)reg[DW-1:0]memory[0:BANK_WORDS-1];
  reg[DW-1:0]rq=0,wq=0;integer k;
  initial for(k=0;k<BANK_WORDS;k=k+1)memory[k]=0;
  always @(posedge wr_clk)begin
   wq<=memory[wr_addr[9:0]];
   if(wr_en&&(wr_addr>>10)==b&&wr_addr<DEPTH)memory[wr_addr[9:0]]<=wr_data;
  end
  always @(posedge rd_clk)rq<=memory[rd_addr[9:0]];
  assign rbank[b]=rq;assign wbank[b]=wq;
 end endgenerate
endmodule
`default_nettype wire
