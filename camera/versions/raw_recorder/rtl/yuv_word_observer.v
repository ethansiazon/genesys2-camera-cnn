`timescale 1ns/1ps
`default_nettype none
// Observes already-qualified bytes at the receiver's actual consume edge.
// Packs Y0/Cb and Y1/Cr without any RGB conversion or discarded low bits.
module yuv_word_observer #(parameter integer H=320,V=240)(
 input wire clk,rst,input wire[48:0]state,
 output reg wr_en=0,output reg[16:0]wr_addr=0,output reg[15:0]wr_data=0
);
 wire valid=state[8];wire[1:0]phase=state[12:11];
 wire[9:0]x=state[22:13],y=state[32:23];reg[7:0]previous_y=0;
 always @(posedge clk)begin
  wr_en<=0;
  if(rst)begin previous_y<=0;wr_addr<=0;wr_data<=0;end
  else if(valid)begin
   if(!phase[0])previous_y<=state[7:0];
   else if(x<H&&y<V)begin
    wr_data<={previous_y,state[7:0]};
    wr_addr<=y*H+x+(phase==3 ? 1 : 0);wr_en<=1;
   end
  end
 end
endmodule
`default_nettype wire
