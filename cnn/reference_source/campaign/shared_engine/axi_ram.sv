// Simulation-only compact AXI4 memory. Never synthesized into the CNN.
// Single outstanding read/write with independent channels and deterministic stalls.
`timescale 1ns/1ps
module g2_axi_ram #(parameter WORDS=1024, parameter FILE="",parameter READ_ONLY=0,parameter INPUT_WORDS=0)(
 input wire clk,resetn,
 input wire arvalid,output wire arready,input wire[63:0] araddr,input wire[7:0] arlen,input wire[2:0] arsize,input wire[1:0] arburst,input wire arid,
 output reg rvalid,input wire rready,output reg[127:0] rdata,output reg rlast,output reg rid,output wire[1:0] rresp,
 input wire awvalid,output wire awready,input wire[63:0] awaddr,input wire[7:0] awlen,input wire[2:0] awsize,input wire[1:0] awburst,input wire awid,
 input wire wvalid,output wire wready,input wire[127:0] wdata,input wire[15:0] wstrb,input wire wlast,
 output reg bvalid,input wire bready,output reg bid,output wire[1:0] bresp
);
 bit[127:0] mem[0:WORDS-1];
 bit valid[0:WORDS-1];
 reg reading,writing;reg[63:0] ra,wa;integer rn,wn,rs,ws,delay,cycle;
 longint unsigned read_beats=0,write_beats=0;
 assign arready=resetn && !reading && !rvalid && cycle%7!=0;
 assign awready=resetn && !writing && !bvalid && cycle%11!=0;
 assign wready=resetn && writing && cycle%5!=0;
 assign rresp=0;assign bresp=0;
 initial begin
   for(integer i=0;i<WORDS;i++)begin mem[i]=0;valid[i]=(READ_ONLY || i<INPUT_WORDS);end
   if(FILE!="")$readmemh(FILE,mem);
 end
 always @(posedge clk)begin
  if(!resetn)begin reading<=0;writing<=0;rvalid<=0;bvalid<=0;rdata<=0;rlast<=0;rid<=0;bid<=0;cycle<=0;delay<=0;ra<=0;wa<=0;rn<=0;wn<=0;rs<=0;ws<=0;end
  else begin
   cycle<=cycle+1;
   if(arvalid && arready)begin
    if(arburst!=1 || arsize>4 || (araddr & ((64'd1<<arsize)-1))!=0 || (araddr>>4)>=WORDS)$fatal(1,"Unsupported/out-of-range AXI read addr=%h size=%d",araddr,arsize);
    reading<=1;ra<=araddr;rn<=arlen+1;rs<=arsize;rid<=arid;delay<=2;
   end
   if(reading)begin
    if(delay>0)delay<=delay-1;
    else if(!rvalid)begin
     if((ra>>4)>=WORDS || !valid[ra>>4])$fatal(1,"Read unwritten/out-of-range address %h",ra);
     rvalid<=1;rdata<=mem[ra>>4];rlast<=(rn==1);
    end else if(rready)begin
     read_beats<=read_beats+1;
     if(rn==1)begin reading<=0;rvalid<=0;rlast<=0;end
     else begin
      if(((ra+(64'd1<<rs))>>4)>=WORDS || !valid[(ra+(64'd1<<rs))>>4])$fatal(1,"Read burst crosses unwritten/out-of-range word");
      ra<=ra+(64'd1<<rs);rn<=rn-1;rdata<=mem[(ra+(64'd1<<rs))>>4];rlast<=(rn==2);
     end
    end
   end
   if(bvalid && bready)bvalid<=0;
   if(awvalid && awready)begin
    if(READ_ONLY || awburst!=1 || awsize>4 || (awaddr & ((64'd1<<awsize)-1))!=0 || (awaddr>>4)>=WORDS)$fatal(1,"Unsupported/out-of-range AXI write");
    writing<=1;wa<=awaddr;wn<=awlen+1;ws<=awsize;bid<=awid;
   end
   if(wvalid && wready)begin
    if((wa>>4)>=WORDS || wlast!=(wn==1))$fatal(1,"AXI write bounds/last mismatch");
    for(integer j=0;j<16;j++)if(wstrb[j])mem[wa>>4][j*8+:8]<=wdata[j*8+:8];
    valid[wa>>4]<=1;write_beats<=write_beats+1;
    if(wn==1)begin writing<=0;bvalid<=1;end
    else begin wa<=wa+(64'd1<<ws);wn<=wn-1;end
   end
  end
 end
endmodule
