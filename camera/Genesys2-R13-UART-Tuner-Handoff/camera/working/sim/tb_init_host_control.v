`timescale 1ns/1ps
module tb_init_host_control;
 reg clk=0;always #5 clk=~clk;
 reg rst=1,refresh=0,hv=1,hrw=1;reg[15:0]ha=16'h5381;reg[7:0]hw=0;
 wire hready,hdone,hn;wire[7:0]hr;
 wire start,rw;wire[15:0]addr;wire[7:0]wd;reg[7:0]rd=0;
 reg busy=0,done=0,nack=0;integer delay_count=0;
 wire initdone;wire[15:0]id;wire[383:0]rb;wire[47:0]rn;
 integer total=0,host_ops=0;reg[7:0]stored=8'h20;reg inject_nack=0;
 ov5640_init #(.CLK_HZ(1000)) dut(
  .clk(clk),.rst(rst),.debug_refresh(refresh),.testbar(1'b0),.vyuy(1'b0),
  .host_valid(hv),.host_rw(hrw),.host_addr(ha),.host_wdata(hw),
  .host_ready(hready),.host_done(hdone),.host_rdata(hr),.host_nack(hn),
  .sccb_start(start),.sccb_rw(rw),.sccb_addr(addr),.sccb_wdata(wd),
  .sccb_rdata(rd),.sccb_busy(busy),.sccb_done(done),.sccb_nack(nack),
  .cam_pwdn(),.cam_reset_n(),.chip_id(id),.id_valid(),.init_done(initdone),
  .nack_seen(),.table_index(),.debug_readback(rb),.debug_read_nack(rn));
 always @(posedge clk)begin
  done<=0;
  if(rst)begin busy<=0;delay_count=0;total=0;host_ops=0;end
  else if(start)begin
   if(busy)$fatal(1,"FAIL overlapping SCCB owners");
   busy<=1;delay_count=3;total=total+1;
   rd<=addr==16'h300a ? 8'h56 : addr==16'h300b ? 8'h40 : addr==16'h5381 ? stored : 0;
   nack<=inject_nack;
   if(addr==16'h5381 && dut.st==13)begin
    host_ops=host_ops+1;
    if(!initdone)$fatal(1,"FAIL host touched bus before init");
    if(!rw)stored=wd;
   end
  end else if(busy)begin
   if(delay_count==0)begin busy<=0;done<=1;end else delay_count=delay_count-1;
  end
 end
 task cyc;input integer n;begin repeat(n)@(negedge clk);end endtask
 task request;input is_read;input[7:0]v;
  begin hrw=is_read;hw=v;hv=1;wait(hready);@(posedge clk);@(negedge clk);hv=0;wait(hdone);cyc(1);end
 endtask
 integer before_refresh;
 initial begin
  cyc(5);rst=0;
  // Held request during startup must be accepted exactly once, only after init.
  wait(hready);@(posedge clk);@(negedge clk);hv=0;wait(hdone);cyc(1);
  if(id!=16'h5640 || host_ops!=1 || hr!=8'h20 || hn)$fatal(1,"FAIL queued startup read");
  request(0,8'h5b);request(1,0);
  if(hr!=8'h5b || host_ops!=3)$fatal(1,"FAIL host write/read roundtrip");
  // Refresh and host valid together: all 48 diagnostic reads have priority.
  before_refresh=total;refresh=1;hv=1;hrw=1;
  cyc(1);refresh=0;
  wait(hready);@(posedge clk);@(negedge clk);hv=0;wait(hdone);cyc(1);
  if(total-before_refresh!=49 || host_ops!=4 || !initdone)
   $fatal(1,"FAIL refresh/host arbitration total=%0d",total-before_refresh);
  inject_nack=1;request(1,0);
  if(!hn || !initdone)$fatal(1,"FAIL NACK response/stream preservation");
  inject_nack=0;request(1,0);
  if(hn || hr!=8'h5b)$fatal(1,"FAIL NACK recovery");
  $display("ALL TESTS PASS: startup/refresh priority, exclusive bus, roundtrip and NACK recovery");$finish;
 end
 initial begin #2000000;$fatal(1,"WATCHDOG");end
endmodule
