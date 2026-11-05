`timescale 1ns/1ps
module tb_sync_health_probe;
 reg clk=0;always #2.5 clk=~clk;
 reg rst=1,v=0,h=0;
 wire[31:0] vr,hr,vc,hc,vhigh,vmaxhi,vmaxlo,hhigh,hmaxhi,hmaxlo;
 sync_health_probe #(.CLK_HZ(20000)) dut(.clk(clk),.rst(rst),.v_i(v),.h_i(h),
 .vraw(vr),.hraw(hr),.vclean(vc),.hclean(hc),.vhigh(vhigh),.vmaxhi(vmaxhi),.vmaxlo(vmaxlo),
 .hhigh(hhigh),.hmaxhi(hmaxhi),.hmaxlo(hmaxlo));
 task cycles;input integer n;begin repeat(n) @(negedge clk);end endtask
 integer k;
 initial begin
  cycles(5);rst=0;cycles(100);
  for(k=0;k<5;k=k+1) begin v=1;cycles(1);v=0;cycles(40);end
  v=1;h=1;cycles(200);v=0;h=0;cycles(500);
  wait(dut.timer==19999);cycles(5);
  if(vr!==6 || vc!==1 || hr!==1 || hc!==1 || vhigh!==205 || hhigh!==200)
   $fatal(1,"FAIL stats raw=%d clean=%d href=%d/%d duty=%d/%d",vr,vc,hr,hc,vhigh,hhigh);
  if(vmaxhi<199 || vmaxhi>201) $fatal(1,"FAIL pulse length %d",vmaxhi);
  // A complete next window with no pulses must not retain previous edge counts.
  cycles(20000);
  if(vr!==0 || vc!==0 || vhigh!==0 || hr!==0) $fatal(1,"FAIL stale window");
  $display("ALL TESTS PASS: sync pulse counters, spike rejection and interval reset");$finish;
 end
 initial begin #300000;$fatal(1,"WATCHDOG");end
endmodule
