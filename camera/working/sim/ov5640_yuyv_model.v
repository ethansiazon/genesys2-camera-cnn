// YUYV fixture derived from the supplied SCCB model.
`timescale 1ns / 1ps
`default_nettype none

module ov5640_yuyv_model #(
    parameter integer H_ACTIVE          = 320,
    parameter integer V_ACTIVE          = 240,
    parameter integer H_BLANK_PCLK      = 40,     // pclk cycles between lines
    parameter integer V_BLANK_LINES     = 8,
    parameter integer PCLK_PERIOD       = 40,     // ns  -> 25 MHz
    parameter integer VSYNC_ACTIVE_HIGH = 1,
    parameter integer EXTRA_COLS        = 0,
    parameter integer EXTRA_ROWS        = 0,
    parameter integer NACK_AT           = 0,      // 0 = never nack
    parameter integer G_FROM_X          = 0       // 1 = green varies along a line
)(
    output wire      pclk,
    output wire      vsync,
    output wire      href,
    output reg [7:0] d,
    input  wire      pwdn,
    input  wire      reset_n,
    input  wire      sioc,
    inout  wire      siod,
    output reg [31:0] frames_sent
);
    // ---------------- register file + SCCB slave ----------------
    reg [7:0] regs [0:65535];
    integer   i;
    reg [15:0] last_addr = 16'h0000;
    integer   xfer_count = 0;
    reg        sda_drv   = 1'b0;      // 1 = pull low
    assign siod = sda_drv ? 1'b0 : 1'bz;

    initial begin
        for (i = 0; i < 65536; i = i + 1) regs[i] = 8'h00;
        regs[16'h300A] = 8'h56;       // chip id high
        regs[16'h300B] = 8'h40;       // chip id low
    end

    // start / stop detection + byte engine.
    // nbit counts SCL RISING edges: 1..8 are data bits, 9 is the ack slot.
    // The slave drives on the falling edge; the master samples on the rising
    // edge. Getting this wrong is why the first version silently returned 0xFF
    // on reads -- it set `sending` and nbit=9 together, so the send branch ran
    // at nbit=9 and skipped all eight data bits.
    reg        in_xfer = 1'b0;
    reg        sending = 1'b0;
    reg [3:0]  nbit    = 4'd0;
    reg [7:0]  shin    = 8'h00;
    reg [7:0]  sendb   = 8'h00;
    integer    bytei   = 0;

    always @(negedge siod) if (sioc === 1'b1) begin            // START
        in_xfer <= 1'b1; nbit <= 0; bytei <= 0;
        sending <= 1'b0; sda_drv <= 1'b0;
        xfer_count = xfer_count + 1;
    end

    always @(posedge siod) if (sioc === 1'b1) begin            // STOP
        in_xfer <= 1'b0; sending <= 1'b0; sda_drv <= 1'b0; nbit <= 0;
    end

    always @(posedge sioc) if (in_xfer) begin
        if (!sending && nbit < 8) shin <= {shin[6:0], siod};
        nbit <= nbit + 4'd1;
    end

    always @(negedge sioc) if (in_xfer) begin
        if (sending) begin
            if (nbit < 8) begin
                sda_drv <= ~sendb[3'd7 - nbit[2:0]];
            end else begin
                sda_drv <= 1'b0; sending <= 1'b0; nbit <= 0;   // master NACKs
            end
        end else if (nbit == 4'd8) begin
            // byte complete -> ack, unless a NACK is being injected
            sda_drv <= (NACK_AT != 0 && xfer_count == NACK_AT) ? 1'b0 : 1'b1;
        end else if (nbit == 4'd9) begin
            sda_drv <= 1'b0;
            nbit    <= 0;
            case (bytei)
                0: if (shin == 8'h79) begin                    // read transaction
                       sendb   <= regs[last_addr];
                       sending <= 1'b1;
                       sda_drv <= ~regs[last_addr][7];         // drive bit 7 now
                   end
                1: last_addr[15:8] <= shin;
                2: last_addr[7:0]  <= shin;
                3: regs[last_addr] <= shin;
            endcase
            bytei <= bytei + 1;
        end
    end

    // ---------------- pixel stream ----------------
    localparam integer HTOT = H_ACTIVE + EXTRA_COLS;
    localparam integer VTOT = V_ACTIVE + EXTRA_ROWS;

    function [15:0] test_rgb565; input integer xx,yy;
        begin
            case(xx%8)
             0:test_rgb565=16'hF800; 1:test_rgb565=16'h07E0;
             2:test_rgb565=16'h001F; 3:test_rgb565=16'hFFFF;
             4:test_rgb565=16'h0000; 5:test_rgb565=16'hFFE0;
             6:test_rgb565=16'h07FF; 7:test_rgb565=16'hF81F;
            endcase
            if(yy%2) test_rgb565=(xx*109+811)&65535;
        end
    endfunction
    reg [15:0] rgbword;
    integer x, y, k;
    reg [4:0] R; reg [5:0] G; reg [4:0] B;

    reg pclk_gen,href_gen,vsync_gen;
    // Hardware VSYNC polarity bit is inverted relative to early datasheet.
    assign pclk = regs[16'h4740][5] ? pclk_gen : ~pclk_gen;
    assign href = regs[16'h4740][1] ? href_gen : ~href_gen;
    assign vsync = regs[16'h4740][0] ? ~vsync_gen : vsync_gen;
    initial begin
        pclk_gen = 1'b0; vsync_gen = VSYNC_ACTIVE_HIGH ? 1'b0 : 1'b1;
        href_gen = 1'b0; d = 8'h00; frames_sent = 32'd0;
    end

    always #(PCLK_PERIOD/2) pclk_gen = ~pclk_gen;

    task emit_byte(input [7:0] v);
        begin @(negedge pclk_gen); d = v; href_gen = 1'b1; end
    endtask

    initial begin
        forever begin
            wait (reset_n === 1'b1 && pwdn === 1'b0);
            // vertical sync pulse
            @(negedge pclk_gen); href_gen = 1'b0;
            vsync_gen = VSYNC_ACTIVE_HIGH ? 1'b1 : 1'b0;
            repeat (40) @(negedge pclk_gen);     // real VSYNC lasts many line times
            vsync_gen = VSYNC_ACTIVE_HIGH ? 1'b0 : 1'b1;
            repeat (40) @(negedge pclk_gen);

            for (y = 0; y < VTOT; y = y + 1) begin
                for (x = 0; x < HTOT; x = x + 1) begin
                    if(regs[16'h501f]==1 && regs[16'h4300]==8'h61) begin
                        rgbword=test_rgb565(x,y);
                        emit_byte(rgbword[15:8]);emit_byte(rgbword[7:0]);
                    end else begin
                        emit_byte(8'd16 + ((x+y)%200));emit_byte(8'd128);
                        emit_byte(8'd16 + ((x+y+1)%200));emit_byte(8'd128);
                        x = x + 1;
                    end
                end
                @(negedge pclk_gen); href_gen = 1'b0; d = 8'h00;
                repeat (H_BLANK_PCLK) @(negedge pclk_gen);
            end
            repeat (V_BLANK_LINES * 8) @(negedge pclk_gen);
            frames_sent = frames_sent + 1;
        end
    end
endmodule

`default_nettype wire
