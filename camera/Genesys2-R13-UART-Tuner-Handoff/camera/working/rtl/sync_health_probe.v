`timescale 1ns/1ps
`default_nettype none
// Observes sync pins only. Does not alter camera capture or drive any camera pin.
module sync_health_probe #(parameter integer CLK_HZ=200000000)(
 input wire clk,rst,v_i,h_i,
 output wire [31:0] vraw,hraw,vclean,hclean,
 output wire [31:0] vhigh,vmaxhi,vmaxlo,hhigh,hmaxhi,hmaxlo
);
 (* ASYNC_REG="TRUE" *) reg [1:0] s0=0,s1=0,s2=0;
 reg [1:0] prev=0,filtered=0,filter_prev=0;
 reg [6:0] vote[0:1];
 reg [31:0] edges[0:1],clean_edges[0:1],highs[0:1];
 reg [31:0] runlen[0:1],maxhi[0:1],maxlo[0:1];
 reg [31:0] out_edges[0:1],out_clean[0:1],out_highs[0:1];
 reg [31:0] out_maxhi[0:1],out_maxlo[0:1];
 reg [31:0] timer=0;
 integer i;
 assign vraw=out_edges[0]; assign hraw=out_edges[1];
 assign vclean=out_clean[0]; assign hclean=out_clean[1];
 assign vhigh=out_highs[0]; assign hhigh=out_highs[1];
 assign vmaxhi=out_maxhi[0]; assign hmaxhi=out_maxhi[1];
 assign vmaxlo=out_maxlo[0]; assign hmaxlo=out_maxlo[1];
 always @(posedge clk) begin
  s0<={h_i,v_i}; s1<=s0; s2<=s1;
  if(rst) begin
   timer<=0;prev<=0;filtered<=0;filter_prev<=0;
   for(i=0;i<2;i=i+1) begin
    vote[i]<=0;edges[i]<=0;clean_edges[i]<=0;highs[i]<=0;
    runlen[i]<=0;maxhi[i]<=0;maxlo[i]<=0;
    out_edges[i]<=0;out_clean[i]<=0;out_highs[i]<=0;
    out_maxhi[i]<=0;out_maxlo[i]<=0;
   end
  end else begin
   prev<=s2;filter_prev<=filtered;
   timer<=timer==CLK_HZ-1 ? 0 : timer+1'b1;
   for(i=0;i<2;i=i+1) begin
    if(s2[i]) begin if(vote[i]<64) vote[i]<=vote[i]+1'b1; end
    else if(vote[i]>0) vote[i]<=vote[i]-1'b1;
    if(vote[i]>=48) filtered[i]<=1;
    else if(vote[i]<=16) filtered[i]<=0;
    if(timer==CLK_HZ-1) begin
     out_edges[i]<=edges[i]+(s2[i]&&!prev[i]);
     out_clean[i]<=clean_edges[i]+(filtered[i]&&!filter_prev[i]);
     out_highs[i]<=highs[i]+s2[i];
     out_maxhi[i]<=s2[i] && runlen[i]>maxhi[i] ? runlen[i] : maxhi[i];
     out_maxlo[i]<=!s2[i] && runlen[i]>maxlo[i] ? runlen[i] : maxlo[i];
     edges[i]<=0;clean_edges[i]<=0;highs[i]<=0;
     runlen[i]<=0;maxhi[i]<=0;maxlo[i]<=0;
    end else begin
     if(s2[i]&&!prev[i]) edges[i]<=edges[i]+1'b1;
     if(filtered[i]&&!filter_prev[i]) clean_edges[i]<=clean_edges[i]+1'b1;
     if(s2[i]) highs[i]<=highs[i]+1'b1;
     if(s2[i]==prev[i]) runlen[i]<=runlen[i]+1'b1;
     else begin
      if(prev[i] && runlen[i]>maxhi[i]) maxhi[i]<=runlen[i];
      if(!prev[i] && runlen[i]>maxlo[i]) maxlo[i]<=runlen[i];
      runlen[i]<=1;
     end
    end
   end
  end
 end
endmodule
`default_nettype wire
