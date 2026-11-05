"""Freeze adapted compact harness/runner for CHANGED R7, then one actual RTL run.

The original final-ROI11 verified simulator is preserved. Adaptation is saved as
ordinary versioned source for review; no generated CNN RTL is edited.
"""
import sys,json,hashlib,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
from state import save,lock
BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_output32_r7'

def change(text,old,new):
    if text.count(old)!=1:raise RuntimeError('Reviewed harness adaptation anchor changed:'+old[:80])
    return text.replace(old,new)

def main():
    if (HERE/'OUTPUT32_R7_RTL_ADAPTATION.json').exists():raise RuntimeError('Existing R7 RTL preparation preserved')
    synthesis=json.loads((HERE/'OUTPUT32_R7_SYNTHESIS.json').read_text());host=json.loads((BUILD/'HOST_NUMERICAL_CHECK.json').read_text())
    if not synthesis['synthesis_passed'] or not host['passed']:raise RuntimeError('Full numerical/synthesis prerequisites missing')
    checked={name:hashlib.sha256((BUILD/name).read_bytes()).hexdigest() for name in ['cnn_engine.cpp','cnn_engine.h','program.h']}
    if checked['cnn_engine.cpp']!=synthesis['prepared']['new_sha256']:raise RuntimeError('Actual synthesized source changed')
    gate=HERE/'R7_RTL_INPUT_GATE.json';save(gate,{'status':'complete','synthesis_passed':True,'cpp_passed':True,'kernel_program_sha256':checked})
    source=(HERE/'prepare_final_roi11_rtl.py').read_text()
    source=change(source,"BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_wide_r2_live'","BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_output32_r7'")
    source=change(source,"OUT=BUILD/'compact_final_rtl_r1'","OUT=BUILD/'compact_output32_r7'")
    source=change(source,"HERE/'FINAL_ROI11_FULL_CIRCUIT.json'","HERE/'R7_RTL_INPUT_GATE.json'")
    prepare_path=HERE/'prepare_output32_r7_actual_rtl.py';prepare_path.write_text(source)
    runner=(HERE/'run_final_roi11_rtl.py').read_text()
    runner=change(runner,"BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_wide_r2_live';OUT=BUILD/'compact_final_rtl_r1';REPORT=HERE/'FINAL_ROI11_ACTUAL_RTL.json'","BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_output32_r7';OUT=BUILD/'compact_output32_r7';REPORT=HERE/'OUTPUT32_R7_ACTUAL_RTL.json'")
    runner=change(runner,"HERE/'FINAL_ROI11_FULL_CIRCUIT.json'","HERE/'OUTPUT32_R7_SYNTHESIS.json'")
    runner=change(runner,"HERE/'final_roi11_rtl_active.json'","HERE/'reuse_r6_rtl_active.json'")
    runner_path=HERE/'run_output32_r7_actual_rtl.py';runner_path.write_text(runner)
    save(HERE/'OUTPUT32_R7_RTL_ADAPTATION.json',{'prepared':True,'checked_kernel_program':checked,'source_templates':{n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ['prepare_final_roi11_rtl.py','run_final_roi11_rtl.py']},'adapted_files':{n.name:hashlib.sha256(n.read_bytes()).hexdigest() for n in [prepare_path,runner_path]},'changes':['Different build/output/report/active paths','New numerical and actual R7 synthesis prerequisite with all kernel hashes','New synthesis resources in final result'],'unchanged':'Both128/256bit AXIRAM models/stall/unit tests, full actual generated RTL, coefficient/input/program identities and all80640 raw-output comparisons','scope':'Not a claim of success; actual RTL gates must complete. Same ROI11 math, NEW scheduling/cache.'})
    subprocess.run([sys.executable,'-u',str(prepare_path)],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'-u',str(runner_path)],cwd=ROOT,check=True)
    old=json.loads((HERE/'FINAL_ROI11_ACTUAL_RTL.json').read_text());new=json.loads((HERE/'OUTPUT32_R7_ACTUAL_RTL.json').read_text())
    if not new['rtl_passed']:raise RuntimeError('Actual changed RTL failed')
    save(HERE/'OUTPUT32_R7_COMPARISON.json',{'passed':True,'old_cycles':old['complete_cnn_cycles'],'new_cycles':new['complete_cnn_cycles'],'conditional_cycle_speedup':old['complete_cnn_cycles']/new['complete_cnn_cycles'],'old_modeled_bytes':old['modeled_total_bytes'],'new_modeled_bytes':new['modeled_total_bytes'],'old_hls_resources':old['resources'],'new_hls_resources':new['resources'],'scope':'Same exact ROI11 final trained math, full-network actual generated RTL, same input and compactAXI/stalls. NOT measured physicalDDR or fullcamera-systemFPS. New cache core needs actual routed timing/size if selected; decoder/preprocessor/system still absent.'})

if __name__=='__main__':main()
