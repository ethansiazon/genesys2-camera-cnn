`timescale 1ns/1ps
module tb_top_reference_readout_saved_picture;
    tb_top_rgb565 #(.REFERENCE_READOUT(6)) test();

    task check_register(input [15:0] addr, input [7:0] expected);
        if (test.sensor.regs[addr] !== expected)
            $fatal(1, "Preset register %h was %h before stream enable, expected %h",
                   addr, test.sensor.regs[addr], expected);
    endtask

    always @(posedge test.sysclk) if (test.dut.init_i.sccb_start &&
        !test.dut.init_i.sccb_rw && test.dut.init_i.sccb_addr == 16'h3008 &&
        test.dut.init_i.sccb_wdata == 8'h02) begin
        check_register(16'h3500, 8'h00);
        check_register(16'h3501, 8'h19);
        check_register(16'h3502, 8'h00);
        check_register(16'h350A, 8'h00);
        check_register(16'h350B, 8'h10);
        check_register(16'h3406, 8'h01);
        check_register(16'h3400, 8'h05);
        check_register(16'h3401, 8'h0A);
        check_register(16'h3402, 8'h04);
        check_register(16'h3403, 8'h00);
        check_register(16'h3404, 8'h07);
        check_register(16'h3405, 8'h4B);
        check_register(16'h5480, 8'h01);
        check_register(16'h5481, 8'h08);
        check_register(16'h5482, 8'h14);
        check_register(16'h5483, 8'h28);
        check_register(16'h5484, 8'h51);
        check_register(16'h5485, 8'h65);
        check_register(16'h5486, 8'h71);
        check_register(16'h5487, 8'h7D);
        check_register(16'h5488, 8'h87);
        check_register(16'h5489, 8'h91);
        check_register(16'h548A, 8'h9A);
        check_register(16'h548B, 8'hAA);
        check_register(16'h548C, 8'hB8);
        check_register(16'h548D, 8'hCD);
        check_register(16'h548E, 8'hDD);
        check_register(16'h548F, 8'hEA);
        check_register(16'h5490, 8'h1D);
        check_register(16'h5583, 8'h50);
        check_register(16'h5584, 8'h50);
        check_register(16'h5586, 8'h30);
        check_register(16'h5587, 8'h10);
        check_register(16'h5588, 8'h41);
        check_register(16'h5580, 8'h06);
        $display("All saved picture registers verified before stream enable");
    end
endmodule
