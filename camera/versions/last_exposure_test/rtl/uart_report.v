// -----------------------------------------------------------------------------
// uart_report -- emits 8 x 32-bit values as space-separated hex, once a second.
// Fixed field order, decoded on the host. No labels on the wire: keeps the
// formatter trivial and the line short.
// -----------------------------------------------------------------------------
`timescale 1ns / 1ps
`default_nettype none

module uart_report (
    input  wire         clk,
    input  wire         rst,
    input  wire         go,            // 1-cycle pulse: latch and send
    input  wire [255:0] words,         // 8 x 32-bit, word 0 in the LSBs
    output reg  [7:0]   tx_data,
    output reg          tx_stb,
    input  wire         tx_busy,
    output wire busy
);
    reg [255:0] lat  = 256'd0;
    reg [2:0]   widx = 3'd0;
    reg [3:0]   nib  = 4'd0;
    reg [1:0]   st   = 2'd0;           // 0 idle, 1 nibbles, 2 sep, 3 crlf
    reg         crlf2 = 1'b0;

    assign busy = (st != 0);
    wire [31:0] cur = lat[widx*32 +: 32];
    wire [3:0]  nv  = cur[(4'd7 - nib)*4 +: 4];
    wire [7:0]  hex = (nv < 4'd10) ? (8'h30 + nv) : (8'h41 + nv - 4'd10);

    always @(posedge clk) begin
        tx_stb <= 1'b0;
        if (rst) begin
            st <= 2'd0; widx <= 0; nib <= 0; crlf2 <= 0;
        end else case (st)
            2'd0: if (go) begin
                      lat <= words; widx <= 0; nib <= 0; st <= 2'd1;
                  end
            2'd1: if (!tx_busy && !tx_stb) begin
                      tx_data <= hex; tx_stb <= 1'b1;
                      if (nib == 4'd7) begin nib <= 0; st <= 2'd2; end
                      else nib <= nib + 4'd1;
                  end
            2'd2: if (!tx_busy && !tx_stb) begin
                      if (widx == 3'd7) begin
                          tx_data <= 8'h0D; tx_stb <= 1'b1; crlf2 <= 1'b0; st <= 2'd3;
                      end else begin
                          tx_data <= 8'h20; tx_stb <= 1'b1;   // space
                          widx <= widx + 3'd1; st <= 2'd1;
                      end
                  end
            2'd3: if (!tx_busy && !tx_stb) begin
                      if (!crlf2) begin tx_data <= 8'h0A; tx_stb <= 1'b1; crlf2 <= 1'b1; end
                      else st <= 2'd0;
                  end
        endcase
    end
endmodule

`default_nettype wire
