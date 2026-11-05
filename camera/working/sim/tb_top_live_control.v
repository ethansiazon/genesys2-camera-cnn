`timescale 1ns/1ps
// Uses behavioural clock/HDMI stand-ins. Verifies the ACTUAL top-level camera
// pin wiring, chip-ID reads, initialization writes, capture and frame-buffer
// pixels. It does not model MMCM locking or physical TMDS serialization.
module tb_top_live_control;
    reg sysclk=0;
    always #2.5 sysclk=~sysclk;
    reg [7:0] sw=8'h40;
    reg btn=0;reg host_rx=1;
    tri [7:0] ja,jb;
    wire [7:0] led;
    wire [2:0] hp,hn;
    wire hcp,hcn,tx;
    pullup(jb[3]); pullup(jb[7]);
    wire pc,vs,hr;
    wire [7:0] data;
    wire [31:0] frames;
    // Camera data intentionally cannot impersonate the 0x5640 chip ID. A read
    // of JA[5] instead of JB[3] must fail the integration test.
    assign ja[0]=pc; assign ja[1]=data[6];
    assign ja[3]=~hr; assign ja[4]=data[2]; assign ja[5]=data[0];
    assign jb[0]=data[5]; assign jb[1]=data[3];
    assign jb[2]=data[1]; assign jb[4]=data[7];
    assign jb[5]=data[4]; assign jb[6]=vs;
    top_genesys2 #(.SIM_FAST_INIT(1)) dut(
        .sysclk_p(sysclk),.sysclk_n(~sysclk),.sw(sw),.btnc(btn),.led(led),
        .ja(ja),.jb(jb),.hdmi_tx_p(hp),.hdmi_tx_n(hn),
        .hdmi_tx_clk_p(hcp),.hdmi_tx_clk_n(hcn),.uart_tx_in(host_rx),.uart_rx_out(tx));
    ov5640_yuyv_model #(.H_ACTIVE(320),.V_ACTIVE(2),.PCLK_PERIOD(70)) sensor(
        .pclk(pc),.vsync(vs),.href(hr),.d(data),.pwdn(ja[6]),.reset_n(ja[7]),
        .sioc(jb[7]),.siod(jb[3]),.frames_sent(frames));
    integer i,expect_y,expected,errors=0,settled_frame;
    task ck;
        input [255:0] label;
        input integer got,want;
        begin
            if(got !== want) begin
                $display("FAIL %0s got=%0h want=%0h",label,got,want);
                errors=errors+1;
            end else $display("  ok %0s",label);
        end
    endtask

    wire[7:0] host_byte;wire host_byte_valid,host_byte_error;
    uart_rx #(.CLK_HZ(200000000),.BAUD(20000000)) host_monitor(
      .clk(sysclk),.rst(dut.rst200),.rx(tx),.data(host_byte),
      .valid(host_byte_valid),.error(host_byte_error));
    reg[255:0] parsed=0;integer char_count=0,nibble_count=0;
    integer response_count=0;reg[255:0] last_response=0;
    function[3:0] nibble;input[7:0]b;begin
      if(b>="0" && b<="9")nibble=b-"0";
      else if(b>="A" && b<="F")nibble=b-"A"+10;
      else begin $fatal(1,"FAIL non-hex response byte");nibble=0;end
    end endfunction
    always @(posedge sysclk)if(!dut.rst200)begin
      if(host_byte_error)$fatal(1,"FAIL response UART framing");
      if(host_byte_valid)begin
        if(host_byte==10)begin
          if(char_count!=72 || nibble_count!=64)$fatal(1,"FAIL interleaved/short packet");
          if(parsed[31:0]==32'hd1650001)begin last_response=parsed;response_count=response_count+1;end
          char_count=0;nibble_count=0;parsed=0;
        end else begin
          if(host_byte!=13 && host_byte!=32)begin
            parsed[(nibble_count/8)*32+(7-nibble_count%8)*4+:4]=nibble(host_byte);
            nibble_count=nibble_count+1;
          end
          char_count=char_count+1;
        end
      end
    end
    task send_byte;input[7:0]v;integer k;
      begin
        host_rx=0;#50;
        for(k=0;k<8;k=k+1)begin host_rx=v[k];#50;end
        host_rx=1;#50;
      end
    endtask
    task send_command;input[7:0]seq,op;input[15:0]a;input[7:0]v;input bad;
      begin
        send_byte(8'ha5);send_byte(8'h5a);send_byte(seq);send_byte(op);
        send_byte(a[15:8]);send_byte(a[7:0]);send_byte(v);
        send_byte(8'ha5^8'h5a^seq^op^a[15:8]^a[7:0]^v^{7'd0,bad});
      end
    endtask
    task expect_reply;input integer n;input[7:0]seq,status,value;
      begin wait(response_count==n);@(negedge sysclk);
        if(last_response[63:32]!=seq || last_response[127:96]!=status ||
           last_response[223:192]!=value || last_response[255:224]!=32'h4c495645)
          $fatal(1,"FAIL actual-wire reply %h",last_response);
      end
    endtask
    initial begin
        wait(dut.init_done === 1'b1);
        ck("actual top SCCB chip ID",dut.chip_id,16'h5640);
        ck("ID valid",dut.id_valid,1);
        ck("SCCB acknowledgements",dut.nack_seen,0);
        ck("slow system divider",sensor.regs[16'h3035],8'h41);
        ck("explicit DVP polarity",sensor.regs[16'h4740],8'h22);
        ck("YUYV format",sensor.regs[16'h4300],8'h30);
        ck("YUV mux",sensor.regs[16'h501f],0);
        ck("width low byte",sensor.regs[16'h3809],8'h40);
        ck("height low byte",sensor.regs[16'h380b],8'hf0);
        settled_frame=frames+4; wait(frames>=settled_frame); repeat(50) @(posedge sysclk);
        ck("captured pixels/frame",dut.pix_pf,640);
        ck("last x",dut.xmax_raw,319);
        ck("last y",dut.ymax_raw,1);
        // First/last pair, second line, and several interior pixels; conversion
        // matches the studio-range neutral-chroma reference independently.
        for(i=0;i<640;i=i+1) begin
            expect_y=16+((i%320+i/320)%200);
            expected=(298*(expect_y-16)+128)>>8;
            if(dut.fb_i.storage.g_bank[0].memory[i] !== {3{expected[7:0]}}) begin
                if(errors<10)$display("FAIL stored pixel %0d got=%h want=%h",i,dut.fb_i.storage.g_bank[0].memory[i],{3{expected[7:0]}});
                errors=errors+1;
            end
        end
        ck("all 640 stored pixels",errors,0);
        ck("manual exposure restored",sensor.regs[16'h3501],8'h08);
        ck("ISP first bank value",dut.config_readback[199:192],8'hA7);
        force dut.diagnostic_page=3'd4;#1;
        ck("ISP UART page tag",dut.diagnostic_words[31:0],32'hD1640004);
        ck("ISP UART first data byte",dut.diagnostic_words[39:32],8'hA7);
        ck("ISP UART second data byte",dut.diagnostic_words[47:40],8'hA3);
        ck("ISP UART NACK mask",dut.diagnostic_words[255:224],0);
        release dut.diagnostic_page;

        // Send a control request during a normal telemetry packet; verify
        // both full packets survive the common UART formatter without mixing.
        @(negedge sysclk);force dut.m_tick=1;@(negedge sysclk);release dut.m_tick;
        send_command(1,8'h50,0,0,0);expect_reply(1,1,0,0);
        send_command(2,8'h52,16'h300a,0,0);expect_reply(2,2,0,8'h56);
        send_command(3,8'h57,16'h3406,1,0);expect_reply(3,3,0,1);
        ck("actual sensor changed by host",sensor.regs[16'h3406],1);
        send_command(4,8'h57,16'h3035,0,0);expect_reply(4,4,2,0);
        ck("forbidden PLL write did not execute",sensor.regs[16'h3035],8'h41);
        send_command(5,8'h57,16'h3406,0,1);expect_reply(5,5,1,0);
        ck("bad CRC did not execute",sensor.regs[16'h3406],1);
        sw[7]=1;repeat(8)@(negedge sysclk);
        send_command(6,8'h57,16'h3406,0,0);#10000;
        ck("recording blocks host mutation",sensor.regs[16'h3406],1);
        ck("recording defers control response",response_count,5);
        sw[7]=0;expect_reply(6,6,3,0);
        send_command(7,8'h57,16'h3406,0,0);expect_reply(7,7,0,0);
        ck("automatic WB restored",sensor.regs[16'h3406],0);
        ck("camera still initialized",dut.init_done,1);
        ck("video capture still complete",dut.pix_pf,640);
        sw[5]=1; repeat(10) @(posedge dut.clk_pix);
        ck("test-pattern switch selects bypass",dut.testpat_en,1);
        if(errors==0)$display("=== ALL TESTS PASS ===");
        else $fatal(1,"%0d integration failures",errors);
        $finish;
    end
    initial begin #10_000_000; $fatal(1,"WATCHDOG top wiring"); end
endmodule

module clk_gen(input sysclk_p,sysclk_n,output clk200,output reg clk24=0,
               output reg clk_pix=0,output reg clk_pix5x=0,output reg locked=0);
    assign clk200=sysclk_p;
    always #20.833333 clk24=~clk24;
    always #20 clk_pix=~clk_pix;
    always #4 clk_pix5x=~clk_pix5x;
    initial #200 locked=1;
endmodule
module ODDR #(parameter DDR_CLK_EDGE="SAME_EDGE",INIT=0,SRTYPE="ASYNC")
    (output Q,input C,CE,D1,D2,R,S);
    assign Q=C;
endmodule
module hdmi_out(input clk_pix,clk_pix5x,rst,input[7:0]red,green,blue,
    input hsync,vsync,de,output[2:0]tmds_p,tmds_n,
    output tmds_clk_p,tmds_clk_n);
    assign tmds_p=3'b000; assign tmds_n=3'b111;
    assign tmds_clk_p=clk_pix; assign tmds_clk_n=~clk_pix;
endmodule

module BUFG(input I,output O); assign O=I; endmodule
