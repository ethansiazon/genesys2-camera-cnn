"""Guarded simulation of unchanged full-network generated RTL, compact AXI harness."""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
import ctypes,hashlib,json,os,re,subprocess,time,traceback
import numpy as np
from state import Memory,lock,save,status
from run_shared_preflight import compare
BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_vector_r3'
OUT=BUILD/'compact_rtl_test';REPORT=HERE/'CUSTOM_RTL_CHECK_R3.json'

def free():
    m=Memory();m.length=ctypes.sizeof(m);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m));return m.available/2**30

def run(label,args,limit):
    logpath=OUT/(label+'.log')
    if logpath.exists():raise RuntimeError('Existing custom-stage log preserved; inspect before changed retry')
    if free()<3:raise RuntimeError('Need3GiB free before starting simulator stage')
    status('Checking complete CNN generated RTL with compact memory model',stage=label)
    with logpath.open('w',encoding='utf-8') as log:
        process=subprocess.Popen(args,cwd=OUT,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        save(HERE/'custom_rtl_r3_active.json',{'pid':process.pid,'stage':label,'started_local':time.strftime('%Y-%m-%d %H:%M:%S')})
        start=last=time.monotonic()
        try:
            while process.poll() is None:
                time.sleep(2)
                if free()<1.5:raise RuntimeError('Own simulator stopped at1.5GiB reserve')
                if time.monotonic()-start>limit:raise RuntimeError('Bounded custom RTL stage exceeded time limit')
                if time.monotonic()-last>40:
                    progress={};tail=logpath.read_text(errors='replace')[-5000:];matches=re.findall(r'CNN_RTL_PROGRESS cycles=(\d+) instruction=(\d+)',tail)
                    if matches:progress={'cycles':int(matches[-1][0]),'instruction':int(matches[-1][1]),'total_instructions':55}
                    status('Full-network RTL simulation running',stage=label,seconds=int(time.monotonic()-start),available_ram_gib=round(free(),2),**progress);last=time.monotonic()
            if process.returncode:raise RuntimeError(f'{label} exited{process.returncode}; inspect{logpath}')
        except BaseException:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True);raise

def main():
    if REPORT.exists():raise RuntimeError('Existing RTL evidence preserved; inspect before changed retry')
    result={'status':'running','rtl_passed':False,'scope':'Complete55instruction CNN sequencer plus tiled circuit, generated RTL unchanged. Compact AXI memory model with legal deterministic stalls; model is NOT physical MIG/board or timing-route proof. New heads untrained.'}
    save(REPORT,result)
    try:
        source=json.loads((OUT/'PROVENANCE.json').read_text())
        for name,sha in source['rtl_sha256'].items():
            if hashlib.sha256((OUT/name).read_bytes()).hexdigest()!=sha:raise RuntimeError('Synthesized RTL changed:'+name)
        bin=Path(r'C:\AMDDesignTools\2026.1\Vivado\bin')
        if not json.loads((HERE/'VECTOR_R3_SYNTHESIS.json').read_text())['synthesis_passed']:raise RuntimeError('R3 synthesis gate missing')
        run('xvlog_r3',[str(bin/'xvlog.bat'),'--prj','rtl.prj'],600)
        run('xelab_r3',[str(bin/'xelab.bat'),'work.tb','-s','g2_shared_actual','-L','unisims_ver','-L','xpm','--relax'],900)
        run('xsim_r3',[str(bin/'xsim.bat'),'g2_shared_actual','-tclbatch','run.tcl','-log','xsim_internal.log'],3600)
        text=(OUT/'xsim_r3.log').read_text(errors='replace')
        if 'AXI_RAM_UNIT_PASS' not in text or 'FULL_CNN_RTL_DONE' not in text:raise RuntimeError('Unit test or complete-network done marker missing; inspect simulator output')
        actual=compare(OUT/'actual_rtl_results.bin',json.loads((BUILD/'program.json').read_text()),np.load(ROOT/'trial03_hardware_expected.npy')[2:3])
        if not actual['passed']:raise RuntimeError('Actual complete generated RTL differs from independent fixed-point reference:'+str(actual))
        match=re.search(r'FULL_CNN_RTL_DONE cycles=(\d+) feature_reads=(\d+) feature_writes=(\d+) coefficient_reads=(\d+)',text)
        cycles,reads,writes,weights=map(int,match.groups())
        result.update(status='complete',rtl_passed=True,axi_memory_unit_passed=True,numerical=actual,complete_cnn_cycles=cycles,
            modeled_feature_read_beats=reads,modeled_feature_write_beats=writes,modeled_coefficient_read_beats=weights,
            simulated_clock_ns=10,conditional_model_cnn_fps_at100MHz=100e6/cycles,
            performance_caveat='Cycles under declared compact AXI memory latency/stalls, excludes camera/realMIG/decoder; NOT measured boardFPS. HLS100MHz estimate passed; functional100MHz simulation is not routed100MHz timing proof.',
            provenance=source,completed_local=time.strftime('%Y-%m-%d %H:%M:%S'))
        save(REPORT,result);status('Complete CNN generated RTL numerical check passed',cycles=cycles,raw_output_error=actual['max_abs_error'],physical_board_fit_proved=False)
    except BaseException as exc:
        result.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,result);status('Compact full RTL check saved for inspection',error=str(exc));raise

if __name__=='__main__':
    with lock():main()

