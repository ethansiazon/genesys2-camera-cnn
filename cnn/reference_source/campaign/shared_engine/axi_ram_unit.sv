`timescale 1ns/1ps
module axi_ram_unit(input wire clk,resetn,output reg done=0);
 reg arvalid=0,rready=0,awvalid=0,wvalid=0,bready=0;
 reg[63:0]araddr=0,awaddr=0;reg[7:0]arlen=3,awlen=3;reg[127:0]wdata=0;reg[15:0]wstrb=16'hffff;reg wlast=0;
 wire arready,rvalid,rlast,rid,awready,wready,bvalid,bid;wire[127:0]rdata;wire[1:0]rresp,bresp;
 g2_axi_ram #(.WORDS(8),.INPUT_WORDS(8)) m(.clk(clk),.resetn(resetn),
  .arvalid(arvalid),.arready(arready),.araddr(araddr),.arlen(arlen),.arsize(3'd4),.arburst(2'd1),.arid(1'b1),
  .rvalid(rvalid),.rready(rready),.rdata(rdata),.rlast(rlast),.rid(rid),.rresp(rresp),
  .awvalid(awvalid),.awready(awready),.awaddr(awaddr),.awlen(awlen),.awsize(3'd4),.awburst(2'd1),.awid(1'b1),
  .wvalid(wvalid),.wready(wready),.wdata(wdata),.wstrb(wstrb),.wlast(wlast),.bvalid(bvalid),.bready(bready),.bid(bid),.bresp(bresp));
 reg[127:0] expected[0:3],held;
 initial begin
  wait(resetn);@(negedge clk);awvalid=1;
  do @(posedge clk);while(!awready);
  @(negedge clk);awvalid=0;
  for(integer i=0;i<4;i++)begin
   wdata=128'h112233445566778899aabbccddeeff00+i;wstrb=(i==2)?16'hfff0:16'hffff;wlast=(i==3);wvalid=1;
   expected[i]=wdata;if(i==2)expected[i][31:0]=0;
   do @(posedge clk);while(!wready);
   @(negedge clk);wvalid=0;
  end
  bready=1;do @(posedge clk);while(!bvalid);
  if(bid!=1 || bresp!=0)$fatal(1,"Unit write response failed");
  @(negedge clk);bready=0;arvalid=1;
  do @(posedge clk);while(!arready);
  @(negedge clk);arvalid=0;
  for(integer i=0;i<4;i++)begin
   wait(rvalid);held=rdata;
   repeat(3)begin @(negedge clk);if(rdata!==held || !rvalid)$fatal(1,"Unit read changed under backpressure");end
   if(rdata!==expected[i] || rlast!=(i==3) || rid!=1 || rresp!=0)$fatal(1,"Unit data/strobes/last/id failed beat%d",i);
   rready=1;@(posedge clk);@(negedge clk);rready=0;
  end
  done=1;$display("AXI_RAM_UNIT_PASS: burst,byte strobes,IDs,last,read/write stalls and held-data tested");
 end
endmodule
