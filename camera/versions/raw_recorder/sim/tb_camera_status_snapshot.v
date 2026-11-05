`timescale 1ns/1ps
module tb_camera_status_snapshot;
    reg sclk=0,dclk=0,rst=1,request=0;
    always #19 sclk=~sclk;
    always #2.5 dclk=~dclk;
    reg [31:0] count=0;
    always @(posedge sclk) if(rst)count<=0;else count<=count+1;
    wire [63:0] result;
    camera_status_snapshot #(.WIDTH(64)) dut(
        .src_clk(sclk),.src_rst(rst),.src_data({count,~count}),
        .dst_clk(dclk),.dst_rst(rst),.request(request),.dst_data(result));
    integer i;
    reg [31:0] previous=0;
    initial begin
        #200;@(negedge dclk);rst=0;
        for(i=0;i<50;i=i+1)begin
            @(negedge dclk);request=1;
            @(negedge dclk);request=0;
            repeat(50)@(negedge dclk);
            if(result[63:32]!==~result[31:0])$fatal(1,"FAIL torn snapshot");
            if(result[63:32]<=previous)$fatal(1,"FAIL stale snapshot");
            previous=result[63:32];
        end
        $display("=== ALL TESTS PASS ===");$finish;
    end
    initial begin #100000;$fatal(1,"WATCHDOG snapshot");end
endmodule
