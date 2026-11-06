`timescale 1ns/1ps
module tb_pipeline_end_to_end;
 reg src=0,dst=0,rst=1,href=0,vs=0;reg[7:0]d=0;
 always #70 src=~src;
 always #2.5 dst=~dst;
 wire[16:0]wa;wire[23:0]wd;wire we;wire[48:0]dbg;
 cam_capture #(.SOURCE_SYNC(1),.SYNC_FILTER(0),.MEDIAN3(0),.TEMPORAL(0)) cap(
  .clk(src),.rst(rst),.pclk_i(src),.vsync_i(vs),.href_i(href),.d_i(d),
  .uyvy(1'b0),.full_range(1'b0),.wr_addr(wa),.wr_data(wd),.wr_en(we),
  .fb_old(24'd0),.debug_state(dbg));
 wire[127:0]sample={13'd0,dbg,24'd0,wd,wa,we};
 wire trigger=dbg[8]&&dbg[12:11]==0&&dbg[22:13]==0&&dbg[32:23]==16;
 pipeline_recorder rec(.src_clk(src),.src_rst(rst),.dst_clk(dst),.dst_rst(rst),
  .arm(1'b1),.trigger(trigger),.sample(sample),.report_busy(1'b1),.words(),.go());
 integer y,x,i,f;reg[127:0]v;
 initial begin
  repeat(10)@(negedge src);rst=0;
  vs=1;repeat(10)@(negedge src);vs=0;repeat(10)@(negedge src);
  for(y=0;y<24;y=y+1)begin
   href=1;
   for(x=0;x<320;x=x+2)begin
    d=16+(x*7+y*13)%220;@(negedge src);
    d=32+(x*3+y*5)%192;@(negedge src);
    d=16+((x+1)*7+y*13)%220;@(negedge src);
    d=32+(x*11+y*2)%192;@(negedge src);
   end
   href=0;repeat(400)@(negedge src);
  end
 end
 initial begin
  wait(rec.captured);@(negedge src);
  f=$fopen("pipeline_sim.txt","w");
  for(i=0;i<2048;i=i+1)begin
   v=rec.memory[i];
   $fdisplay(f,"%08h %08h %08h %08h %08h 00000800 00000000 50495045",
    32'hD1680000|i,v[31:0],v[63:32],v[95:64],v[127:96]);
  end
  $fclose(f);$display("PIPELINE FIXTURE SAVED");$finish;
 end
 initial begin #10000000;$fatal(1,"capture timeout");end
endmodule
