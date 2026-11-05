`timescale 1ns/1ps
module tb_uart_rx;
 reg clk=0;always #5 clk=~clk;
 reg rst=1,rx=1;wire[7:0]data;wire valid,error;
 integer count=0,errors=0;reg[7:0]got[0:7];integer i;
 uart_rx #(.CLK_HZ(2000),.BAUD(100)) dut(clk,rst,rx,data,valid,error);
 always @(posedge clk)begin
  if(valid)begin got[count]=data;count=count+1;end
  if(error)errors=errors+1;
 end
 task cycles;input integer n;begin repeat(n)@(negedge clk);end endtask
 task send;input[7:0]v;input good_stop;integer j;
  begin rx=0;cycles(20);for(j=0;j<8;j=j+1)begin rx=v[j];cycles(20);end
   rx=good_stop;cycles(20);end
 endtask
 initial begin
  cycles(5);rst=0;cycles(5);
  rx=0;cycles(3);rx=1;cycles(30); // False start must not make a byte.
  if(count!=0)$fatal(1,"FAIL false start");
  send(8'ha5,1);send(8'h00,1);send(8'hff,1);send(8'h5a,1);cycles(10);
  if(count!=4 || got[0]!=8'ha5 || got[1]!=0 || got[2]!=255 || got[3]!=8'h5a)
   $fatal(1,"FAIL byte decoding/back-to-back bytes");
  send(8'h33,0);cycles(40);
  if(errors!=1 || count!=4)$fatal(1,"FAIL framing/break rejection");
  rx=1;cycles(30);send(8'h72,1);cycles(10);
  if(count!=5 || got[4]!=8'h72)$fatal(1,"FAIL recovery after framing error");
  $display("ALL TESTS PASS: UART centres, back-to-back bytes, false start, framing and break recovery");$finish;
 end
 initial begin #1000000;$fatal(1,"WATCHDOG");end
endmodule
