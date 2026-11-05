"""Test UNCHANGED generated full-CNN RTL without the large UVM byte-queue harness.
Custom memory model has its own burst/strobe/backpressure unit gate.
"""
import hashlib,json,re,shutil
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_live_r2'
OUT=BUILD/'compact_rtl_test'

def main():
    if OUT.exists():raise RuntimeError('Existing custom RTL evidence preserved')
    OUT.mkdir();rtl=BUILD/'shared_engine_prj/solution1/syn/verilog';hashes={}
    for source in rtl.iterdir():
        if source.suffix in ['.v','.dat']:
            shutil.copy2(source,OUT/source.name);hashes[source.name]=hashlib.sha256(source.read_bytes()).hexdigest()
    for name in ['axi_ram.sv','axi_ram_unit.sv']:shutil.copy2(HERE/name,OUT/name)
    program=json.loads((BUILD/'program.json').read_text());fw=program['feature_ddr_words'];cw=program['coefficient_ddr_words']
    feature=bytearray(fw*16);frame=(BUILD/'input_2.bin').read_bytes();feature[:len(frame)]=frame
    for name,data in [('features.hex',feature),('coefficients.hex',(BUILD/'coefficients.bin').read_bytes())]:
        (OUT/name).write_text('\n'.join(f'{int.from_bytes(data[i:i+16],"little"):032x}' for i in range(0,len(data),16))+'\n')
    source=(rtl/'cnn_engine.v').read_text();params={name:int(v) for name,v in re.findall(r'parameter\s+(\w+)\s*=\s*(\d+);',source)}
    params.update(C_S_AXI_CONTROL_WSTRB_WIDTH=4,C_M_AXI_FEATURE_DDR_WSTRB_WIDTH=16,C_M_AXI_COEFFICIENT_DDR_WSTRB_WIDTH=16)
    ports=[]
    for direction,shape,name in re.findall(r'^(input|output)\s+(\[[^\]]+\])?\s*(\w+)\s*;',source,re.M):
        if shape:
            expr=shape[1:-1].split(':')[0]
            for key in sorted(params,key=len,reverse=True):expr=re.sub(r'\b'+key+r'\b',str(params[key]),expr)
            if re.search(r'[^\d\s+*/()\-]',expr):raise RuntimeError('Unknown generated port width '+expr)
            width=int(eval(expr,{'__builtins__':{}},{}))+1;shape=f'[{width-1}:0]'
        ports.append((direction,shape,name))
    if len(ports)<100:raise RuntimeError('Generated port parse incomplete')
    tb='`timescale 1ns/1ps\nmodule tb;\n'
    for direction,shape,name in ports:tb+=('logic' if direction=='input' else 'wire')+' '+shape+' '+name+';\n'
    tb+='initial ap_clk=0;always #10 ap_clk=~ap_clk;\n'
    tb+='cnn_engine dut('+','.join('.'+name+'('+name+')' for _,_,name in ports)+');\n'
    fields=['arvalid','arready','araddr','arlen','arsize','arburst','arid','rvalid','rready','rdata','rlast','rid','rresp','awvalid','awready','awaddr','awlen','awsize','awburst','awid','wvalid','wready','wdata','wstrb','wlast','bvalid','bready','bid','bresp']
    for label,count,file,readonly,inputwords in [('feature',fw,'features.hex',0,len(frame)//16),('coefficient',cw,'coefficients.hex',1,0)]:
        prefix='m_axi_'+label+'_ddr_';connections=['.clk(ap_clk)','.resetn(ap_rst_n)']+['.'+f+'('+prefix+f.upper()+')' for f in fields]
        tb+=f'g2_axi_ram #(.WORDS({count}),.FILE("{file}"),.READ_ONLY({readonly}),.INPUT_WORDS({inputwords})) '+label+'_ram('+','.join(connections)+');\n'
        tb+='assign '+prefix+'RUSER=0;assign '+prefix+'BUSER=0;\n'
    tb+='wire unit_done;axi_ram_unit unit_test(.clk(ap_clk),.resetn(ap_rst_n),.done(unit_done));\n'
    tb+='''longint unsigned cycles=0,start_cycle;
always @(posedge ap_clk)begin
 if(ap_rst_n)cycles<=cycles+1;
 if(cycles>0 && cycles%1000000==0)$display("CNN_RTL_PROGRESS cycles=%0d instruction=%0d feature_reads=%0d feature_writes=%0d coefficient_reads=%0d",cycles,dut.pc_fu_120,feature_ram.read_beats,feature_ram.write_beats,coefficient_ram.read_beats);
 if(cycles>100000000)$fatal(1,"Full CNN RTL cycle watchdog");
end
task automatic ctrl_write(input[5:0]addr,input[31:0]data);
 begin
  @(negedge ap_clk);s_axi_control_AWADDR=addr;s_axi_control_AWVALID=1;
  do @(posedge ap_clk);while(!s_axi_control_AWREADY);
  @(negedge ap_clk);s_axi_control_AWVALID=0;s_axi_control_WDATA=data;s_axi_control_WSTRB=4'hf;s_axi_control_WVALID=1;
  do @(posedge ap_clk);while(!s_axi_control_WREADY);
  @(negedge ap_clk);s_axi_control_WVALID=0;s_axi_control_BREADY=1;
  do @(posedge ap_clk);while(!s_axi_control_BVALID);
  if(s_axi_control_BRESP!=0)$fatal(1,"Control write failed");
  @(negedge ap_clk);s_axi_control_BREADY=0;
 end
endtask
integer fd;
initial begin
 ap_rst_n=0;
'''
    for direction,_,name in ports:
        if direction=='input' and name.startswith('s_axi_control_'):tb+=name+'=0;\n'
    tb+='''repeat(8)@(posedge ap_clk);@(negedge ap_clk);ap_rst_n=1;
 wait(unit_done);
 ctrl_write(6'h10,0);ctrl_write(6'h14,0);ctrl_write(6'h1c,0);ctrl_write(6'h20,0);
 ctrl_write(6'h04,1);ctrl_write(6'h08,1);ctrl_write(6'h00,1);
 start_cycle=cycles;$display("CNN_RTL_STARTED complete55instruction realTRAINframe");
 wait(interrupt===1'b1);repeat(4)@(posedge ap_clk);
 fd=$fopen("actual_rtl_results.bin","wb");if(fd==0)$fatal(1,"Cannot open RTL result");
'''
    for head in program['heads']:
        _,c,h,w=head['shape_bchw'];count=((c+7)//8)*h*w;off=head['offset_words']
        tb+=f'for(integer i=0;i<{count};i++)for(integer b=0;b<16;b++)$fwrite(fd,"%c",feature_ram.mem[{off}+i][b*8+:8]);\n'
    tb+='''$fclose(fd);
 $display("FULL_CNN_RTL_DONE cycles=%0d feature_reads=%0d feature_writes=%0d coefficient_reads=%0d",cycles-start_cycle,feature_ram.read_beats,feature_ram.write_beats,coefficient_ram.read_beats);
 $finish;
end
endmodule
'''
    if 'reg   [5:0] pc_fu_120;' not in source:raise RuntimeError('Progress counter hierarchy changed; inspect before simulation')
    (OUT/'tb.sv').write_text(tb)
    files=[p.name for p in OUT.glob('*.v')];project='\n'.join('verilog work "'+n+'"' for n in files)+'\n'+'\n'.join('sv work "'+n+'"' for n in ['axi_ram.sv','axi_ram_unit.sv','tb.sv'])+'\n'
    (OUT/'rtl.prj').write_text(project);(OUT/'run.tcl').write_text('run all\nquit\n')
    (OUT/'PROVENANCE.json').write_text(json.dumps({'scope':'Simulation-only compact AXI RAM harness. Synthesized CNN RTL copied byte-for-byte from prior full-controller HLS build. Not board/MIG simulation, no routed timing. Deterministic legal AXI stalls, byte strobes,IDs and burst assertions; unit gate before actualCNN.',
        'source_rtl':str(rtl),'rtl_sha256':hashes,'complete_program_instructions':len(program['instructions']),'full_real_train_input_sha256':hashlib.sha256(frame).hexdigest(),'feature_words':fw,'coefficient_words':cw,
        'clock_ns':20,'ddr_model':'One outstanding read/write per interface,2cycleinitial read delay, ARstall every7cycles,AWstall11,Wstall5. Ideal compact RAM under those test constraints; not physicalDDRbandwidth.'},indent=2))
    print(OUT)

if __name__=='__main__':main()
