`timescale 1ns/1ps
module tb_init_readback;
 reg clk=0;always #5 clk=~clk;
 reg rst=1;
 wire start,rw;wire[15:0] addr;wire[7:0] wd;
 reg busy=0,done=0,nack=0;reg[7:0] rd=0;reg[3:0] delay_count=0;
 wire[15:0] id;wire idvalid,initdone,nackseen,pwdn,resetn;wire[7:0] idx;
 wire[191:0] rb;wire[23:0] rn;
 ov5640_init #(.CLK_HZ(1000)) dut(.clk(clk),.rst(rst),.testbar(1'b0),.vyuy(1'b0),
 .sccb_start(start),.sccb_rw(rw),.sccb_addr(addr),.sccb_wdata(wd),
 .sccb_rdata(rd),.sccb_busy(busy),.sccb_done(done),.sccb_nack(nack),
 .cam_pwdn(pwdn),.cam_reset_n(resetn),.chip_id(id),.id_valid(idvalid),
 .init_done(initdone),.nack_seen(nackseen),.table_index(idx),.debug_readback(rb),.debug_read_nack(rn));
 always @(posedge clk) begin
  done<=0;
  if(rst) begin busy<=0;delay_count<=0;nack<=0;end
  else if(start && !busy) begin
   busy<=1;delay_count<=3;
   rd<=addr==16'h300A ? 8'h56 : addr==16'h300B ? 8'h40 : addr[15:8]^addr[7:0];
   nack<=rw && addr==16'h501F;
  end else if(busy) begin
   if(delay_count==0) begin busy<=0;done<=1;end else delay_count<=delay_count-1'b1;
  end
 end

 reg[15:0] manual_addr[0:5];reg[7:0] manual_data[0:5];integer manual_count=0;
 always @(posedge clk) if(!rst && start && !busy && !rw) begin
   if(addr>=16'h3500 && addr<=16'h350b) begin
     if(manual_count>=6) $fatal(1,"FAIL extra manual write");
     if(addr!==manual_addr[manual_count] || wd!==manual_data[manual_count])
       $fatal(1,"FAIL manual register order/value");
     manual_count=manual_count+1;
   end
   if(addr==16'h3008 && wd==8'h02 && manual_count!=6)
     $fatal(1,"FAIL streaming before manual exposure complete");
 end
 reg[15:0] expected[0:23];integer i;
 initial begin
  manual_addr[0]=16'h3503;manual_data[0]=8'h03;
  manual_addr[1]=16'h3500;manual_data[1]=8'h00;
  manual_addr[2]=16'h3501;manual_data[2]=8'h0C;
  manual_addr[3]=16'h3502;manual_data[3]=8'h00;
  manual_addr[4]=16'h350a;manual_data[4]=8'h00;
  manual_addr[5]=16'h350b;manual_data[5]=8'h10;
  expected[0]=16'h4740;expected[1]=16'h4300;expected[2]=16'h501f;expected[3]=16'h300e;
  expected[4]=16'h3017;expected[5]=16'h3018;expected[6]=16'h3034;expected[7]=16'h3035;
  expected[8]=16'h3036;expected[9]=16'h3037;expected[10]=16'h3108;expected[11]=16'h3824;
  expected[12]=16'h3808;expected[13]=16'h3809;expected[14]=16'h380a;expected[15]=16'h380b;
  expected[16]=16'h3008;expected[17]=16'h4713;expected[18]=16'h3503;expected[19]=16'h3500;
  expected[20]=16'h3501;expected[21]=16'h3502;expected[22]=16'h350A;expected[23]=16'h350B;
  repeat(5) @(negedge clk);rst=0;
  wait(initdone);@(negedge clk);
  if(manual_count!=6) $fatal(1,"FAIL manual writes missing");
  if(id!==16'h5640 || !idvalid) $fatal(1,"FAIL ID");
  for(i=0;i<24;i=i+1)
   if(rb[i*8+:8] !== (expected[i][15:8]^expected[i][7:0])) $fatal(1,"FAIL readback index %d got %h expected %h all=%h",i,rb[i*8+:8],(expected[i][15:8]^expected[i][7:0]),rb);
  if(rn!==24'h000004 || !nackseen) $fatal(1,"FAIL read nack capture %h",rn);
  $display("ALL TESTS PASS: readback address order, byte packing and NACK reporting");$finish;
 end
 initial begin #1000000;$fatal(1,"WATCHDOG");end
endmodule
