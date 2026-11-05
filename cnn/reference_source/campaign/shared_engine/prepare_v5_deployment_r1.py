"""Export the ACTUAL successful V5 epoch8 weights onto the proven R7 core.

Same trained model, not a new training run. Preserve all originals and reports.
"""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
import hashlib,json,re,shutil,subprocess
from state import save,guard,status
from prepare_nano_silu_r1 import allocate,KEYS

SOURCE=Path.home()/'fpga_builds/g2_roi_epoch11_output32_r7'
RAW=Path.home()/'fpga_builds/g2_roi_v5_epoch08_output32_raw_r1'
BUILD=Path.home()/'fpga_builds/g2_roi_v5_epoch08_output32_r1'
CHECKPOINT=ROOT/'trial05_roi_robust/epoch_08.pt'


def one(text,before,after):
    if text.count(before)!=1:raise RuntimeError('Reviewed source anchor changed:'+before[:70])
    return text.replace(before,after)


def main():
    if RAW.exists() or BUILD.exists():raise RuntimeError('Existing new trained export preserved')
    guard();expected=json.loads((ROOT/'feedback_r3_miss1_latency009_native_val/FROZEN_CONFIG.json').read_text())['checkpoint_sha256']
    if hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest()!=expected:raise RuntimeError('Actual evaluated checkpoint bytes changed')
    if not json.loads((ROOT/'shared_engine/OUTPUT32_R7_ACTUAL_RTL.json').read_text())['rtl_passed']:raise RuntimeError('Proven R7 base required')
    RAW.mkdir();source=(HERE/'export_wide_model_r4.py').read_text()
    source=one(source,'HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))',f'HERE=Path({str(HERE)!r});ROOT=Path({str(ROOT)!r});sys.path.insert(0,str(ROOT))')
    source=one(source,"BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_wide_r4_roi256'",f'BUILD=Path({str(RAW)!r})')
    source=one(source,"checkpoint=ROOT/'trial03_p23_consistent_flying/epoch_05.pt';snap=torch.load(checkpoint,map_location='cpu',weights_only=False);net,_=make(anchors=snap['config']['anchors']);net.load_state_dict(snap['ema']);net.eval()",f"checkpoint=Path({str(CHECKPOINT)!r});snap=torch.load(checkpoint,map_location='cpu',weights_only=False);seed=torch.load(ROOT/snap['config']['seed_checkpoint'],map_location='cpu',weights_only=False);net,_=make(anchors=seed['config']['anchors']);net.load_state_dict(snap['ema']);net.eval()")
    source=source.replace('Trained retained globalepoch5 seed, full same CNN at256ROI size. NOT the final newly fine-tuned ROI model.','Actual V5 robustness epoch8 trained checkpoint. New coefficients need own numerical/quality/RTL proof.')
    (RAW/'reviewed_export_source.py').write_text(source);subprocess.run([sys.executable,str(RAW/'reviewed_export_source.py')],cwd=ROOT,check=True)
    program=json.loads((RAW/'program.json').read_text());ops,high,audit=allocate(program['instructions'],program['heads'],256*192)
    program.update(instructions=ops,feature_ddr_words=high,feature_ddr_bytes=high*32,scope='Actual V5 epoch8 full trained 331114parameter model, all55ops. R7 shared256MAC circuit; not ROI11 weights. Trained quantization quality/HLS/RTL/route/system still required.',checkpoint_sha256=expected)
    BUILD.mkdir()
    for name in ['cnn_engine.cpp','cnn_engine.h','test_engine.cpp']:shutil.copy2(SOURCE/name,BUILD/name)
    for name in ['coefficients.bin','input_0.bin','input_1.bin','input_2.bin','expected.npy','quantized_fx.pt','QUANTIZED_MODEL_METADATA.json','VECTORS.json']:shutil.copy2(RAW/name,BUILD/name)
    header='#pragma once\n#include "cnn_engine.h"\n'+f'#define FEATURE_WORDS {high}\n#define COEFFICIENT_WORDS {program["coefficient_ddr_words"]}\n#define PROGRAM_LENGTH {len(ops)}\n#define INPUT_WORDS {256*192}\n'
    header+='static const Op PROGRAM[PROGRAM_LENGTH]={\n'+',\n'.join('{'+','.join(str(op[k]) for k in KEYS)+'}' for op in ops)+'\n};\n'
    for i,head in enumerate(program['heads']):
        _,c,h,w=head['shape_bchw'];header+=f'#define HEAD{i}_OFFSET {head["offset_words"]}\n#define HEAD{i}_WORDS {((c+7)//8)*h*w}\n'
    (BUILD/'program.h').write_text(header);save(BUILD/'program.json',program);save(BUILD/'LIVENESS_AUDIT.json',audit)
    kernels={n:hashlib.sha256((BUILD/n).read_bytes()).hexdigest() for n in ['cnn_engine.cpp','cnn_engine.h','program.h','test_engine.cpp','coefficients.bin']}
    report={'prepared':True,'build':str(BUILD),'raw_build':str(RAW),'checkpoint':str(CHECKPOINT),'checkpoint_sha256':expected,'same_circuit_source_as_verified_R7':all((BUILD/n).read_bytes()==(SOURCE/n).read_bytes() for n in ['cnn_engine.cpp','cnn_engine.h','test_engine.cpp']),'kernel_program_sha256':kernels,'instruction_count':len(ops),'scope':'New actual V5 trained export, not new training or Nano. Current sky demonstration evidence motivates checking existing model before more training. Newquantization/nativefeedbackquality/actualRTL/routed/system evidence required.'}
    save(BUILD/'PREPARED.json',report);save(ROOT/'shared_engine/V5_DEPLOYMENT_R1_PREPARED.json',report);status('Actual V5 trained weights exported for FPGA checks',instructions=len(ops),existing_training_preserved=True)


if __name__=='__main__':main()
