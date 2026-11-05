"""One guarded changed-code R6 HLS attempt, with a real host parity prerequisite."""
import sys,json,hashlib,traceback,xml.etree.ElementTree as ET
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
from state import lock,save,status
import run_shared_preflight as runner
BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_reuse_r6'
REPORT=HERE/'WEIGHT_REUSE_R6_SYNTHESIS.json'

def main():
    if REPORT.exists():raise RuntimeError('Existing R6 attempt preserved; inspect rather than repeat')
    host=json.loads((BUILD/'HOST_NUMERICAL_CHECK.json').read_text());prepared=json.loads((BUILD/'PREPARED.json').read_text())
    if not host['passed'] or host['numerical']['compared_values']!=241920:raise RuntimeError('Full exact numerical gate required')
    if hashlib.sha256((BUILD/'cnn_engine.cpp').read_bytes()).hexdigest()!=prepared['new_sha256']:raise RuntimeError('Checked R6 source changed')
    program=json.loads((BUILD/'program.json').read_text())
    if program['model_sha256']!='d2b32cd56f5ab2937411707f4096922c7e3657f5d1c17322e3a11432489d6406':raise RuntimeError('Actual finalROI11 weights required')
    result={'status':'running','synthesis_passed':False,'rtl_passed':False,'prepared':prepared,'scope':'Same trained ROI11 full55instruction331114parameter CNN. New weight reuse/interior-clear scheduling only. HLS does not establish routed fit, actual cycle speedup, camera/MIG/system timing or V5 quality.'};save(REPORT,result)
    try:
        runner.HERE=BUILD;name=runner.tcl('synth')
        runner.run('synth_weight_reuse_r6',[r'C:\AMDDesignTools\2026.1\Vitis\bin\vitis-run.bat','--tcl',name,'--mode','hls'],3600)
        tree=ET.parse(BUILD/'shared_engine_prj/solution1/syn/report/cnn_engine_csynth.xml');resources={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/Resources')};limits={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/AvailableResources')};fractions={k:v/limits[k] for k,v in resources.items() if limits.get(k,0)>0};period=float(tree.findtext('.//EstimatedClockPeriod'))
        log=(BUILD/'synth_weight_reuse_r6.log').read_text(errors='replace');burst=[s.strip() for s in log.splitlines() if 'burst' in s.lower() and ('infer' in s.lower() or 'cached' in s.lower())]
        result.update(status='complete',synthesis_passed=True,resources=resources,device_limits=limits,resource_fractions=fractions,estimated_clock_period_ns=period,meets100MHz_estimate=period<=10,within_engine60percent_reserve=all(fractions.get(k,0)<=.6 for k in ['LUT','DSP','BRAM_18K','FF']),burst_evidence=burst);save(REPORT,result);status('Changed same-math R6 circuit HLS report saved',resources=resources,estimated_clock_ns=period,actual_rtl_cycles_pending=True)
    except BaseException as exc:
        result.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,result);raise

if __name__=='__main__':
    with lock():main()
