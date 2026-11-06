`timescale 1ns/1ps
// Uses behavioural clock/HDMI stand-ins. Verifies the ACTUAL top-level camera
// pin wiring, chip-ID reads, initialization writes, capture and frame-buffer
// pixels. It does not model MMCM locking or physical TMDS serialization.
module tb_top_rgb565 #(parameter integer REFERENCE_READOUT=0);
    reg sysclk=0;
    always #2.5 sysclk=~sysclk;
    reg [7:0] sw=8'h40;
    reg btn=0;
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
    // Same short excursions that the qualified YUV fixture rejects.
    reg glitch=0;
    always @(posedge pc or negedge pc)begin #8;glitch=1;#5;glitch=0;end
    assign ja[0]=pc^glitch; assign ja[1]=data[6];
    assign ja[3]=~hr^glitch; assign ja[4]=data[2]; assign ja[5]=data[0];
    assign jb[0]=data[5]; assign jb[1]=data[3];
    assign jb[2]=data[1]; assign jb[4]=data[7];
    assign jb[5]=data[4]; assign jb[6]=vs^glitch;
    top_genesys2 #(.SIM_FAST_INIT(1),.RGB565(1),.REFERENCE_READOUT(REFERENCE_READOUT)) dut(
        .sysclk_p(sysclk),.sysclk_n(~sysclk),.sw(sw),.btnc(btn),.led(led),
        .ja(ja),.jb(jb),.hdmi_tx_p(hp),.hdmi_tx_n(hn),
        .hdmi_tx_clk_p(hcp),.hdmi_tx_clk_n(hcn),.uart_tx_in(1'b1),.uart_rx_out(tx));
    ov5640_yuyv_model #(.H_ACTIVE(320),.V_ACTIVE(2),.PCLK_PERIOD(REFERENCE_READOUT == 5 ? 56 : (REFERENCE_READOUT == 4 ? 76 : 70))) sensor(
        .pclk(pc),.vsync(vs),.href(hr),.d(data),.pwdn(ja[6]),.reset_n(ja[7]),
        .sioc(jb[7]),.siod(jb[3]),.frames_sent(frames));
    integer i,expect_y,expected,actual,errors=0,settled_frame;
    function integer absval;input integer x;begin absval=x<0?-x:x;end endfunction
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
    initial begin
        wait(dut.init_done === 1'b1);
        ck("actual top SCCB chip ID",dut.chip_id,16'h5640);
        ck("ID valid",dut.id_valid,1);
        ck("SCCB acknowledgements",dut.nack_seen,0);
        ck("system divider",sensor.regs[16'h3035],REFERENCE_READOUT >= 2 ? 8'h21 : 8'h41);
        ck("PLL multiplier",sensor.regs[16'h3036],REFERENCE_READOUT == 4 ? 8'h64 : (REFERENCE_READOUT >= 3 ? 8'h5a : 8'h48));
        ck("DVP divider",sensor.regs[16'h3824],REFERENCE_READOUT == 4 ? 6 : ((REFERENCE_READOUT == 3 || REFERENCE_READOUT == 5) ? 5 : 4));
        ck("line length",{sensor.regs[16'h380c],sensor.regs[16'h380d]},REFERENCE_READOUT == 4 ? 2112 : 1896);
        ck("explicit DVP polarity",sensor.regs[16'h4740],8'h22);
        ck("RGB565 format",sensor.regs[16'h4300],8'h61);
        ck("RGB mux",sensor.regs[16'h501f],1);
        ck("width low byte",sensor.regs[16'h3809],8'h40);
        ck("height low byte",sensor.regs[16'h380b],8'hf0);
        ck("horizontal increment",sensor.regs[16'h3814],REFERENCE_READOUT ? 8'h31 : 8'h71);
        ck("vertical increment",sensor.regs[16'h3815],REFERENCE_READOUT ? 8'h31 : 8'h71);
        ck("frame length",{sensor.regs[16'h380e],sensor.regs[16'h380f]},REFERENCE_READOUT ? 984 : 520);
        if(REFERENCE_READOUT) begin
            ck("readout 3618",sensor.regs[16'h3618],8'h00);
            ck("readout 3612",sensor.regs[16'h3612],8'h29);
            ck("readout 3708",sensor.regs[16'h3708],8'h64);
            ck("readout 3709",sensor.regs[16'h3709],8'h52);
            ck("readout 370c",sensor.regs[16'h370c],8'h03);
            ck("black reference start",sensor.regs[16'h4001],8'h02);
            ck("black reference lines",sensor.regs[16'h4004],8'h02);
        end
        settled_frame=frames+4; wait(frames>=settled_frame); repeat(50) @(posedge sysclk);
        ck("captured pixels/frame",dut.pix_pf,640);
        ck("last x",dut.xmax_raw,319);
        ck("last y",dut.ymax_raw,1);
        // Known colour bars plus a second row of independently packed words.
        // Ideal 5/6bit->8bit scaling allows one level for bit replication.
        for(i=0;i<640;i=i+1) begin
            if(i<320) begin
                case(i%8)
                0:expected=24'hFF0000;1:expected=24'h00FF00;
                2:expected=24'h0000FF;3:expected=24'hFFFFFF;
                4:expected=24'h000000;5:expected=24'hFFFF00;
                6:expected=24'h00FFFF;7:expected=24'hFF00FF;
                endcase
            end else begin
                expect_y=((i%320)*109+811)&65535;
                expected=((((expect_y>>11)&31)*255+15)/31)<<16 |
                         ((((expect_y>>5)&63)*255+31)/63)<<8 |
                         (((expect_y&31)*255+15)/31);
            end
            actual=dut.fb_i.storage.g_bank[0].memory[i];
            if(absval((actual>>16&255)-(expected>>16&255))>1 ||
               absval((actual>>8&255)-(expected>>8&255))>1 ||
               absval((actual&255)-(expected&255))>1 || ^actual===1'bx) begin
                if(errors<10)$display("FAIL RGB pixel%0d got=%h expected=%h",i,actual,expected);
                errors=errors+1;
            end
        end
        ck("all 640 stored pixels",errors,0);
        ck("manual exposure",{sensor.regs[16'h3500],sensor.regs[16'h3501],sensor.regs[16'h3502]},
           (REFERENCE_READOUT >= 3 ? 400 : 128) << 4);
        ck("ISP first bank value",dut.config_readback[199:192],8'hA7);
        force dut.diagnostic_page=3'd4;#1;
        ck("ISP UART page tag",dut.diagnostic_words[31:0],32'hD1640004);
        ck("ISP UART first data byte",dut.diagnostic_words[39:32],8'hA7);
        ck("ISP UART second data byte",dut.diagnostic_words[47:40],8'hA3);
        ck("ISP UART NACK mask",dut.diagnostic_words[255:224],0);
        release dut.diagnostic_page;
        sw[5]=1; repeat(10) @(posedge dut.clk_pix);
        ck("test-pattern switch selects bypass",dut.testpat_en,1);
        if(errors==0)$display("=== ALL TESTS PASS ===");
        else $fatal(1,"%0d integration failures",errors);
        $finish;
    end
    initial begin #10_000_000; $fatal(1,"WATCHDOG top wiring"); end
    // These sensor-mode writes must complete before enabling the live array.
    // This checks transaction ordering, not just the final register image.
    always @(posedge sysclk) if(REFERENCE_READOUT && dut.init_i.sccb_start &&
        !dut.init_i.sccb_rw && dut.init_i.sccb_addr==16'h3008 &&
        dut.init_i.sccb_wdata==8'h02) begin
        if(sensor.regs[16'h3618]!==8'h00 || sensor.regs[16'h3612]!==8'h29 ||
           sensor.regs[16'h3708]!==8'h64 || sensor.regs[16'h3709]!==8'h52 ||
           sensor.regs[16'h370c]!==8'h03 || sensor.regs[16'h4001]!==8'h02 ||
           sensor.regs[16'h4004]!==8'h02 || sensor.regs[16'h380e]!==8'h03 ||
           sensor.regs[16'h380f]!==8'hd8)
            $fatal(1,"FAIL streaming before readout profile completed");
    end
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
