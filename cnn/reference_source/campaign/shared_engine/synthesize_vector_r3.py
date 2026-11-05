"""Compile the evidenced vector-stage optimization only; no UVM retry or GPU."""
import sys,json,traceback,xml.etree.ElementTree as ET
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
from state import lock,save,status
import run_shared_preflight as runner
BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_vector_r3'
REPORT=HERE/'VECTOR_R3_SYNTHESIS.json'

def main():
    if REPORT.exists():raise RuntimeError('Existing measured result preserved; inspect before changed retry')
    if not json.loads((BUILD/'HOST_NUMERICAL_CHECK.json').read_text())['passed']:raise RuntimeError('Full3frame host numeric gate required')
    result={'status':'running','synthesis_passed':False,'rtl_passed':False,'scope':'Same complete initialized CNN, staged vector DMA COPY. No trained accuracy/physicalboardclaim.'};save(REPORT,result)
    try:
        text=(Path.home()/'fpga_builds/g2_shared_engine_20261017_live_r2/synth.tcl').read_text();(BUILD/'synth.tcl').write_text(text)
        runner.HERE=BUILD;runner.run('synth_vector_r3',[r'C:\AMDDesignTools\2026.1\Vitis\bin\vitis-run.bat','--tcl','synth.tcl','--mode','hls'])
        tree=ET.parse(BUILD/'shared_engine_prj/solution1/syn/report/cnn_engine_csynth.xml')
        resources={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/Resources')};limits={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/AvailableResources')};fractions={k:v/limits[k] for k,v in resources.items() if limits.get(k,0)>0}
        period=float(tree.findtext('.//EstimatedClockPeriod'));result.update(status='complete',synthesis_passed=True,resources=resources,limits=limits,fractions=fractions,estimated_clock_period_ns=period,meets_requested100MHz_estimate=period<=10,meets_engine_reserve=all(fractions.get(k,0)<=.6 for k in ['LUT','DSP','BRAM_18K','FF']))
        save(REPORT,result);status('Staged complete CNN engine synthesis saved',resources=resources,estimated_clock_ns=period,rtl_still_required=True)
    except BaseException as exc:result.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,result);raise

if __name__=='__main__':
    with lock():main()
