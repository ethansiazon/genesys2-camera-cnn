"""One guarded actual decoder HLS/RTL run, after fresh native integer quality.

Checks actual C-postchecking CSV, not an initial C-reference output directory.
"""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'shared_engine'))
import hashlib,json,traceback,xml.etree.ElementTree as ET
import numpy as np
from state import save,status,lock
import run_shared_preflight as runner
BUILD=Path.home()/'fpga_builds/g2_v5_decoder_work_r2'
REPORT=HERE/'DECODER_WORK_R2_FPGA.json'


def main():
    if REPORT.exists():raise RuntimeError('Previous decoder hardware attempt preserved')
    host=json.loads((BUILD/'HOST_CHECK.json').read_text());quality=json.loads((ROOT/'v5_integer_decoder_native_r2/COMPLETE.json').read_text());core=json.loads((ROOT/'shared_engine/V5_R2_CORE_FIT_REVIEW.json').read_text())
    if not host['passed'] or not quality['within_three_percentage_point_loss'] or not quality['author_negative_gate_passed'] or quality['clipped_values'] or not core['core_fit_verified']:raise RuntimeError('Actual trained core and full integer decoder native quality gates required')
    for name,digest in host['source_sha256'].items():
        if hashlib.sha256((BUILD/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Host-proven decoder source changed')
    record={'status':'running','synthesis_passed':False,'rtl_passed':False,'source_sha256':host['source_sha256'],'scope':'Actual V5geometrydecoder including LUTsigmoid/Q16xywh/nativeworkingmap/motion+associationgates/rawlogitranking. ComponentHLS/RTL only; stillCPUtracker/preprocessing/MIG/camera not complete-system fit or measuredboardFPS.'};save(REPORT,record)
    try:
        tb=(BUILD/'test_decoder.cpp').read_text()
        if tb.count('int cursor=0;')!=1 or tb.count('Candidate best;decode_work_heads')!=1:raise RuntimeError('Frozen testbench anchors changed')
        tb=tb.replace('int cursor=0;','#ifdef RTL_SIM\n  if(frame!=2)continue;\n  #endif\n  int cursor=0;').replace('Candidate best;decode_work_heads','#ifdef RTL_SIM\n   if(id!=0 && id!=3 && id!=9)continue;\n   #endif\n   Candidate best;decode_work_heads')
        (BUILD/'test_decoder_rtl.cpp').write_text(tb);runner.HERE=BUILD
        def tcl(stage):
            reset='-reset ' if stage=='synth' else ''
            code=f'open_project {reset}decoder_prj\nset_top decode_work_heads\nadd_files decoder_work_r2.cpp -cflags "-std=c++14"\nadd_files -tb test_decoder_rtl.cpp -cflags "-std=c++14 -DRTL_SIM"\nadd_files -tb cases.bin\nadd_files -tb queries.txt\n'
            code+=f'open_solution {reset}solution1 -flow_target vivado\nset_part {{xc7k325tffg900-2}}\ncreate_clock -period 10 -name default\nconfig_compile -pipeline_loops 0\n'
            code+=('csynth_design\n' if stage=='synth' else 'cosim_design -rtl verilog -tool xsim -trace_level none\n')+'exit\n'
            name='decoder_'+stage+'.tcl';(BUILD/name).write_text(code);return name
        runner.run('decoder_work_r2_synthesis',[r'C:\AMDDesignTools\2026.1\Vitis\bin\vitis-run.bat','--tcl',tcl('synth'),'--mode','hls'],3600)
        tree=ET.parse(BUILD/'decoder_prj/solution1/syn/report/decode_work_heads_csynth.xml');resources={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/Resources')};record.update(synthesis_passed=True,resources=resources,estimated_clock_period_ns=float(tree.findtext('.//EstimatedClockPeriod')));save(REPORT,record)
        status('Integer box/centre decoder synthesis complete',resources=resources,rtl_pending=True)
        runner.run('decoder_work_r2_cosimulation',[r'C:\AMDDesignTools\2026.1\Vitis\bin\vitis-run.bat','--tcl',tcl('cosim'),'--mode','hls'],3600)
        report=BUILD/'decoder_prj/solution1/sim/report/decode_work_heads_cosim.rpt';text=report.read_text()
        if 'Pass' not in text:raise RuntimeError('Actual decoder RTL cosimulation did not pass')
        # HLS initial C run produces expected data; only wrapc_pc is the C POST
        # CHECKING pass consuming actual RTL transactions. Never use wrapc output.
        actual=BUILD/'decoder_prj/solution1/sim/wrapc_pc/decoder_results.csv'
        if not actual.exists():raise RuntimeError('Need actual C-postchecking CSV; inspect flow rather than substituting C-reference output')
        observed=np.loadtxt(actual,delimiter=',',dtype=np.int64);expected=np.load(BUILD/'expected_results.npy');expected=expected[(expected[:,0]==2)&np.isin(expected[:,1],[0,3,9])]
        if observed.shape!=expected.shape or not np.array_equal(observed,expected):raise RuntimeError('Actual decoder RTL integer fields differ from independent reference')
        numerical={'passed':True,'queries':len(expected),'compared_integer_fields':expected[:,2:].size,'max_abs_error':0,'actual_rtl_postcheck_csv':str(actual),'sha256':hashlib.sha256(actual.read_bytes()).hexdigest()}
        record.update(status='complete',rtl_passed=True,numerical=numerical,cosimulation_report=text);save(REPORT,record);status('Integer box/centre decoder actual RTL passed',queries=len(expected),integer_error=0,full_camera_system_proven=False)
    except BaseException as exc:
        record.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,record);status('Integer decoder hardware needs review',error=str(exc));raise


if __name__=='__main__':
    with lock():main()
