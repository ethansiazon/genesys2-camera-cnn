"""One measured32-output/8-input-lane HLS trial after exact full host parity."""
import sys,json,hashlib,traceback,xml.etree.ElementTree as ET
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
from state import lock,save,status
import run_shared_preflight as runner
BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_output32_r7';REPORT=HERE/'OUTPUT32_R7_SYNTHESIS.json'

def main():
    if REPORT.exists():raise RuntimeError('Existing output32 attempt preserved')
    host=json.loads((BUILD/'HOST_NUMERICAL_CHECK.json').read_text());prepared=json.loads((BUILD/'PREPARED.json').read_text())
    if not host['passed'] or host['numerical']['compared_values']!=241920 or hashlib.sha256((BUILD/'cnn_engine.cpp').read_bytes()).hexdigest()!=prepared['new_sha256']:raise RuntimeError('Changed source requires exact full numerical gate')
    result={'status':'running','synthesis_passed':False,'rtl_passed':False,'prepared':prepared,'scope':'Actual finalROI11 full331114parameter/55op CNN, NEW256MACoutput32 circuit, unchanged numerical format/model/DDRlayout. HLS only; no measured new cycles/routed/system or V5 weight claim.'};save(REPORT,result)
    try:
        runner.HERE=BUILD;name=runner.tcl('synth');runner.run('synth_output32_r7',[r'C:\AMDDesignTools\2026.1\Vitis\bin\vitis-run.bat','--tcl',name,'--mode','hls'],3600)
        tree=ET.parse(BUILD/'shared_engine_prj/solution1/syn/report/cnn_engine_csynth.xml');resources={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/Resources')};limits={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/AvailableResources')};fractions={k:v/limits[k] for k,v in resources.items() if limits.get(k,0)>0};period=float(tree.findtext('.//EstimatedClockPeriod'))
        log=(BUILD/'synth_output32_r7.log').read_text(errors='replace');burst=[s.strip() for s in log.splitlines() if 'burst' in s.lower() and 'infer' in s.lower()]
        result.update(status='complete',synthesis_passed=True,resources=resources,device_limits=limits,resource_fractions=fractions,estimated_clock_period_ns=period,meets100MHz_estimate=period<=10,within_engine60percent_reserve=all(fractions.get(k,0)<=.6 for k in ['LUT','DSP','BRAM_18K','FF']),burst_evidence=burst);save(REPORT,result);status('Output32 circuit HLS report saved',resources=resources,estimated_clock_ns=period,actual_cycles_and_route_pending=True)
    except BaseException as exc:result.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,result);raise

if __name__=='__main__':
    with lock():main()
