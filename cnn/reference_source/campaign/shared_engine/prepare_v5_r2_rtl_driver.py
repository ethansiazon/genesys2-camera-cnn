"""Prepare/run one versioned actual V5 trained RTL check after quality gate.

Generated CNN RTL is copied byte-for-byte. Reviewed RAM test harness unchanged.
"""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
import hashlib,json,subprocess
from state import save
BUILD=Path.home()/'fpga_builds/g2_roi_v5_epoch08_output32_r2'


def main():
    provenance=HERE/'V5_R2_RTL_ADAPTATION.json'
    if provenance.exists():raise RuntimeError('Existing V5 RTL attempt preserved')
    synth=json.loads((HERE/'V5_DEPLOYMENT_R2_SYNTHESIS.json').read_text());host=json.loads((BUILD/'HOST_NUMERICAL_CHECK.json').read_text());quality=json.loads((ROOT/'v5_fixed_feedback_native_r1/COMPLETE.json').read_text())
    if not synth['synthesis_passed'] or not host['passed'] or not quality['within_three_percentage_point_loss'] or quality['clipped_values']:
        raise RuntimeError('Full actual trained host/HLS and unchanged-policy quality required')
    hashes={n:hashlib.sha256((BUILD/n).read_bytes()).hexdigest() for n in ['cnn_engine.cpp','cnn_engine.h','program.h']}
    expected=json.loads((BUILD/'PREPARED.json').read_text())['kernel_program_sha256']
    if any(hashes[n]!=expected[n] for n in hashes):raise RuntimeError('Export changed since gates')
    save(HERE/'V5_R2_RTL_INPUT_GATE.json',{'status':'complete','synthesis_passed':True,'cpp_passed':True,'kernel_program_sha256':hashes})
    adapted={}
    for source_name,new_name in [('prepare_output32_r7_actual_rtl.py','prepare_v5_r2_actual_rtl.py'),('run_output32_r7_actual_rtl.py','run_v5_r2_actual_rtl.py')]:
        text=(HERE/source_name).read_text()
        for before,after in [('g2_roi_epoch11_output32_r7','g2_roi_v5_epoch08_output32_r2'),('compact_output32_r7','compact_v5_r2'),('R7_RTL_INPUT_GATE','V5_R2_RTL_INPUT_GATE'),('OUTPUT32_R7_SYNTHESIS','V5_DEPLOYMENT_R2_SYNTHESIS'),('OUTPUT32_R7_ACTUAL_RTL','V5_R2_ACTUAL_RTL'),('reuse_r6_rtl_active','v5_r2_rtl_active'),('FINAL ROI epoch11','V5 epoch8'),('FINALROI11','V5epoch8'),('FINAL ROI11','V5 epoch8'),('FINAL trained','V5 trained'),('final_roi11','v5_epoch8')]:text=text.replace(before,after)
        path=HERE/new_name
        if path.exists():raise RuntimeError('Existing adapted source preserved')
        path.write_text(text);adapted[new_name]=hashlib.sha256(path.read_bytes()).hexdigest()
    save(provenance,{'source_templates':{n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ['prepare_output32_r7_actual_rtl.py','run_output32_r7_actual_rtl.py']},'adapted_sha256':adapted,'actual_trained_checkpoint_sha256':json.loads((BUILD/'PREPARED.json').read_text())['checkpoint_sha256'],'changes':'Versioned model/build/gate/output/progress/simulation naming only. Same55op/twohead layout; copied generatedRTL NEVERedited. OriginalRAM128/256unitgates/realTRAINvector/full80640rawoutputs required.','scope':'Prepared actual-trained RTL experiment, not result, route, physicalDDR or board proof.'})
    subprocess.run([sys.executable,'-u',str(HERE/'prepare_v5_r2_actual_rtl.py')],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'-u',str(HERE/'run_v5_r2_actual_rtl.py')],cwd=ROOT,check=True)


if __name__=='__main__':main()
