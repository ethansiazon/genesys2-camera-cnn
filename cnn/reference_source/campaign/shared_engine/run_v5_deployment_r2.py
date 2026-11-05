"""Independent bounded preparation/host/HLS for actual V5 trained model."""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
import hashlib,json,traceback,xml.etree.ElementTree as ET
from state import lock,save,status
import run_shared_preflight as runner
import check_wide_cpp_r4 as host
BUILD=Path.home()/'fpga_builds/g2_roi_v5_epoch08_output32_r2'
REPORT=HERE/'V5_DEPLOYMENT_R2_SYNTHESIS.json'


def main():
    if REPORT.exists():raise RuntimeError('Existing V5 attempt preserved')
    result={'status':'running','synthesis_passed':False,'rtl_passed':False,'scope':'Actual evaluated V5epoch8 trained331114parameter/55op model on sharedR7circuit. HLS estimate ONLY, not completecamera-system fit or measuredboardFPS.'};save(REPORT,result)
    try:
        runner.HERE=HERE
        runner.run('v5_deploy_prepare_r2',[sys.executable,str(HERE/'prepare_v5_deployment_r2.py')],600)
        host.BUILD=BUILD;host.run('host_compile',[r'C:\msys64\ucrt64\bin\g++.exe','-std=c++14','-O2',r'-IC:\AMDDesignTools\2026.1\Vitis\include','cnn_engine.cpp','test_engine.cpp','-o','test_engine.exe'],300)
        host.run('complete_cpp',[str(BUILD/'test_engine.exe')],1200);numeric=host.compare();save(BUILD/'HOST_NUMERICAL_CHECK.json',{'status':'complete','passed':numeric['passed'],'numerical':numeric,'scope':'Actual trainedV5epoch8, independent3fullvectors. No fit/accuracy claim.'})
        if not numeric['passed']:raise RuntimeError('New V5 complete numerical comparison failed')
        status('Actual V5 full integer host check passed',**numeric)
        runner.HERE=BUILD;runner.run('synth_v5_deployment_r2',[r'C:\AMDDesignTools\2026.1\Vitis\bin\vitis-run.bat','--tcl',runner.tcl('synth'),'--mode','hls'],5400)
        tree=ET.parse(BUILD/'shared_engine_prj/solution1/syn/report/cnn_engine_csynth.xml');resources={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/Resources')};limits={x.tag:int(x.text) for x in tree.find('.//AreaEstimates/AvailableResources')};fractions={k:v/limits[k] for k,v in resources.items() if limits.get(k,0)>0}
        result.update(status='complete',synthesis_passed=True,resources=resources,device_limits=limits,resource_fractions=fractions,within_engine60percent_reserve=all(fractions.get(k,0)<=.6 for k in ['LUT','DSP','BRAM_18K','FF']),estimated_clock_period_ns=float(tree.findtext('.//EstimatedClockPeriod')),host_numerical=numeric)
        save(REPORT,result);status('Actual V5 trained FPGA core estimate completed',resources=resources,rtl_and_route_pending=True)
    except BaseException as exc:result.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,result);status('V5 deployment needs review',error=str(exc));raise


if __name__=='__main__':
    with lock():main()
