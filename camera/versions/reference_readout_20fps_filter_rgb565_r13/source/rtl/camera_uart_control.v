`timescale 1ns/1ps
`default_nettype none
// One request at a time. Frame: A5 5A seq op addr_hi addr_lo data xor(all 7).
// Ops: 50 ping, 52 read, 57 write+readback. Response is one uart_report packet:
// D1650001 seq op status addr requested readback 4C495645.
// Status: 0 OK, 1 format, 2 denied, 3 recording, 4 NACK, 5 timeout,
//         6 UART framing, 7 readback mismatch. No automatic retries.
module camera_uart_control #(
 parameter integer CLK_HZ=200000000,
 parameter integer FRAME_TIMEOUT=CLK_HZ/20,
 parameter integer OP_TIMEOUT=CLK_HZ*2
)(
 input wire clk,rst,input wire[7:0]rx_data,input wire rx_valid,rx_error,blocked,
 output wire cfg_valid,cfg_rw,output wire[15:0]cfg_addr,output wire[7:0]cfg_wdata,
 input wire cfg_ready,cfg_done,input wire[7:0]cfg_rdata,input wire cfg_nack,
 output reg reply_valid,output reg[255:0]reply_words,input wire reply_take
);
 localparam RECEIVE=0,ISSUE=1,WAIT_RESULT=2,REPLY=3;
 reg[1:0]state=0;reg[2:0]index=0;
 reg[7:0]seq=0,op=0,write_data=0,checksum=0;
 reg[15:0]address=0;reg verify=0;reg[31:0]age=0;
 assign cfg_valid=state==ISSUE && (!blocked || verify);
 assign cfg_rw=op==8'h52 || verify;
 assign cfg_addr=address;assign cfg_wdata=write_data;

 function write_allowed;
  input[15:0]a; input[7:0]v;
  begin
   write_allowed=((a>=16'h3400 && a<=16'h3406) ||
    (a>=16'h3500 && a<=16'h3503) || a==16'h350a || a==16'h350b ||
    a==16'h5000 || a==16'h5001 || a==16'h5005 ||
    (a>=16'h5180 && a<=16'h5197) || a==16'h519e ||
    (a>=16'h5380 && a<=16'h538b) ||
    (a>=16'h5480 && a<=16'h5490) ||
    (a>=16'h5580 && a<=16'h558c));
   if((a==16'h3400 || a==16'h3402 || a==16'h3404 || a==16'h3500) && v[7:4]!=0)
    write_allowed=0;
   if(a==16'h3406 && v>1)write_allowed=0;
   if(a==16'h3502 && v[3:0]!=0)write_allowed=0;
   if((a==16'h3503 || a==16'h350a) && v>3)write_allowed=0;
  end
 endfunction
 task respond;
  input[7:0]status,value;
  begin
   reply_words<={32'h4c495645,{24'd0,value},{24'd0,write_data},
    {16'd0,address},{24'd0,status},{24'd0,op},{24'd0,seq},32'hd1650001};
   reply_valid<=1;state<=REPLY;index<=0;age<=0;
  end
 endtask

 always @(posedge clk)begin
  if(rst)begin
   state<=RECEIVE;index<=0;seq<=0;op<=0;address<=0;write_data<=0;
   checksum<=0;verify<=0;age<=0;reply_valid<=0;reply_words<=0;
  end else case(state)
   RECEIVE:begin
    if(rx_error)respond(6,0);
    else if(rx_valid)begin
     age<=0;
     case(index)
      0:if(rx_data==8'ha5)begin index<=1;checksum<=8'ha5;seq<=0;op<=0;address<=0;write_data<=0;end
      1:if(rx_data==8'h5a)begin index<=2;checksum<=checksum^rx_data;end
        else if(rx_data==8'ha5)begin index<=1;checksum<=8'ha5;end
        else index<=0;
      2:begin seq<=rx_data;checksum<=checksum^rx_data;index<=3;end
      3:begin op<=rx_data;checksum<=checksum^rx_data;index<=4;end
      4:begin address[15:8]<=rx_data;checksum<=checksum^rx_data;index<=5;end
      5:begin address[7:0]<=rx_data;checksum<=checksum^rx_data;index<=6;end
      6:begin write_data<=rx_data;checksum<=checksum^rx_data;index<=7;end
      7:begin
       index<=0;verify<=0;
       if(rx_data!=checksum || (op!=8'h50 && op!=8'h52 && op!=8'h57))respond(1,0);
       else if(blocked)respond(3,0);
       else if(op==8'h50)respond(0,0);
       else if(op==8'h57 && !write_allowed(address,write_data))respond(2,0);
       else begin age<=0;state<=ISSUE;end
      end
     endcase
    end else if(index!=0)begin
     if(age>=FRAME_TIMEOUT-1)respond(1,0);else age<=age+1'b1;
    end
   end
   ISSUE:begin
    if(blocked && !verify)respond(3,0);
    else if(cfg_ready)begin state<=WAIT_RESULT;age<=0;end
    else if(age>=OP_TIMEOUT-1)respond(5,0);
    else age<=age+1'b1;
   end
   WAIT_RESULT:begin
    if(cfg_done)begin
     if(cfg_nack)respond(4,cfg_rdata);
     else if(op==8'h57 && !verify)begin verify<=1;state<=ISSUE;age<=0;end
     else if(op==8'h57 && cfg_rdata!=write_data)respond(7,cfg_rdata);
     else respond(0,cfg_rdata);
    end else if(age>=OP_TIMEOUT-1)respond(5,0);
    else age<=age+1'b1;
   end
   REPLY:if(reply_take)begin reply_valid<=0;state<=RECEIVE;index<=0;age<=0;end
   default:state<=RECEIVE;
  endcase
 end
endmodule
`default_nettype wire
