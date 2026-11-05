// -----------------------------------------------------------------------------
// uart_tx -- 8N1 transmitter. Basys 3 routes this to the USB-UART bridge that
// shares the programming cable, so measurements land on the host as text.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module uart_tx #(
    parameter integer CLK_HZ = 100_000_000,
    parameter integer BAUD   = 115200
)(
    input  wire       clk,
    input  wire       rst,
    input  wire [7:0] data,
    input  wire       stb,      // pulse to send `data`
    output reg        tx,
    output wire       busy
);
    localparam integer DIV = CLK_HZ / BAUD;      // 868 @ 100 MHz / 115200

    reg [15:0] cnt  = 16'd0;
    reg [3:0]  bitn = 4'd0;
    reg [9:0]  sh   = 10'b1111111111;
    reg        act  = 1'b0;

    assign busy = act;
    initial tx = 1'b1;

    always @(posedge clk) begin
        if (rst) begin
            act <= 1'b0; tx <= 1'b1; cnt <= 0; bitn <= 0;
        end else if (!act) begin
            tx <= 1'b1;
            if (stb) begin
                sh   <= {1'b1, data, 1'b0};      // stop, data LSB first, start
                act  <= 1'b1;
                cnt  <= 0;
                bitn <= 0;
            end
        end else begin
            if (cnt == DIV-1) begin
                cnt <= 0;
                tx  <= sh[0];
                sh  <= {1'b1, sh[9:1]};
                if (bitn == 4'd9) act <= 1'b0;
                else bitn <= bitn + 4'd1;
            end else cnt <= cnt + 16'd1;
        end
    end
endmodule

`default_nettype wire
