`timescale 1ns/1ps
`default_nettype none
// Uses a fabric clock enable, never gates/creates a clock. Accepts a PCLK
// transition only after four stable samples. Data and controls share the same
// sampling pipeline and are captured together at a qualified rising event.
module dvp_clean_sampler #(parameter integer STABLE_CYCLES=4)(
 input wire clk,rst,pclk,href,vsync,input wire[7:0]data,
 output reg tick=0,output reg[7:0]sample_data=0,
 output reg sample_href=0,output reg sample_vsync=0
);
 (* ASYNC_REG="TRUE",SHREG_EXTRACT="NO" *)reg[2:0]ps=0;
 (* ASYNC_REG="TRUE",SHREG_EXTRACT="NO" *)reg[9:0]s0=0,s1=0,s2=0;
 reg level=0;reg[7:0]count=0;
 always @(posedge clk)begin
  ps<={ps[1:0],pclk};s0<={vsync,href,data};s1<=s0;s2<=s1;
  tick<=0;
  if(rst)begin level<=0;count<=0;sample_data<=0;sample_href<=0;sample_vsync<=0;end
  else if(ps[2]==level)count<=0;
  else if(count==STABLE_CYCLES-1)begin
   level<=ps[2];count<=0;
   if(ps[2])begin
    tick<=1;sample_data<=s2[7:0];sample_href<=s2[8];sample_vsync<=s2[9];
   end
  end else count<=count+1;
 end
endmodule
`default_nettype wire
