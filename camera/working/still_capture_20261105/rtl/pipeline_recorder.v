`timescale 1ns/1ps
`default_nettype none
// Captures exactly what the camera receiver consumes and the framebuffer writes.
// Frozen dual-clock storage only; does not alter the image path.
module pipeline_recorder #(parameter integer DEPTH=2048)(
 input wire src_clk,src_rst,dst_clk,dst_rst,arm,trigger,
 input wire[127:0] sample,
 input wire report_busy,
 output reg[255:0] words,output reg go
);
 (* ASYNC_REG="TRUE" *) reg[1:0] arm_s=0,arm_d=0,done_d=0;
 (* ram_style="block" *) reg[127:0] memory[0:DEPTH-1];
 reg active=0,captured=0;reg[15:0] wr_index=0;
 reg[15:0] rd_index=0,packet_index=0;reg[127:0] rd_data;
 reg[2:0] state=0;
 localparam [31:0] DEPTH_WORD=DEPTH;
 wire start_capture=arm_s[1]&&!src_rst&&!active&&!captured&&trigger;
 wire memory_we=!src_rst && arm_s[1] && (start_capture||active);
 wire[15:0] memory_address=start_capture ? 16'd0 : wr_index;
 // One indexed write port is essential for dual-clock block RAM inference.
 always @(posedge src_clk) begin
  if(memory_we)memory[memory_address]<=sample;
 end
 always @(posedge src_clk) begin
  arm_s<={arm_s[0],arm};
  if(src_rst||!arm_s[1])begin active<=0;captured<=0;wr_index<=0;end
  else if(start_capture)begin wr_index<=1;active<=1;end
  else if(active)begin
   if(wr_index==DEPTH-1)begin active<=0;captured<=1;end
   else wr_index<=wr_index+1'b1;
  end
 end
 always @(posedge dst_clk) begin
  rd_data<=memory[rd_index];
  arm_d<={arm_d[0],arm};done_d<={done_d[0],captured};
 end
 always @(posedge dst_clk) begin
  go<=0;
  if(dst_rst||!arm_d[1])begin state<=0;words<=0;rd_index<=0;packet_index<=0;end
  else case(state)
   0:if(done_d[1]&&!report_busy)begin rd_index<=packet_index;state<=1;end
   1:state<=2;
   2:begin
      words<={32'h50495045,32'd0,DEPTH_WORD,rd_data,(32'hD1680000|{16'd0,packet_index})};
      state<=3;
     end
   3:if(!report_busy)begin go<=1;state<=4;end
   4:if(report_busy)state<=5;
   5:if(!report_busy)begin packet_index<=packet_index==DEPTH-1 ? 0 : packet_index+1'b1;state<=0;end
   default:state<=0;
  endcase
 end
endmodule
`default_nettype wire
