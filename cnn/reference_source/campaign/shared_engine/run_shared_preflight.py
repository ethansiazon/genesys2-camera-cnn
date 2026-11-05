"""Independent full-program shared-engine checks; no PyTorch/GPU resident."""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
import ctypes,json,os,subprocess,time,traceback,xml.etree.ElementTree as ET
import numpy as np
from state import Memory,lock,save,status
REPORT=HERE/'PREFLIGHT.json'

def free():
    m=Memory();m.length=ctypes.sizeof(m);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m));return m.available/2**30

def run(stage,command,timeout=3600):
    path=HERE/(stage+'.log')
    if path.exists():raise RuntimeError('Preserve previous failed stage, do not silently retry:'+stage)
    if free()<3:raise RuntimeError('Need3GiB free to begin guarded compiler')
    status('Checking entire CNN on shared hardware engine',stage=stage)
    with path.open('w',encoding='utf-8') as log:
        env=dict(os.environ);env['PATH']=r'C:\msys64\ucrt64\bin;'+env['PATH']
        process=subprocess.Popen(command,cwd=HERE,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        save(HERE/'active.json',{'pid':process.pid,'stage':stage,'started_local':time.strftime('%Y-%m-%d %H:%M:%S')})
        start=last=time.monotonic()
        try:
            while process.poll() is None:
                time.sleep(2)
                if free()<1.5:raise RuntimeError('Own compiler stopped at1.5GiB RAM reserve')
                if time.monotonic()-start>timeout:raise RuntimeError('Bounded stage time exceeded; evidence preserved')
                if time.monotonic()-last>40:
                    status('Shared CNN engine check running',stage=stage,seconds=int(time.monotonic()-start),available_ram_gib=round(free(),2));last=time.monotonic()
            if process.returncode:raise RuntimeError(f'{stage} exited{process.returncode}; inspect{path}')
        except BaseException:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True);raise

def compare(path,program,expected):
    values=np.fromfile(path,np.int16);heads=program['heads'];length=sum(((h['shape_bchw'][1]+7)//8)*h['shape_bchw'][2]*h['shape_bchw'][3]*8 for h in heads)
    if values.size!=expected.shape[0]*length:raise RuntimeError('Unexpected complete-program output length')
    rows=[]
    for frame in values.reshape(-1,length):
        start=0;outputs=[]
        for head in heads:
            _,c,h,w=head['shape_bchw'];count=((c+7)//8)*h*w*8
            out=frame[start:start+count].reshape((c+7)//8,h,w,8).transpose(1,2,0,3).reshape(h,w,-1)[:,:,:c]
            outputs.append(out.reshape(-1).astype(float)/1024);start+=count
        rows.append(np.concatenate(outputs))
    error=np.abs(np.stack(rows)-expected)
    return {'passed':bool(error.max()==0),'max_abs_error':float(error.max()),'mean_abs_error':float(error.mean()),'frames':len(rows),'scope':'All raw heads of complete CNN program, compared with independent FX fixed-point reference; not detection accuracy.'}

def tcl(stage):
    text='open_project '+('-reset ' if stage=='synth' else '')+'shared_engine_prj\nset_top cnn_engine\n'
    text+='add_files cnn_engine.cpp -cflags "-std=c++14"\nadd_files -tb test_engine.cpp -cflags "-std=c++14 -DRTL_SIM"\n'
    for name in ['coefficients.bin','input_0.bin','input_1.bin','input_2.bin']:text+='add_files -tb '+name+'\n'
    text+='open_solution '+('-reset ' if stage=='synth' else '')+'solution1 -flow_target vivado\nset_part {xc7k325tffg900-2}\ncreate_clock -period10 -name default\nconfig_compile -pipeline_loops0\n'
    # Explicit spaces: avoid relying on Tcl option token concatenation.
    text=text.replace('-period10','-period 10').replace('-pipeline_loops0','-pipeline_loops 0')
    text+=('csynth_design\n' if stage=='synth' else 'cosim_design -rtl verilog -tool xsim -trace_level none\n')+'exit\n'
    path=HERE/(stage+'.tcl');path.write_text(text);return path.name

def main():
    if REPORT.exists():raise RuntimeError('Previous report exists; inspect before changed retry')
    program=json.loads((HERE/'program.json').read_text());expected=np.load(ROOT/'trial03_hardware_expected.npy')
    result={'status':'running','scope':'Full55instruction initialized CNN, single128multiplier tiled engine and complete on-FPGA sequencer. All coefficients/intermediates reside in external DDR; reported engine must be combined with actual MIG/camera/interconnect/decode. No trained accuracy/routed/board or throughput claim.','complete_cpp_passed':False,'synthesis_passed':False,'rtl_passed':False}
    save(REPORT,result)
    try:
        run('host_compile',[r'C:\msys64\ucrt64\bin\g++.exe','-std=c++14','-O2',r'-IC:\AMDDesignTools\2026.1\Vitis\include','cnn_engine.cpp','test_engine.cpp','-o','test_engine.exe'],300)
        run('complete_cpp',[str(HERE/'test_engine.exe')],1800)
        result['complete_cpp']=compare(HERE/'engine_results.bin',program,expected);result['complete_cpp_passed']=result['complete_cpp']['passed'];save(REPORT,result)
        if not result['complete_cpp_passed']:raise RuntimeError('Shared full CNN differs numerically; diagnose before synthesis')
        status('Complete shared-engine CNN numerical check passed',**result['complete_cpp'])
        cmd=[r'C:\AMDDesignTools\2026.1\Vitis\bin\vitis-run.bat','--tcl',tcl('synth'),'--mode','hls'];run('synth',cmd)
        tree=ET.parse(HERE/'shared_engine_prj/solution1/syn/report/cnn_engine_csynth.xml')
        resources={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/Resources')};limits={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/AvailableResources')}
        fractions={k:v/limits[k] for k,v in resources.items() if limits.get(k,0)>0};caps={'LUT':.60,'DSP':.60,'FF':.60,'BRAM_18K':.60}
        fits=all(fractions.get(k,0)<=v for k,v in caps.items())
        result.update(synthesis_passed=True,resources=resources,device_limits=limits,resource_fractions=fractions,engine_reserve_caps=caps,meets_engine_reserve=fits,
            feature_ddr_bytes=program['feature_ddr_bytes'],coefficient_ddr_bytes=program['coefficient_ddr_bytes'],estimated_clock_period_ns=tree.findtext('.//EstimatedClockPeriod'))
        save(REPORT,result)
        if not fits:raise RuntimeError('Shared complete CNN engine too large for reserved system margin')
        status('Shared complete CNN synthesis report saved',resources=resources,still_requires_mig_camera_and_rtl=True)
        run('cosim',[r'C:\AMDDesignTools\2026.1\Vitis\bin\vitis-run.bat','--tcl',tcl('cosim'),'--mode','hls'],3600)
        report=(HERE/'shared_engine_prj/solution1/sim/report/cnn_engine_cosim.rpt').read_text()
        if 'Pass' not in report:raise RuntimeError('RTL cosimulation did not pass')
        outputs=list((HERE/'shared_engine_prj/solution1/sim').rglob('engine_results.bin'))
        if len(outputs)!=1:raise RuntimeError('Need unique actual RTL numeric file, found'+str(len(outputs)))
        result['rtl']=compare(outputs[0],program,expected[2:3]);result['rtl_passed']=result['rtl']['passed']
        if not result['rtl_passed']:raise RuntimeError('Full-program RTL output differs from fixed-point reference')
        result.update(status='complete',completed_local=time.strftime('%Y-%m-%d %H:%M:%S'));save(REPORT,result)
        status('Complete CNN shared-engine preflight finished',resources=resources,board_fit_proved=False)
    except BaseException as exc:
        result.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,result)
        status('Shared engine result saved for inspection',error=str(exc));raise

if __name__=='__main__':
    with lock():main()
