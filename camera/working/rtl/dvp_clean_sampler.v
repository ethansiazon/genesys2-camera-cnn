`timescale 1ns/1ps
`default_nettype none
// Uses a fabric clock enable, never gates/creates a clock. Accepts a PCLK
// transition only after four stable samples. Data and controls share the same
// sampling pipeline and are captured together at a qualified rising event.
module dvp_clean_sampler #(
 parameter integer STABLE_CYCLES=4,
 parameter integer MAJORITY_FILTER=0 // 0: consecutive samples, 1: majority, 2: confirmed majority
)(
 input wire clk,rst,pclk,href,vsync,input wire[7:0]data,
 output reg tick=0,output reg[7:0]sample_data=0,
 output reg sample_href=0,output reg sample_vsync=0
);
 (* ASYNC_REG="TRUE",SHREG_EXTRACT="NO" *)reg[6:0]ps=0;
 (* ASYNC_REG="TRUE",SHREG_EXTRACT="NO" *)reg[9:0]s0=0,s1=0,s2=0,s3=0;
 reg level=0,previous_majority=0;reg[7:0]count=0;
 // A five-sample majority rejects isolated one- or two-sample excursions
 // without requiring the remaining half-period to contain four consecutive
 // samples. Only synchronized samples enter this filter.
 wire a=ps[2],b=ps[3],c=ps[4],d=ps[5],e=ps[6];
 wire majority=(a & b & (c | d | e)) |
               ((a | b) & ((c & d) | (c & e) | (d & e))) |
               (c & d & e);
 always @(posedge clk)begin
  ps<={ps[5:0],pclk};s0<={vsync,href,data};s1<=s0;s2<=s1;s3<=s2;
  tick<=0;
  if(rst)begin level<=0;previous_majority<=0;count<=0;sample_data<=0;sample_href<=0;sample_vsync<=0;end
  else if(MAJORITY_FILTER)begin
   previous_majority<=majority;
   // At the higher PCLK, require two consecutive majority results.
   // Sample one stage earlier in the byte history to offset the extra wait.
   if(MAJORITY_FILTER == 1 || majority == previous_majority)begin
    level<=majority;
    if(majority && !level)begin
     tick<=1;
     {sample_vsync,sample_href,sample_data} <= MAJORITY_FILTER == 2 ? s3 : s2;
    end
   end
  end
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
