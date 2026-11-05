"""Independent bounded host then HLS stage; no training or board programming."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import hashlib,json,os,subprocess,traceback,xml.etree.ElementTree as ET
from state import lock,save,status
import run_shared_preflight as runner
BUILD=Path.home()/'fpga_builds/g2_yolov5n_initial_silu_r1'
REPORT=ROOT/'shared_engine/NANO_SILU_R1_SYNTHESIS.json'


def main():
    if REPORT.exists():raise RuntimeError('Previous hardware attempt preserved')
    result={'status':'running','synthesis_passed':False,'rtl_passed':False,'initialized_not_drone_trained':True,'scope':'Entire Nano initialized target 88-op sequencer/shared256MAC/SiLU/SPPF core, HLS resource estimate ONLY. Not routed core or complete camera-system fit, latency, accuracy or physical board proof.'}
    save(REPORT,result)
    try:
        runner.HERE=BUILD
        runner.run('host_gate_driver',[sys.executable,str(ROOT/'shared_engine/check_nano_silu_r1.py')],1800)
        host=json.loads((BUILD/'HOST_NUMERICAL_CHECK.json').read_text())
        if not host['passed']:raise RuntimeError('Complete host gate required before synthesis')
        prepared=json.loads((BUILD/'PREPARED.json').read_text())
        for name,digest in prepared['source_hashes'].items():
            if hashlib.sha256((BUILD/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Frozen source changed:'+name)
        runner.run('synth_nano_silu_r1',[r'C:\AMDDesignTools\2026.1\Vitis\bin\vitis-run.bat','--tcl',runner.tcl('synth'),'--mode','hls'],5400)
        tree=ET.parse(BUILD/'shared_engine_prj/solution1/syn/report/cnn_engine_csynth.xml')
        resources={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/Resources')};limits={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/AvailableResources')}
        fractions={k:v/limits[k] for k,v in resources.items() if limits.get(k,0)>0};period=float(tree.findtext('.//EstimatedClockPeriod'))
        fits=all(fractions.get(k,0)<=.6 for k in ['LUT','DSP','BRAM_18K','FF'])
        result.update(status='complete',synthesis_passed=True,resources=resources,device_limits=limits,resource_fractions=fractions,estimated_clock_period_ns=period,within_engine60percent_reserve=fits,source_hashes=prepared['source_hashes'],host=host)
        save(REPORT,result);status('Nano full core HLS estimate completed',resources=resources,reserve_estimate_passed=fits,rtl_and_route_pending=True)
    except BaseException as exc:
        result.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,result);status('Nano hardware stage needs review',error=str(exc));raise


if __name__=='__main__':
    with lock():main()
