"""Guarded actual HLS synthesis of full wide circuit; acquire heavy lock once.
No UVM/co-simulation retry. Runtime coefficients are the numerically tested seed;
final trained coefficients require their own precision/numerical checks.
"""
import sys,json,traceback,xml.etree.ElementTree as ET
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
from state import lock,save,status
import run_shared_preflight as runner
BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_wide_r5_burst_roi256'
REPORT=HERE/'WIDE_BURST_R5_SYNTHESIS.json'

def main():
    if REPORT.exists():raise RuntimeError('Existing measured attempt preserved; no identical retry')
    host=json.loads((BUILD/'HOST_NUMERICAL_CHECK.json').read_text())
    if not host['passed']:raise RuntimeError('Full host numeric gate required')
    result={'status':'running','synthesis_passed':False,'rtl_passed':False,'scope':'Full55instruction331114parameter runtime-coefficientCNN, A24F14/W16,256x192, one128MAC circuit. Actual HLS resources/timing only; not final ROI quantized accuracy, real MIG/camera/decoder/system fit or routed timing.'};save(REPORT,result)
    try:
        tcl=(Path.home()/'fpga_builds/g2_shared_engine_20261017_live_r2/synth.tcl').read_text();(BUILD/'synth.tcl').write_text(tcl)
        runner.HERE=BUILD;runner.run('synth_wide_burst_r5',[r'C:\AMDDesignTools\2026.1\Vitis\bin\vitis-run.bat','--tcl','synth.tcl','--mode','hls'],3600)
        tree=ET.parse(BUILD/'shared_engine_prj/solution1/syn/report/cnn_engine_csynth.xml');resources={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/Resources')};limits={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/AvailableResources')};fractions={k:v/limits[k] for k,v in resources.items() if limits.get(k,0)>0};period=float(tree.findtext('.//EstimatedClockPeriod'))
        log=(BUILD/'synth_wide_burst_r5.log').read_text(errors='replace');burst=[line.strip() for line in log.splitlines() if 'burst' in line.lower() and ('infer' in line.lower() or 'LoadValid' in line)]
        result.update(status='complete',synthesis_passed=True,resources=resources,device_limits=limits,resource_fractions=fractions,estimated_clock_period_ns=period,meets_requested100MHz_estimate=period<=10,within_engine60percent_reserve=all(fractions.get(k,0)<=.6 for k in ['LUT','DSP','BRAM_18K','FF']),burst_inference_evidence=burst);save(REPORT,result);status('Wide complete CNN circuit synthesis saved',resources=resources,estimated_clock_ns=period,rtl_and_system_still_required=True)
    except BaseException as exc:
        result.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,result);raise

if __name__=='__main__':
    with lock():main()
