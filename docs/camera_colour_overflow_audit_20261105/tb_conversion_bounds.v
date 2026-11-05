`timescale 1ns/1ps
module tb_conversion_bounds;
reg clk=0;always #5 clk=~clk;
reg rst=1,full=0;reg[7:0] y=0,u=128,v=128;
wire[7:0] r,g,b;wire valid;
ycbcr2rgb dut(.clk(clk),.rst(rst),.full_range(full),.y(y),.cb(u),.cr(v),.valid_i(1'b1),.r(r),.g(g),.b(b),.valid_o(valid));
integer vals[0:6];integer m,yy,ui,vi,n=0,er,eg,eb;real rr,gg,bb;
function integer clipped;input real value;begin
 if(value<=0.0)clipped=0;else if(value>=255.0)clipped=255;else clipped=$rtoi(value+0.5);
end endfunction
function integer absval;input integer x;begin absval=x<0?-x:x;end endfunction
initial begin
vals[0]=0;vals[1]=16;vals[2]=127;vals[3]=128;vals[4]=129;vals[5]=240;vals[6]=255;
repeat(3)@(negedge clk);rst=0;
for(m=0;m<2;m=m+1)for(yy=0;yy<256;yy=yy+1)for(ui=0;ui<7;ui=ui+1)for(vi=0;vi<7;vi=vi+1)begin
 @(negedge clk);full=m;y=yy;u=vals[ui];v=vals[vi];
 if(m==0)begin
 rr=1.16438356*(yy-16)+1.59602679*(vals[vi]-128);
 gg=1.16438356*(yy-16)-0.39176229*(vals[ui]-128)-0.81296765*(vals[vi]-128);
 bb=1.16438356*(yy-16)+2.01723214*(vals[ui]-128);
 end else begin
 rr=yy+1.402*(vals[vi]-128);
 gg=yy-0.344136*(vals[ui]-128)-0.714136*(vals[vi]-128);
 bb=yy+1.772*(vals[ui]-128);
 end
 er=clipped(rr);eg=clipped(gg);eb=clipped(bb);
 repeat(2)@(posedge clk);#1;
 if(!valid || absval(r-er)>2 || absval(g-eg)>2 || absval(b-eb)>2)
 $fatal(1,"FAIL mode=%0d Y=%0d Cb=%0d Cr=%0d got=%0d,%0d,%0d ref=%0d,%0d,%0d",m,yy,vals[ui],vals[vi],r,g,b,er,eg,eb);
 n=n+1;
end
$display("ALL TESTS PASS: %0d boundary/sweep vectors, two ranges; independent real-valued reference tolerance2",n);$finish;
end
initial begin #1000000;$fatal(1,"WATCHDOG");end
endmodule
