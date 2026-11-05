"""FINAL ROI11 coefficient scale/program differs from seed: verify/re-synthesize.
Do not reuse seed RTL blindly: per-layer q is compiled into program.h.
"""
import hashlib,json,sys,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
from state import lock,save,status
import check_wide_cpp_r4 as host
import synthesize_wide_burst_r5 as synthesis
BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_wide_r2_live'
REPORT=HERE/'FINAL_ROI11_FULL_CIRCUIT.json'

def main():
    if REPORT.exists():raise RuntimeError('Existing actual final circuit attempt preserved')
    parent=Path.home()/'fpga_builds/g2_shared_engine_20261017_wide_r5_burst_roi256';seed=json.loads((parent/'program.json').read_text());final=json.loads((BUILD/'program.json').read_text());changes=[]
    for pc,(a,b) in enumerate(zip(seed['instructions'],final['instructions'])):
        delta={key:[a[key],b[key]] for key in a if a[key]!=b[key]}
        if delta:changes.append({'instruction':pc,'changes':delta})
    if len(seed['instructions'])!=len(final['instructions']) or any(set(r['changes'])-{'q'} for r in changes):raise RuntimeError('Unexpected final shape/schedule change, inspect before compile')
    record={'status':'running','program_changes_from_seed':changes,'cpp_passed':False,'synthesis_passed':False,'rtl_passed':False,'scope':'ACTUAL trained ROI epoch11 coefficient/program verification. SAME circuit source, but new quantization q constants require their own actual HLS output. No original-seed substitution; no final accuracy/system/board claim.'};save(REPORT,record)
    try:
        host.BUILD=BUILD;host.REPORT=BUILD/'HOST_NUMERICAL_CHECK.json';host.main();numeric=json.loads(host.REPORT.read_text());numeric['scope']='FINAL ROI epoch11 full55instruction CNN A24F14/W16, actual Vitis ap_int native C++, three full inputs compared to independent float64rounding FX. No HLS/RTL/accuracy/board claim.';save(host.REPORT,numeric);record['cpp_passed']=numeric['passed'];save(REPORT,record)
        synthesis.BUILD=BUILD;synthesis.REPORT=BUILD/'ACTUAL_HLS_SYNTHESIS.json';synthesis.main();actual=json.loads(synthesis.REPORT.read_text());record.update(status='complete',synthesis_passed=actual['synthesis_passed'],numerical=numeric['numerical'],resources=actual['resources'],resource_fractions=actual['resource_fractions'],estimated_clock_period_ns=actual['estimated_clock_period_ns'],kernel_program_sha256={name:hashlib.sha256((BUILD/name).read_bytes()).hexdigest() for name in ['cnn_engine.cpp','cnn_engine.h','program.h']});save(REPORT,record);status('FINAL trained ROI full circuit C++ and synthesis saved',resources=actual['resources'],rtl_and_quantized_quality_still_pending=True)
    except BaseException as exc:record.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,record);raise

if __name__=='__main__':
    with lock():main()
