`timescale 1ns/1ps
// Uses behavioural clock/HDMI stand-ins. Verifies the ACTUAL top-level camera
// pin wiring, chip-ID reads, initialization writes, capture and frame-buffer
// pixels. It does not model MMCM locking or physical TMDS serialization.
module tb_top_wiring_inverted;
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
    assign ja[0]=pc; assign ja[1]=data[6];
    assign ja[3]=~hr; assign ja[4]=data[2]; assign ja[5]=data[0];
    assign jb[0]=data[5]; assign jb[1]=data[3];
    assign jb[2]=data[1]; assign jb[4]=data[7];
    assign jb[5]=data[4]; assign jb[6]=vs;
    top_genesys2 #(.SIM_FAST_INIT(1)) dut(
        .sysclk_p(sysclk),.sysclk_n(~sysclk),.sw(sw),.btnc(btn),.led(led),
        .ja(ja),.jb(jb),.hdmi_tx_p(hp),.hdmi_tx_n(hn),
        .hdmi_tx_clk_p(hcp),.hdmi_tx_clk_n(hcn),.uart_rx_out(tx));
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
