"""Versioned FINAL ROI-trained coefficients/vectors on the same wide R5 engine.
Preserve seed builds and freeze every generated source. CPU-only preparation.
"""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
from state import save

def replace_one(text,old,new):
    if text.count(old)!=1:raise RuntimeError('Reviewed exporter template changed: '+old[:70])
    return text.replace(old,new)

def main():
    p=argparse.ArgumentParser();p.add_argument('--epoch',type=int,required=True);args=p.parse_args();parent=Path.home()/'fpga_builds/g2_shared_engine_20261017_wide_r5_burst_roi256';raw=Path.home()/f'fpga_builds/g2_roi_epoch{args.epoch:02d}_wide_r2';live=Path(str(raw)+'_live')
    if raw.exists() or live.exists():raise RuntimeError('Existing final export preserved')
    checkpoint=ROOT/f'trial04_roi256/epoch_{args.epoch:02d}.pt'
    if not checkpoint.exists():raise RuntimeError('Immutable trained checkpoint required')
    if not json.loads((parent/'HOST_NUMERICAL_CHECK.json').read_text())['passed']:raise RuntimeError('Parent wide R5 numerical gate required')
    raw.mkdir()
    for name in ['cnn_engine.cpp','cnn_engine.h','test_engine.cpp']:shutil.copy2(parent/name,raw/name)
    save(raw/'SOURCE_PROVENANCE.json',{'parent_kernel':str(parent),'kernel_sha256':{name:hashlib.sha256((raw/name).read_bytes()).hexdigest() for name in ['cnn_engine.cpp','cnn_engine.h','test_engine.cpp']},'trained_checkpoint':str(checkpoint),'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),'scope':'SAME R5 runtime-coefficient kernel. NEW FINAL ROI-trained immutable checkpoint export; no source model change, originalseedcoefficients preserved. Quantizedquality/C++/RTL still require checks.'})
    source=(HERE/'export_wide_model_r4.py').read_text();source=replace_one(source,'\nHERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))\n',f'\nHERE=Path({str(HERE)!r});ROOT=Path({str(ROOT)!r});sys.path.insert(0,str(ROOT))\n');source=replace_one(source,"BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_wide_r4_roi256'",f'BUILD=Path({str(raw)!r})')
    source=replace_one(source,"checkpoint=ROOT/'trial03_p23_consistent_flying/epoch_05.pt';snap=torch.load(checkpoint,map_location='cpu',weights_only=False);net,_=make(anchors=snap['config']['anchors']);net.load_state_dict(snap['ema']);net.eval()",f"checkpoint=Path({str(checkpoint)!r});snap=torch.load(checkpoint,map_location='cpu',weights_only=False);seed=torch.load(ROOT/snap['config']['seed_checkpoint'],map_location='cpu',weights_only=False);net,_=make(anchors=seed['config']['anchors']);net.load_state_dict(snap['ema']);net.eval()")
    source=source.replace('Trained retained globalepoch5 seed, full same CNN at256ROI size. NOT the final newly fine-tuned ROI model.','FINAL ROI-trained immutable epoch'+str(args.epoch)+', full same CNN at256ROI size. No seed-only quality claim.');source=source.replace('torch.set_num_threads(2)','torch.set_num_threads(1)')
    script=raw/'reviewed_export_source.py';script.write_text(source);subprocess.run([sys.executable,str(script)],cwd=ROOT,check=True)
    path=raw/'program.json';program=json.loads(path.read_text());program.update(layout='NCHW8:256bit featurewords carrying8signextended32bitA24F14lanes;128bit coefficientwords carrying8signedW16lanes;B24F14stored32bits',feature_word_bits=256,coefficient_word_bits=128,scope=f'FINAL immutable ROI epoch{args.epoch} full CNN coefficients/program, not seed. Hardware arithmetic/quality/fit require checks.');save(path,program)
    planner=(HERE/'plan_live_memory.py').read_text();planner=replace_one(planner,"SOURCE=Path.home()/'fpga_builds/g2_shared_engine_20261017_r1'",f'SOURCE=Path({str(raw)!r})');planner=replace_one(planner,"BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_live_r2'",f'BUILD=Path({str(live)!r})');planner=planner.replace('sizes={0:288*384}','sizes={0:192*256}').replace('high*16','high*32');planner=replace_one(planner,"'input_2.bin']","'input_2.bin','quantized_fx.pt','QUANTIZED_MODEL_METADATA.json','expected.npy','VECTORS.json','SOURCE_PROVENANCE.json']");begin=planner.index("    original=(HERE/'run_shared_preflight.py').read_text()");end=planner.index('    print(json.dumps(',begin);planner=planner[:begin]+planner[end:];script=raw/'reviewed_liveness_source.py';script.write_text(planner);subprocess.run([sys.executable,str(script)],cwd=ROOT,check=True)
    save(ROOT/f'FINAL_ROI_EPOCH{args.epoch:02d}_WIDE_EXPORT.json',{'epoch':args.epoch,'raw_build':str(raw),'live_build':str(live),'checkpoint':str(checkpoint),'kernel_identical_to_r5':all((live/name).read_bytes()==(parent/name).read_bytes() for name in ['cnn_engine.cpp','cnn_engine.h','test_engine.cpp']),'scope':'Prepared final ROI-trained export. Actual48bitbounds/folding/stemreindex/full3inputreferences generated; full C++/RTL and quantizednativeVALquality pending. HLSruntimekernel same, shape unchanged.'});print(live)

if __name__=='__main__':main()
