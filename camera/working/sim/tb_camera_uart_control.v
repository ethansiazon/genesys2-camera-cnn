`timescale 1ns/1ps
module tb_camera_uart_control;
 reg clk=0;always #5 clk=~clk;
 reg rst=1,rv=0,re=0,blocked=0;reg[7:0]rd=0;
 wire cv,crw;wire[15:0]ca;wire[7:0]cw;
 reg ready=1,done=0,nack=0;reg[7:0]value=0;
 wire reply;wire[255:0]words;reg take=0;
 integer requests=0,writes=0,reads=0,delay_count=0;
 reg op_nack=0,mismatch=0,hang=0,pending=0;reg[7:0]stored=8'h40;
 camera_uart_control #(.CLK_HZ(1000),.FRAME_TIMEOUT(30),.OP_TIMEOUT(80)) dut(
  .clk(clk),.rst(rst),.rx_data(rd),.rx_valid(rv),.rx_error(re),.blocked(blocked),
  .cfg_valid(cv),.cfg_rw(crw),.cfg_addr(ca),.cfg_wdata(cw),.cfg_ready(ready),
  .cfg_done(done),.cfg_rdata(value),.cfg_nack(nack),
  .reply_valid(reply),.reply_words(words),.reply_take(take));
 always @(posedge clk)begin
  done<=0;
  if(rst)begin requests=0;writes=0;reads=0;delay_count=0;pending=0;end
  else if(cv && ready)begin
   requests=requests+1;delay_count=3;pending=1;ready<=0;
   if(crw)begin reads=reads+1;value<=mismatch ? stored^8'h01 : stored;end
   else begin writes=writes+1;stored=cw;end
   nack<=op_nack;
  end else if(pending && !hang)begin
   if(delay_count==0)begin done<=1;ready<=1;pending=0;end
   else delay_count=delay_count-1;
  end
 end
 task cyc;input integer n;begin repeat(n)@(negedge clk);end endtask
 task byte_in;input[7:0]b;begin rd=b;rv=1;cyc(1);rv=0;cyc(1);end endtask
 task command;input[7:0]seq,op;input[15:0]addr;input[7:0]v;input bad_crc;
  reg[7:0]cs;begin
   cs=8'ha5^8'h5a^seq^op^addr[15:8]^addr[7:0]^v;
   byte_in(8'ha5);byte_in(8'h5a);byte_in(seq);byte_in(op);
   byte_in(addr[15:8]);byte_in(addr[7:0]);byte_in(v);byte_in(cs^{7'd0,bad_crc});
  end endtask
 task response;input[7:0]seq,status;
  begin wait(reply);cyc(1);
   if(words[31:0]!=32'hd1650001 || words[63:32]!=seq || words[127:96]!=status || words[255:224]!=32'h4c495645)
    $fatal(1,"FAIL response seq/status got %h",words);
   take=1;cyc(1);take=0;cyc(2);
  end endtask
 integer before_requests;
 initial begin
  cyc(5);rst=0;cyc(2);
  command(1,8'h50,0,0,0);response(1,0);
  command(2,8'h52,16'h300a,0,0);response(2,0);
  if(reads!=1 || writes!=0)$fatal(1,"FAIL read request");
  command(3,8'h57,16'h3406,1,0);response(3,0);
  if(reads!=2 || writes!=1)$fatal(1,"FAIL mandatory write verification");
  before_requests=requests;
  command(4,8'h57,16'h3035,8'h41,0);response(4,2);
  command(5,8'h57,16'h3406,8'h80,0);response(5,2);
  command(6,8'h57,16'h3406,1,1);response(6,1);
  command(7,8'h99,16'h3406,1,0);response(7,1);
  blocked=1;command(8,8'h57,16'h3406,1,0);response(8,3);blocked=0;
  if(requests!=before_requests)$fatal(1,"FAIL denied/malformed/blocked request touched SCCB");
  op_nack=1;command(9,8'h52,16'h300a,0,0);response(9,4);op_nack=0;
  mismatch=1;command(10,8'h57,16'h3406,0,0);response(10,7);mismatch=0;
  byte_in(8'ha5);byte_in(8'h5a);byte_in(11);cyc(35);response(11,1);
  re=1;cyc(1);re=0;response(11,6);
  ready=0;command(12,8'h52,16'h300a,0,0);cyc(10);ready=1;response(12,0);
  ready=0;command(13,8'h52,16'h300a,0,0);response(13,5);ready=1;
  hang=1;command(14,8'h52,16'h300a,0,0);response(14,5);
  hang=0;cyc(8);command(15,8'h50,0,0,0);response(15,0);
  $display("ALL TESTS PASS: protocol, allowlist, values, busy, CRC, readback/NACK, timeouts and recovery");$finish;
 end
 initial begin #1000000;$fatal(1,"WATCHDOG");end
endmodule
