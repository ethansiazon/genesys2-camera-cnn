"""Guarded actual full FINAL-trained RTL simulation, width-correct RAM harness."""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
import ctypes,hashlib,json,os,re,subprocess,time,traceback
import numpy as np
from state import Memory,lock,save,status
BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_wide_r2_live';OUT=BUILD/'compact_final_rtl_r1';REPORT=HERE/'FINAL_ROI11_ACTUAL_RTL.json'

def free():
    m=Memory();m.length=ctypes.sizeof(m);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m));return m.available/2**30

def run(label,args,limit):
    path=OUT/(label+'.log')
    if path.exists():raise RuntimeError('Prior actual stage preserved; no identical retry')
    if free()<3:raise RuntimeError('Need3GiB free before owned simulator stage')
    status('Checking FINAL trained complete CNN generated RTL',stage=label)
    with path.open('w',encoding='utf-8') as log:
        child=subprocess.Popen(args,cwd=OUT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP);save(HERE/'final_roi11_rtl_active.json',{'pid':child.pid,'stage':label});start=last=time.monotonic()
        try:
            while child.poll() is None:
                time.sleep(2)
                if free()<1.5:raise RuntimeError('Stopped own RTL process at1.5GiB reserve')
                if time.monotonic()-start>limit:raise RuntimeError('Bounded actual RTL stage timeout')
                if time.monotonic()-last>40:
                    tail=path.read_text(errors='replace')[-5000:];matches=re.findall(r'CNN_RTL_PROGRESS cycles=(\d+) instruction=(\d+)',tail);progress={'cycles':int(matches[-1][0]),'instruction':int(matches[-1][1]),'total_instructions':55} if matches else {};status('FINAL trained CNN RTL simulation running',stage=label,seconds=int(time.monotonic()-start),available_ram_gib=round(free(),2),**progress);last=time.monotonic()
            if child.returncode:raise RuntimeError(f'{label} exited{child.returncode}; inspect actual saved log')
        except BaseException:subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True);raise

def compare():
    program=json.loads((BUILD/'program.json').read_text());expected=np.load(BUILD/'expected.npy')[2:3];values=np.fromfile(OUT/'actual_rtl_results.bin',np.int32);length=sum(((h['shape_bchw'][1]+7)//8)*h['shape_bchw'][2]*h['shape_bchw'][3]*8 for h in program['heads'])
    if len(values)!=length:raise RuntimeError('Final full RTL wide output length mismatch')
    offset=0;heads=[]
    for head in program['heads']:
        _,c,h,w=head['shape_bchw'];n=((c+7)//8)*h*w*8;code=values[offset:offset+n].reshape((c+7)//8,h,w,8).transpose(1,2,0,3).reshape(h,w,((c+7)//8)*8)[:,:,:c];heads.append(code.reshape(-1).astype(np.float64)/16384);offset+=n
    actual=np.concatenate(heads)[None];error=np.abs(actual-expected);return {'passed':bool((error==0).all()),'max_abs_error':float(error.max()),'different_values':int((error!=0).sum()),'compared_raw_values':error.size,'whole_real_train_inputs':1}

def main():
    if REPORT.exists():raise RuntimeError('Existing actual final RTL attempt preserved')
    record={'status':'running','rtl_passed':False,'scope':'ACTUAL FINAL ROI epoch11 model, all55instructions/bothrawheads, A24F14/W16. Byte-unchanged generatedRTL/actualtrainedqprogram/coefficients, custom compactAXI model128/256bits. No realMIG/camera/decoder/routedtiming/boardFPS or detectionaccuracy claim.'};save(REPORT,record)
    try:
        provenance=json.loads((OUT/'PROVENANCE.json').read_text())
        for name,sha in {**provenance['rtl_sha256'],**provenance['harness_sha256']}.items():
            if hashlib.sha256((OUT/name).read_bytes()).hexdigest()!=sha:raise RuntimeError('Frozen RTL/harness changed:'+name)
        for name,key in [('program.h','program_sha256'),('coefficients.bin','coefficients_sha256'),('input_2.bin','input_sha256')]:
            if hashlib.sha256((BUILD/name).read_bytes()).hexdigest()!=provenance[key]:raise RuntimeError('Frozen final program/coeff/input changed')
        bin=Path(r'C:\AMDDesignTools\2026.1\Vivado\bin');run('xvlog_final_r1',[str(bin/'xvlog.bat'),'--prj','rtl.prj'],600);run('xelab_final_r1',[str(bin/'xelab.bat'),'work.tb','-s','g2_final_roi11','-L','unisims_ver','-L','xpm','--relax'],900);run('xsim_final_r1',[str(bin/'xsim.bat'),'g2_final_roi11','-tclbatch','run.tcl','-log','xsim_internal.log'],3600)
        text=(OUT/'xsim_final_r1.log').read_text(errors='replace')
        if 'AXI_RAM_UNIT_PASS width=128' not in text or 'AXI_RAM_UNIT_PASS width=256' not in text or 'FULL_CNN_RTL_DONE' not in text:raise RuntimeError('Both RAMunit/completeNN done gates required')
        numeric=compare()
        if not numeric['passed']:raise RuntimeError('Actual final RTL differs from independent reference:'+str(numeric))
        match=re.search(r'FULL_CNN_RTL_DONE cycles=(\d+) feature_reads=(\d+) feature_writes=(\d+) coefficient_reads=(\d+)',text)
        if match is None:raise RuntimeError('Complete circuit cycle/counter evidence missing')
        cycles,reads,writes,coefficients=map(int,match.groups());synthesis=json.loads((HERE/'FINAL_ROI11_FULL_CIRCUIT.json').read_text());record.update(status='complete',rtl_passed=True,unit128_passed=True,unit256_passed=True,numerical=numeric,complete_cnn_cycles=cycles,feature_read_beats256=reads,feature_write_beats256=writes,coefficient_read_beats128=coefficients,modeled_total_bytes=32*(reads+writes)+16*coefficients,simulated_clock_ns=10,conditional_cnn_calls_per_second_at100MHz=100e6/cycles,conditional_two_roi_updates_per_second_at100MHz=100e6/cycles/2,resources=synthesis['resources'],estimated_clock_period_ns=synthesis['estimated_clock_period_ns'],provenance=provenance,performance_caveat='Conditional compactAXI deterministiclatency/stall simulation only. PhysicalDDRarbitration/latency/bandwidth,camera/frontend/decoderandpostrouteclock remain REQUIRED. Simulatorclock/HLSestimate is NOTrealboardFPS.');save(REPORT,record);status('ACTUAL final trained full CNN RTL numerical proof saved',cycles=cycles,raw_error=numeric['max_abs_error'],conditional_two_roi_updates=100e6/cycles/2,board_inference_demonstrated=False)
    except BaseException as exc:record.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,record);status('Actual final RTL needs evidence-based inspection',error=str(exc));raise

if __name__=='__main__':
    with lock():main()
