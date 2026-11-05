`timescale 1ns/1ps
module tb_init_analog_reference;
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

 reg[23:0] expected_write[0:88]; integer write_count=0;
 initial begin
 expected_write[0]={16'h3008,8'h82};
 expected_write[1]={16'h3008,8'h42};
 expected_write[2]={16'h3103,8'h13};
 expected_write[3]={16'h3630,8'h36};
 expected_write[4]={16'h3631,8'h0E};
 expected_write[5]={16'h3632,8'hE2};
 expected_write[6]={16'h3633,8'h12};
 expected_write[7]={16'h3621,8'hE0};
 expected_write[8]={16'h3704,8'hA0};
 expected_write[9]={16'h3703,8'h5A};
 expected_write[10]={16'h3715,8'h78};
 expected_write[11]={16'h3717,8'h01};
 expected_write[12]={16'h370B,8'h60};
 expected_write[13]={16'h3705,8'h1A};
 expected_write[14]={16'h3905,8'h02};
 expected_write[15]={16'h3906,8'h10};
 expected_write[16]={16'h3901,8'h0A};
 expected_write[17]={16'h3731,8'h12};
 expected_write[18]={16'h3600,8'h08};
 expected_write[19]={16'h3601,8'h33};
 expected_write[20]={16'h302D,8'h60};
 expected_write[21]={16'h3620,8'h52};
 expected_write[22]={16'h371B,8'h20};
 expected_write[23]={16'h471C,8'h50};
 expected_write[24]={16'h3A13,8'h43};
 expected_write[25]={16'h3A18,8'h00};
 expected_write[26]={16'h3A19,8'hF8};
 expected_write[27]={16'h3635,8'h13};
 expected_write[28]={16'h3636,8'h03};
 expected_write[29]={16'h3634,8'h40};
 expected_write[30]={16'h3622,8'h01};
 expected_write[31]={16'h3017,8'hFF};
 expected_write[32]={16'h3018,8'hFF};
 expected_write[33]={16'h3016,8'hC3};
 expected_write[34]={16'h3020,8'h21};
 expected_write[35]={16'h4713,8'h02};
 expected_write[36]={16'h5001,8'h83};
 expected_write[37]={16'h3000,8'h20};
 expected_write[38]={16'h3002,8'h1C};
 expected_write[39]={16'h3004,8'hFF};
 expected_write[40]={16'h3006,8'hC3};
 expected_write[41]={16'h5000,8'hA7};
 expected_write[42]={16'h5001,8'hA3};
 expected_write[43]={16'h5003,8'h08};
 expected_write[44]={16'h370C,8'h02};
 expected_write[45]={16'h3634,8'h40};
 expected_write[46]={16'h3039,8'h00};
 expected_write[47]={16'h3034,8'h1A};
 expected_write[48]={16'h3035,8'h41};
 expected_write[49]={16'h3036,8'h48};
 expected_write[50]={16'h3037,8'h13};
 expected_write[51]={16'h3108,8'h01};
 expected_write[52]={16'h3824,8'h04};
 expected_write[53]={16'h460C,8'h22};
 expected_write[54]={16'h3820,8'h41};
 expected_write[55]={16'h3821,8'h07};
 expected_write[56]={16'h3814,8'h71};
 expected_write[57]={16'h3815,8'h71};
 expected_write[58]={16'h3800,8'h00};
 expected_write[59]={16'h3801,8'h00};
 expected_write[60]={16'h3802,8'h00};
 expected_write[61]={16'h3803,8'h04};
 expected_write[62]={16'h3804,8'h0A};
 expected_write[63]={16'h3805,8'h3F};
 expected_write[64]={16'h3806,8'h07};
 expected_write[65]={16'h3807,8'h9B};
 expected_write[66]={16'h3808,8'h01};
 expected_write[67]={16'h3809,8'h40};
 expected_write[68]={16'h380A,8'h00};
 expected_write[69]={16'h380B,8'hF0};
 expected_write[70]={16'h380C,8'h07};
 expected_write[71]={16'h380D,8'h68};
 expected_write[72]={16'h380E,8'h02};
 expected_write[73]={16'h380F,8'h08};
 expected_write[74]={16'h3810,8'h00};
 expected_write[75]={16'h3811,8'h10};
 expected_write[76]={16'h3812,8'h00};
 expected_write[77]={16'h3813,8'h06};
 expected_write[78]={16'h4300,8'h30};
 expected_write[79]={16'h501F,8'h00};
 expected_write[80]={16'h4740,8'h22};
 expected_write[81]={16'h503D,8'h00};
 expected_write[82]={16'h3503,8'h03};
 expected_write[83]={16'h3500,8'h00};
 expected_write[84]={16'h3501,8'h08};
 expected_write[85]={16'h3502,8'h00};
 expected_write[86]={16'h350A,8'h00};
 expected_write[87]={16'h350B,8'h10};
 expected_write[88]={16'h3008,8'h02};
 end
 always @(posedge clk) if(!rst && start && !busy && !rw) begin
 if(write_count>=89) $fatal(1,"FAIL extra startup write");
 if({addr,wd}!==expected_write[write_count]) $fatal(1,"FAIL startup write %0d got %h expected %h",write_count,{addr,wd},expected_write[write_count]);
 write_count=write_count+1;
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
  manual_addr[2]=16'h3501;manual_data[2]=8'h08;
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
  if(write_count!=89) $fatal(1,"FAIL missing startup writes");
  if(manual_count!=6) $fatal(1,"FAIL manual writes missing");
  if(id!==16'h5640 || !idvalid) $fatal(1,"FAIL ID");
  for(i=0;i<24;i=i+1)
   if(rb[i*8+:8] !== (expected[i][15:8]^expected[i][7:0])) $fatal(1,"FAIL readback index %d got %h expected %h all=%h",i,rb[i*8+:8],(expected[i][15:8]^expected[i][7:0]),rb);
  if(rn!==24'h000004 || !nackseen) $fatal(1,"FAIL read nack capture %h",rn);
  $display("ALL TESTS PASS: readback address order, byte packing and NACK reporting");$finish;
 end
 initial begin #1000000;$fatal(1,"WATCHDOG");end
endmodule
