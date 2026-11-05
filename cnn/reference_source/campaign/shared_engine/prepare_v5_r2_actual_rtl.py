"""Unchanged final-trained generated RTL plus width-correct compact AXI harness.
Both128/256bit RAM models unit-tested before the actual full CNN runs.
"""
import hashlib,json,re,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
BUILD=Path.home()/'fpga_builds/g2_roi_v5_epoch08_output32_r2'
OUT=BUILD/'compact_v5_r2'

def main():
    if OUT.exists():raise RuntimeError('Existing final RTL harness preserved')
    report=json.loads((HERE/'V5_R2_RTL_INPUT_GATE.json').read_text())
    if report['status']!='complete' or not report['synthesis_passed'] or not report['cpp_passed']:raise RuntimeError('Actual V5 trained C++ and HLS gates required')
    for name,sha in report['kernel_program_sha256'].items():
        if hashlib.sha256((BUILD/name).read_bytes()).hexdigest()!=sha:raise RuntimeError('Compiled final source/program changed')
    OUT.mkdir();rtl=BUILD/'shared_engine_prj/solution1/syn/verilog';hashes={}
    for path in rtl.iterdir():
        if path.suffix in ['.v','.dat']:shutil.copy2(path,OUT/path.name);hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    ram=(HERE/'axi_ram.sv').read_text();ram=ram.replace('parameter INPUT_WORDS=0)(', 'parameter INPUT_WORDS=0,parameter DATA_BITS=128)(').replace('[127:0]','[DATA_BITS-1:0]').replace('[15:0]','[DATA_BITS/8-1:0]').replace('>>4','>>ADDR_SHIFT').replace('arsize>4','arsize>ADDR_SHIFT').replace('awsize>4','awsize>ADDR_SHIFT').replace('j<16','j<DATA_BITS/8');ram=ram.replace(' bit[DATA_BITS-1:0] mem',' localparam integer ADDR_SHIFT=$clog2(DATA_BITS/8);\n bit[DATA_BITS-1:0] mem')
    if 'ADDR_SHIFT=$clog2' not in ram or 'parameter DATA_BITS=128' not in ram:raise RuntimeError('Reviewed RAM template changed')
    (OUT/'axi_ram.sv').write_text(ram)
    unit=(HERE/'axi_ram_unit.sv').read_text();unit=unit.replace('module axi_ram_unit(input wire','module axi_ram_unit #(parameter DATA_BITS=128)(input wire').replace('[127:0]','[DATA_BITS-1:0]').replace('[15:0]','[DATA_BITS/8-1:0]').replace("16'hffff","{(DATA_BITS/8){1'b1}}").replace('wire arready','localparam integer ADDR_SHIFT=$clog2(DATA_BITS/8);\n wire arready').replace('.WORDS(8),.INPUT_WORDS(8)', '.WORDS(8),.INPUT_WORDS(8),.DATA_BITS(DATA_BITS)').replace("3'd4",'ADDR_SHIFT')
    old="wdata=128'h112233445566778899aabbccddeeff00+i;wstrb=(i==2)?16'hfff0:{(DATA_BITS/8){1'b1}};wlast=(i==3);wvalid=1;"
    new="for(integer b=0;b<DATA_BITS/8;b++)wdata[b*8+:8]=(b+17*(i+1));wstrb={(DATA_BITS/8){1'b1}};if(i==2)wstrb[3:0]=0;wlast=(i==3);wvalid=1;"
    if old not in unit:raise RuntimeError('Reviewed RAM unit stimulus changed')
    unit=unit.replace(old,new).replace('AXI_RAM_UNIT_PASS: burst,byte strobes,IDs,last,read/write stalls and held-data tested','AXI_RAM_UNIT_PASS width=%0d: burst,byte strobes,IDs,last,read/write stalls and held-data tested').replace('tested");','tested",DATA_BITS);');(OUT/'axi_ram_unit.sv').write_text(unit)
    program=json.loads((BUILD/'program.json').read_text());fw=program['feature_ddr_words'];cw=program['coefficient_ddr_words'];frame=(BUILD/'input_2.bin').read_bytes();feature=bytearray(fw*32);feature[:len(frame)]=frame
    for name,data,wordbytes in [('features.hex',feature,32),('coefficients.hex',(BUILD/'coefficients.bin').read_bytes(),16)]:
        (OUT/name).write_text('\n'.join(f'{int.from_bytes(data[i:i+wordbytes],"little"):0{wordbytes*2}x}' for i in range(0,len(data),wordbytes))+'\n')
    source=(rtl/'cnn_engine.v').read_text();params={name:int(v) for name,v in re.findall(r'parameter\s+(\w+)\s*=\s*(\d+);',source)};params.update(C_S_AXI_CONTROL_WSTRB_WIDTH=4,C_M_AXI_FEATURE_DDR_WSTRB_WIDTH=32,C_M_AXI_COEFFICIENT_DDR_WSTRB_WIDTH=16);ports=[]
    for direction,shape,name in re.findall(r'^(input|output)\s+(\[[^\]]+\])?\s*(\w+)\s*;',source,re.M):
        if shape:
            expr=shape[1:-1].split(':')[0]
            for key in sorted(params,key=len,reverse=True):expr=re.sub(r'\b'+key+r'\b',str(params[key]),expr)
            if re.search(r'[^\d\s+*/()\-]',expr):raise RuntimeError('Unknown actual port width '+expr)
            shape=f'[{int(eval(expr,{"__builtins__":{}},{}))+0}:0]'
        ports.append((direction,shape,name))
    if len(ports)<100:raise RuntimeError('Actual generated port parse incomplete')
    pcs=re.findall(r'reg\s+\[5:0\]\s+(pc_\w+);',source)
    if len(pcs)!=1:raise RuntimeError('Inspect actual progress hierarchy, expected unique6bitprogramcounter')
    tb='`timescale 1ns/1ps\nmodule tb;\n'
    for direction,shape,name in ports:tb+=('logic' if direction=='input' else 'wire')+' '+shape+' '+name+';\n'
    tb+='initial ap_clk=0;always #5 ap_clk=~ap_clk;\ncnn_engine dut('+','.join('.'+name+'('+name+')' for _,_,name in ports)+');\n'
    fields=['arvalid','arready','araddr','arlen','arsize','arburst','arid','rvalid','rready','rdata','rlast','rid','rresp','awvalid','awready','awaddr','awlen','awsize','awburst','awid','wvalid','wready','wdata','wstrb','wlast','bvalid','bready','bid','bresp']
    for label,words,file,readonly,inputwords,bits in [('feature',fw,'features.hex',0,len(frame)//32,256),('coefficient',cw,'coefficients.hex',1,0,128)]:
        prefix='m_axi_'+label+'_ddr_';connections=['.clk(ap_clk)','.resetn(ap_rst_n)']+['.'+field+'('+prefix+field.upper()+')' for field in fields];tb+=f'g2_axi_ram #(.WORDS({words}),.FILE("{file}"),.READ_ONLY({readonly}),.INPUT_WORDS({inputwords}),.DATA_BITS({bits})) {label}_ram('+','.join(connections)+');\nassign '+prefix+'RUSER=0;assign '+prefix+'BUSER=0;\n'
    tb+='wire done128,done256;axi_ram_unit #(.DATA_BITS(128)) u128(.clk(ap_clk),.resetn(ap_rst_n),.done(done128));axi_ram_unit #(.DATA_BITS(256)) u256(.clk(ap_clk),.resetn(ap_rst_n),.done(done256));\n'
    tb+='''longint unsigned cycles=0,start_cycle;
always @(posedge ap_clk)begin
 if(ap_rst_n)cycles<=cycles+1;
 if(cycles>0 && cycles%1000000==0)$display("CNN_RTL_PROGRESS cycles=%0d instruction=%0d feature_reads=%0d feature_writes=%0d coefficient_reads=%0d",cycles,dut.PROGRESS_PC,feature_ram.read_beats,feature_ram.write_beats,coefficient_ram.read_beats);
 if(cycles>100000000)$fatal(1,"Actual full CNN RTL cycle watchdog");
end
task automatic ctrl_write(input[5:0]addr,input[31:0]data);
 begin
  @(negedge ap_clk);s_axi_control_AWADDR=addr;s_axi_control_AWVALID=1;
  do @(posedge ap_clk);while(!s_axi_control_AWREADY);
  @(negedge ap_clk);s_axi_control_AWVALID=0;s_axi_control_WDATA=data;s_axi_control_WSTRB=4'hf;s_axi_control_WVALID=1;
  do @(posedge ap_clk);while(!s_axi_control_WREADY);
  @(negedge ap_clk);s_axi_control_WVALID=0;s_axi_control_BREADY=1;
  do @(posedge ap_clk);while(!s_axi_control_BVALID);
  if(s_axi_control_BRESP!=0)$fatal(1,"AXI-Lite control write failed");
  @(negedge ap_clk);s_axi_control_BREADY=0;
 end
endtask
integer fd;
initial begin
 ap_rst_n=0;
'''.replace('PROGRESS_PC',pcs[0])
    for direction,_,name in ports:
        if direction=='input' and name.startswith('s_axi_control_'):tb+=name+'=0;\n'
    tb+='''repeat(8)@(posedge ap_clk);@(negedge ap_clk);ap_rst_n=1;
 wait(done128 && done256);
 ctrl_write(6'h10,0);ctrl_write(6'h14,0);ctrl_write(6'h1c,0);ctrl_write(6'h20,0);
 ctrl_write(6'h04,1);ctrl_write(6'h08,1);ctrl_write(6'h00,1);
 start_cycle=cycles;$display("CNN_RTL_STARTED V5 epoch8 complete55instruction realTRAINframe");
 wait(interrupt===1'b1);repeat(4)@(posedge ap_clk);
 fd=$fopen("actual_rtl_results.bin","wb");if(fd==0)$fatal(1,"Cannot open actual RTL output");
'''
    for head in program['heads']:
        _,c,h,w=head['shape_bchw'];n=((c+7)//8)*h*w;offset=head['offset_words'];tb+=f'for(integer i=0;i<{n};i++)for(integer b=0;b<32;b++)$fwrite(fd,"%c",feature_ram.mem[{offset}+i][b*8+:8]);\n'
    tb+='''$fclose(fd);
 $display("FULL_CNN_RTL_DONE cycles=%0d feature_reads=%0d feature_writes=%0d coefficient_reads=%0d",cycles-start_cycle,feature_ram.read_beats,feature_ram.write_beats,coefficient_ram.read_beats);
 $finish;
end
endmodule
''';(OUT/'tb.sv').write_text(tb);project='\n'.join('verilog work "'+p.name+'"' for p in OUT.glob('*.v'))+'\n'+'\n'.join('sv work "'+name+'"' for name in ['axi_ram.sv','axi_ram_unit.sv','tb.sv'])+'\n';(OUT/'rtl.prj').write_text(project);(OUT/'run.tcl').write_text('run all\nquit\n')
    (OUT/'PROVENANCE.json').write_text(json.dumps({'scope':'ACTUAL V5epoch8generatedRTL byte-identical copy, complete55instructions, realTRAINinput/actualtrainedcoefficients. Independent128/256RAMunitgates. CompactAXIlatency/stalls NOT realMIG/board or routedtiming.','source_rtl':str(rtl),'rtl_sha256':hashes,'harness_sha256':{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ['axi_ram.sv','axi_ram_unit.sv','tb.sv']},'program_sha256':hashlib.sha256((BUILD/'program.h').read_bytes()).hexdigest(),'coefficients_sha256':hashlib.sha256((BUILD/'coefficients.bin').read_bytes()).hexdigest(),'input_sha256':hashlib.sha256(frame).hexdigest(),'feature_word_bits':256,'coefficient_word_bits':128,'clock_ns':10,'memory_model':'Oneoutstandingread/writeeachinterface,2cycleinitialreaddelay,ARstall7/AWstall11/Wstall5. IdealRAM withdeclaredstalls, no physicalDDRlatency/bandwidthclaim.'},indent=2));print(OUT)

if __name__=='__main__':main()
