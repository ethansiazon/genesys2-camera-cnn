`timescale 1ns/1ps
module tb_raw_word_snapshot;
 reg src=0,dst=0,rst=1,arm=0,we=0,busy=0;reg[16:0]addr=0;reg[23:0]rgb=0;
 always #35 src=~src;always #2.5 dst=~dst;
 wire[255:0]words;wire go;
 frame_snapshot #(.DEPTH(30),.RAW_WORDS(1))dut(.src_clk(src),.src_rst(rst),.dst_clk(dst),
 .dst_rst(rst),.arm(arm),.pixel_we(we),.pixel_addr(addr),.pixel_rgb(rgb),
 .frame_count(16'd4),.report_busy(busy),.words(words),.go(go));
 integer i,j,n=0,idx,expected,pixel;reg[15:0]v;
 function[15:0] colour;input integer k;reg[23:0]r;begin r=k*1234567;
 colour=r[15:0];end endfunction
 initial begin
  repeat(10)@(negedge src);rst=0;arm=1;repeat(10)@(negedge src);
  for(i=0;i<30;i=i+1)begin we=1;addr=i;rgb=i*1234567;@(negedge src);end
  we=0;
 end
 always @(posedge dst)begin
  if(go)begin
   if(busy)$fatal(1,"FAIL busy handshake");
   idx=words[15:0];if(words[31:16]!=16'hD16C||idx!=n%4)$fatal(1,"FAIL packet/replay order");
   if(idx==3)begin
    if(words[63:32]!=30||words[95:64]!=0||words[127:96]!=4||words[159:128]!=1||
      words[191:160]!=30||words[223:192]!=16||words[255:224]!=32'h59555630)$fatal(1,"FAIL metadata");
   end else for(j=0;j<14;j=j+1)begin
    pixel=idx*14+j;v=words[32+j*16+:16];
    if(pixel<30)begin if(v!==colour(pixel))$fatal(1,"FAIL pixel/prefix alignment");end
    else if(v!==0)$fatal(1,"FAIL padding");
   end
   n=n+1;busy<=1;
   if(n==8)begin $display("ALL TESTS PASS");$finish;end
  end else if(busy)busy<=0;
 end
 initial begin #1000000;$fatal(1,"WATCHDOG");end
endmodule
