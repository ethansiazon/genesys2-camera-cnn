`timescale 1ns/1ps
module tb_banked_frame_memory;
 reg wc=0,rc=0,we=0;reg[16:0]wa=0,ra=0;reg[23:0]wd=0;wire[23:0]old,rd;
 always #7 wc=~wc;always #11 rc=~rc;
 banked_frame_memory #(.DEPTH(3073))dut(.wr_clk(wc),.wr_en(we),.wr_addr(wa),
 .wr_data(wd),.wr_dout(old),.rd_clk(rc),.rd_addr(ra),.rd_data(rd));
 integer i;reg[23:0]expected;
 function[23:0]pattern;input integer a;begin pattern=(a*73427)^24'hA57C39;end endfunction
 initial begin
  for(i=0;i<3073;i=i+1)begin
   @(negedge wc);we=1;wa=i;wd=pattern(i);@(posedge wc);#1;
   if(old!==0)$fatal(1,"FAIL write read-first/bank select");
  end
  @(negedge wc);we=0;
  for(i=0;i<3073;i=i+1)begin
   @(negedge rc);ra=i;expected=pattern(i);@(posedge rc);#1;
   if(rd!==expected)$fatal(1,"FAIL read at address %0d got %h want %h",i,rd,expected);
  end
  @(negedge wc);we=1;wa=1024;wd=24'h123456;@(posedge wc);#1;
  if(old!==pattern(1024))$fatal(1,"FAIL overwrite read-first");
  @(negedge wc);we=0;
  @(negedge rc);ra=1024;@(posedge rc);#1;
  if(rd!==24'h123456)$fatal(1,"FAIL overwrite");
  $display("ALL TESTS PASS");$finish;
 end
 initial begin #1000000;$fatal(1,"WATCHDOG");end
endmodule
