`timescale 1ns/1ps
module tb_pipeline_recorder;
 reg sc=0;always #35 sc=~sc;
 reg dc=0;always #2.5 dc=~dc;
 reg rst=1,arm=0,trig=0;reg[127:0] sample=0;
 reg busy=0;wire[255:0] words;wire go;
 pipeline_recorder #(.DEPTH(16)) dut(.src_clk(sc),.src_rst(rst),.dst_clk(dc),.dst_rst(rst),
 .arm(arm),.trigger(trig),.sample(sample),.report_busy(busy),.words(words),.go(go));
 reg[127:0] expected[0:15];integer c=0,packets=0,wait_count=0,index,want=0;
 always @(negedge sc)sample<=sample+128'h123456789abcdef00123456789abcdef;
 always @(posedge sc)begin
  if(dut.start_capture || dut.active)begin expected[c]=sample;c=c+1;end
 end
 always @(posedge dc)begin
  if(go)begin
   index=words[15:0];
   if(words[31:16]!==16'hD168 || index!=want)$fatal(1,"FAIL packet index");
   if(words[159:32]!==expected[index])$fatal(1,"FAIL sample %d",index);
   if(words[191:160]!==16)$fatal(1,"FAIL depth metadata");
   want=index==15 ? 0:index+1;packets=packets+1;busy<=1;wait_count=5;
  end else if(busy)begin if(wait_count==0)busy<=0;else wait_count=wait_count-1;end
 end
 initial begin
  repeat(4)@(negedge sc);rst=0;arm=1;
  repeat(5)@(negedge sc);trig=1;
  @(negedge sc);trig=0;
  wait(packets==19);@(negedge sc);arm=0;
  repeat(5)@(negedge sc);
  if(dut.captured)$fatal(1,"FAIL disarm");
  $display("ALL TESTS PASS: source trigger, dual-clock frozen memory, records and replay");$finish;
 end
 initial begin #100000;$fatal(1,"WATCHDOG");end
endmodule
