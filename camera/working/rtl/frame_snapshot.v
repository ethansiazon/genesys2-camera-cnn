`timescale 1ns/1ps
`default_nettype none
// Observes framebuffer writes only. Frozen full-frame RGB565 UART snapshot.
module frame_snapshot #(parameter integer DEPTH=76800)(
 input wire src_clk,src_rst,dst_clk,dst_rst,arm,
 input wire pixel_we,input wire[16:0]pixel_addr,input wire[23:0]pixel_rgb,
 input wire[15:0]frame_count,input wire report_busy,
 output reg[255:0]words,output reg go
);
 localparam integer PACKETS=(DEPTH+13)/14;
 localparam [31:0] DEPTH_WORD=DEPTH;
 (* ASYNC_REG="TRUE" *)reg[1:0]arm_s=0,arm_d=0,done_d=0;
 reg active=0,captured=0;reg[15:0]capture_frame=0;
 reg[31:0]write_count=0,address_errors=0,finish_reason=0;
 reg[16:0]next_address=0,rd_index=0;
 wire[15:0]rd_data;
 wire start_capture=arm_s[1]&&!src_rst&&!active&&!captured&&pixel_we&&pixel_addr==0;
 wire memory_we=!src_rst&&arm_s[1]&&(start_capture||active)&&pixel_we&&pixel_addr<DEPTH;
 banked_frame_memory #(.DW(16),.DEPTH(DEPTH),.AW(17)) storage(
  .wr_clk(src_clk),.wr_en(memory_we),.wr_addr(pixel_addr),
  .wr_data({pixel_rgb[23:19],pixel_rgb[15:10],pixel_rgb[7:3]}),.wr_dout(),
  .rd_clk(dst_clk),.rd_addr(rd_index),.rd_data(rd_data));
 always @(posedge src_clk)begin
  arm_s<={arm_s[0],arm};
  if(src_rst||!arm_s[1])begin
   active<=0;captured<=0;write_count<=0;address_errors<=0;next_address<=0;finish_reason<=0;
  end else if(start_capture)begin
   active<=1;capture_frame<=frame_count;write_count<=1;next_address<=1;
  end else if(active)begin
   if(frame_count!=capture_frame)begin active<=0;captured<=1;finish_reason<=2;end
   else if(pixel_we)begin
    write_count<=write_count+1;
    if(pixel_addr!=next_address)address_errors<=address_errors+1;
    next_address<=pixel_addr+1;
    if(pixel_addr==DEPTH-1)begin active<=0;captured<=1;finish_reason<=1;end
   end
  end
 end
 always @(posedge dst_clk)begin
  arm_d<={arm_d[0],arm};done_d<={done_d[0],captured};
 end
 reg[3:0]state=0,slot=0;reg[15:0]packet_index=0;reg[16:0]base=0;reg pad=0;
 always @(posedge dst_clk)begin
  go<=0;
  if(dst_rst||!arm_d[1])begin state<=0;words<=0;slot<=0;packet_index<=0;base<=0;rd_index<=0;end
  else case(state)
   0:if(done_d[1]&&!report_busy)begin
     if(packet_index==PACKETS)begin
      words<={32'h534E4150,32'd16,DEPTH_WORD,finish_reason,{16'd0,capture_frame},address_errors,write_count,(32'hD16A0000|{16'd0,packet_index})};
      state<=4;
     end else begin words<=0;words[31:0]<=32'hD16A0000|{16'd0,packet_index};slot<=0;state<=1;end
    end
   1:begin pad<=base+slot>=DEPTH;rd_index<=base+slot<DEPTH ? base+slot : 0;state<=2;end
   2:state<=3;
   3:begin
     words[32+slot*16+:16]<=pad ? 16'd0 : rd_data;
     if(slot==13)state<=4;else begin slot<=slot+1;state<=1;end
    end
   4:if(!report_busy)begin go<=1;state<=5;end
   5:if(report_busy)state<=6;
   6:if(!report_busy)begin
     if(packet_index==PACKETS)begin packet_index<=0;base<=0;end
     else begin packet_index<=packet_index+1;base<=base+14;end
     state<=0;
    end
   default:state<=0;
  endcase
 end
endmodule
`default_nettype wire
