`timescale 1ns/1ps
module tb_yuv_word_observer;
 reg clk=0,rst=1;reg[48:0]state=0;always #5 clk=~clk;
 wire we;wire[16:0]addr;wire[15:0]data;
 yuv_word_observer #(.H(4),.V(2))dut(.clk(clk),.rst(rst),.state(state),.wr_en(we),.wr_addr(addr),.wr_data(data));
 integer g,p,n=0;reg[7:0]v;
 function[7:0]pattern;input integer group_id,phase;begin pattern=(group_id*53+phase*37+13)&255;end endfunction
 initial begin
  repeat(3)@(negedge clk);rst=0;
  for(g=0;g<4;g=g+1)for(p=0;p<4;p=p+1)begin
   @(negedge clk);v=pattern(g,p);
   state={16'd17,10'(g/2),10'((g%2)*2),2'(p),1'b0,1'b1,1'b1,v};
   @(negedge clk);state=0;
  end
  repeat(4)@(negedge clk);
  if(n!=8)$fatal(1,"FAIL missing words");
  $display("ALL TESTS PASS");$finish;
 end
 always @(posedge clk)begin
  #1;
  if(we)begin
   if(addr!==n)$fatal(1,"FAIL word address");
   if(data!=={pattern(n/2,(n%2)*2),pattern(n/2,(n%2)*2+1)})$fatal(1,"FAIL byte loss/order");
   n=n+1;
  end
 end
 initial begin #100000;$fatal(1,"WATCHDOG");end
endmodule
