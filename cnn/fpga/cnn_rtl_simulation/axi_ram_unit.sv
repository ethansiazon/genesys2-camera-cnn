`timescale 1ns/1ps
module axi_ram_unit #(parameter DATA_BITS=128)(input wire clk,resetn,output reg done=0);
 reg arvalid=0,rready=0,awvalid=0,wvalid=0,bready=0;
 reg[63:0]araddr=0,awaddr=0;reg[7:0]arlen=3,awlen=3;reg[DATA_BITS-1:0]wdata=0;reg[DATA_BITS/8-1:0]wstrb={(DATA_BITS/8){1'b1}};reg wlast=0;
 localparam integer ADDR_SHIFT=$clog2(DATA_BITS/8);
 wire arready,rvalid,rlast,rid,awready,wready,bvalid,bid;wire[DATA_BITS-1:0]rdata;wire[1:0]rresp,bresp;
 g2_axi_ram #(.WORDS(8),.INPUT_WORDS(8),.DATA_BITS(DATA_BITS)) m(.clk(clk),.resetn(resetn),
  .arvalid(arvalid),.arready(arready),.araddr(araddr),.arlen(arlen),.arsize(ADDR_SHIFT),.arburst(2'd1),.arid(1'b1),
  .rvalid(rvalid),.rready(rready),.rdata(rdata),.rlast(rlast),.rid(rid),.rresp(rresp),
  .awvalid(awvalid),.awready(awready),.awaddr(awaddr),.awlen(awlen),.awsize(ADDR_SHIFT),.awburst(2'd1),.awid(1'b1),
  .wvalid(wvalid),.wready(wready),.wdata(wdata),.wstrb(wstrb),.wlast(wlast),.bvalid(bvalid),.bready(bready),.bid(bid),.bresp(bresp));
 reg[DATA_BITS-1:0] expected[0:3],held;
 initial begin
  wait(resetn);@(negedge clk);awvalid=1;
  do @(posedge clk);while(!awready);
  @(negedge clk);awvalid=0;
  for(integer i=0;i<4;i++)begin
   for(integer b=0;b<DATA_BITS/8;b++)wdata[b*8+:8]=(b+17*(i+1));wstrb={(DATA_BITS/8){1'b1}};if(i==2)wstrb[3:0]=0;wlast=(i==3);wvalid=1;
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
  done=1;$display("AXI_RAM_UNIT_PASS width=%0d: burst,byte strobes,IDs,last,read/write stalls and held-data tested",DATA_BITS);
 end
endmodule
