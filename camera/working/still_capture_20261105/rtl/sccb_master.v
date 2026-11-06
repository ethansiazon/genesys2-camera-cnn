// Registered SCCB master: 16-bit address, 8-bit data, 0x3c sensor.
// Every wire transition is registered; SDA changes only while SCL is low,
// except explicit START/STOP. Read uses STOP then a fresh START.
`timescale 1ns/1ps
`default_nettype none
module sccb_master #(parameter integer CLK_HZ=25000000,SCL_HZ=100000)(
 input wire clk,rst,start,rw,input wire[15:0]reg_addr,input wire[7:0]wr_data,
 output reg[7:0]rd_data,output reg busy,done,nack,
 output reg scl_low,sda_low,input wire sda_in);
 localparam integer DIV=CLK_HZ/(4*SCL_HZ);
 localparam IDLE=0,START=1,SEND=2,ACK=3,RECEIVE=4,NACK=5,STOP=6;
 reg[2:0]state=IDLE;
 reg[1:0]phase=0;
 reg[31:0]counter=0;
 reg[2:0]bit_index=0;
 reg[1:0]byte_index=0;
 reg read_request=0,read_started=0;
 reg[15:0]address=0;
 reg[7:0]write_value=0;
 reg[7:0]txbyte;
 always @* case(byte_index)
  0:txbyte=8'h78;
  1:txbyte=address[15:8];
  2:txbyte=address[7:0];
  default:txbyte=read_request ? 8'h79 : write_value;
 endcase
 always @(posedge clk) begin
  done<=0;
  if(rst)begin
   state<=IDLE;busy<=0;phase<=0;counter<=0;bit_index<=0;byte_index<=0;
   read_request<=0;read_started<=0;address<=0;write_value<=0;
   rd_data<=0;nack<=0;scl_low<=0;sda_low<=0;
  end else if(state==IDLE)begin
   scl_low<=0;sda_low<=0;counter<=0;phase<=0;
   if(start)begin
    busy<=1;nack<=0;rd_data<=0;read_request<=rw;address<=reg_addr;
    write_value<=wr_data;read_started<=0;byte_index<=0;bit_index<=0;state<=START;
   end
  end else if(counter==DIV-1)begin
   counter<=0;phase<=phase+1'b1;
   case(state)
    START:case(phase)
     0:begin scl_low<=0;sda_low<=1;end
     1:scl_low<=1;
     3:begin state<=SEND;bit_index<=0;end
    endcase
    SEND:case(phase)
     0:begin scl_low<=1;sda_low<=~txbyte[7-bit_index];end
     2:scl_low<=0;
     3:begin scl_low<=1;if(bit_index==7)state<=ACK;else bit_index<=bit_index+1'b1;end
    endcase
    ACK:case(phase)
     0:begin scl_low<=1;sda_low<=0;end
     2:scl_low<=0;
     3:begin
      scl_low<=1;if(sda_in)nack<=1;
      if(read_request && read_started)begin bit_index<=0;state<=RECEIVE;end
      else if((!read_request && byte_index==3)||(read_request && byte_index==2))state<=STOP;
      else begin byte_index<=byte_index+1'b1;bit_index<=0;state<=SEND;end
     end
    endcase
    RECEIVE:case(phase)
     0:begin scl_low<=1;sda_low<=0;end
     2:scl_low<=0;
     3:begin
      scl_low<=1;rd_data<={rd_data[6:0],sda_in};
      if(bit_index==7)state<=NACK;else bit_index<=bit_index+1'b1;
     end
    endcase
    NACK:case(phase)
     0:begin scl_low<=1;sda_low<=0;end
     2:scl_low<=0;
     3:begin scl_low<=1;state<=STOP;end
    endcase
    STOP:case(phase)
     0:begin scl_low<=1;sda_low<=1;end
     1:scl_low<=0;
     2:sda_low<=0;
     3:begin
      if(read_request && !read_started)begin
       read_started<=1;byte_index<=3;bit_index<=0;state<=START;
      end else begin state<=IDLE;busy<=0;done<=1;end
     end
    endcase
    default:state<=IDLE;
   endcase
  end else counter<=counter+1'b1;
 end
endmodule
`default_nettype wire
