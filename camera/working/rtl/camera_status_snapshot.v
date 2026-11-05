`timescale 1ns/1ps
`default_nettype none
// Bundled-data request/acknowledge crossing. The source holds an entire snapshot
// stable until the next request. No independently synchronized multi-bit counter.
module camera_status_snapshot #(parameter integer WIDTH=160)(
    input wire src_clk,src_rst,
    input wire [WIDTH-1:0] src_data,
    input wire dst_clk,dst_rst,request,
    output reg [WIDTH-1:0] dst_data=0
);
    reg req_toggle=0, ack_toggle=0;
    (* ASYNC_REG="TRUE" *) reg [1:0] req_sync=0,ack_sync=0;
    reg [WIDTH-1:0] held=0;
    reg waiting=0;
    always @(posedge src_clk) begin
        if(src_rst) begin req_sync<=0; ack_toggle<=0; held<=0; end
        else begin
            req_sync<={req_sync[0],req_toggle};
            if(req_sync[1]!=ack_toggle) begin
                held<=src_data;
                ack_toggle<=req_sync[1];
            end
        end
    end
    always @(posedge dst_clk) begin
        if(dst_rst) begin
            req_toggle<=0;ack_sync<=0;waiting<=0;dst_data<=0;
        end else begin
            ack_sync<={ack_sync[0],ack_toggle};
            if(request && !waiting) begin req_toggle<=~req_toggle;waiting<=1;end
            if(waiting && ack_sync[1]==req_toggle) begin
                dst_data<=held;waiting<=0;
            end
        end
    end
endmodule
`default_nettype wire
