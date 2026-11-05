"""Prepare trained-seed A24F14/W16 full CNN program/vectors, CPU only.
No hardware fit/accuracy claim and no active ROI training files changed.
"""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
import environment
import copy,hashlib,json,math,subprocess
import cv2,numpy as np,torch
from torch import nn
from model_p2_two_class import make,HardwareGraph
from data_roi256 import Data
from state import guard

BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_wide_r4_roi256'

def main():
    if (BUILD/'QUANTIZED_MODEL_METADATA.json').exists():raise RuntimeError('Existing export preserved')
    guard();torch.set_num_threads(2);cv2.setNumThreads(1);torch.manual_seed(20261017)
    checkpoint=ROOT/'trial03_p23_consistent_flying/epoch_05.pt';snap=torch.load(checkpoint,map_location='cpu',weights_only=False);net,_=make(anchors=snap['config']['anchors']);net.load_state_dict(snap['ema']);net.eval()
    raw=HardwareGraph(copy.deepcopy(net));fused=torch.fx.symbolic_trace(HardwareGraph(copy.deepcopy(net).fuse()).eval())
    for node in fused.graph.nodes:
        if node.op=='call_function' and node.target is torch.cat and len(node.args)>1:node.kwargs={**node.kwargs,'dim':node.args[1]};node.args=(node.args[0],)
    fused.graph.lint();fused.recompile();probe=torch.rand(1,3,192,256)
    with torch.no_grad():folding=max(float((a-b).abs().max()) for a,b in zip(raw(probe),fused(probe)))
    if folding>.002:raise RuntimeError('Trained BN folding mismatch')
    modules=dict(fused.named_modules());configs=[]
    with torch.no_grad():
        for node in fused.graph.nodes:
            if node.op!='call_module' or not isinstance(modules[node.target],nn.Conv2d):continue
            m=modules[node.target];maximum=float(m.weight.abs().max());integer=max(-4,math.ceil(math.log2(max(maximum,1e-12)+1e-9))+1)
            if integer>11:raise RuntimeError('W16 scale outside implemented q range')
            q=16-integer;w=torch.round(m.weight*2**q)
            if w.min()<-32768 or w.max()>32767:raise RuntimeError('W16 coefficient overflow')
            b=torch.round(m.bias*16384)
            if b.abs().max()>=2**23:raise RuntimeError('B24F14 bias overflow')
            # Exact48bit raw accumulator bound covers every partial sum, not just final output.
            bound=float((w.abs().flatten(1).sum(1)*2**23+b.abs()*2**q).max())
            if bound>=2**47:raise RuntimeError('Full48bit accumulator bound exceeded')
            m.weight.copy_(w/2**q);m.bias.copy_(b/16384);configs.append({'name':node.name,'weight_integer':integer,'weight_fraction':q,'raw_accumulator_abs_bound':bound,'weights':m.weight.numel()})
    torch.save(fused,BUILD/'quantized_fx.pt');meta={'checkpoint':str(checkpoint),'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),'input':[256,192,3],'conv_configs':configs,'folding_max_error':folding,
        'format':{'activation_bits':24,'activation_fraction':14,'physical_feature_lane_bits':32,'weight_bits':16,'bias_fraction':14,'bias_bits':24,'accumulator_bits':48},
        'scope':'Trained retained globalepoch5 seed, full same CNN at256ROI size. NOT the final newly fine-tuned ROI model. Per-layerW16/A24F14 initial engine conversion, not quantized accuracy or hardware resource/timing proof.'}
    (BUILD/'QUANTIZED_MODEL_METADATA.json').write_text(json.dumps(meta,indent=2))
    source=(HERE/'export_program.py').read_text();source=source.replace('HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))',f'HERE=Path({str(BUILD)!r});ROOT=Path({str(ROOT)!r});sys.path.insert(0,str(ROOT))')
    source=source.replace("ROOT/'trial03_quantized_fx.pt'","HERE/'quantized_fx.pt'").replace("ROOT/'TRIAL03_CODEGEN_GATE.json'","HERE/'QUANTIZED_MODEL_METADATA.json'")
    source=source.replace('ShapeProp(net).propagate(torch.zeros(1,3,288,384))','ShapeProp(net).propagate(torch.zeros(1,3,192,256))').replace('q=12-cfg','q=16-cfg')
    source=source.replace('assert raw.min()>=-2048 and raw.max()<=2047','assert raw.min()>=-32768 and raw.max()<=32767')
    source=source.replace('out=np.zeros(((c+7)//8,8,h,w),np.int16)','out=np.zeros(((c+7)//8,8,h,w),np.int32)').replace('{288*384}','{192*256}')
    source=source.replace('torch.randn(1,ci,32,48,dtype=torch.float64)','torch.randint(-7,8,(1,ci,32,48)).to(torch.float64)')
    begin=source.index('    source=Path(json.loads(');end=source.index('    result={',begin);source=source[:begin]+source[end:]
    source=source.replace("'feature_ddr_bytes':address*16","'feature_ddr_bytes':address*32").replace('feature_ddr_mib=address*16','feature_ddr_mib=address*32').replace('NCHW8, 128bit words','NCHW8, 256bit feature words (coefficient words128bit)').replace('signed16activation codes frac10; signed12weight codes','signed24activation codes frac14 stored32bit lanes; signed16weight codes')
    source=source.replace('Complete initialized two-class P2/P3 CNN scheduled on shared circuit. No training accuracy or synthesis/RTL/board claim.','Complete retained trained-seed two-class P2/P3 CNN at256ROI, A24F14/W16 shared circuit. Not final ROI-trained quality or synthesis/RTL/board proof.')
    source=source.replace('from state import save,status','from state import save,status\nstatus=lambda phase,**kw:print(phase,kw,flush=True)')
    (BUILD/'generate_program.py').write_text(source);subprocess.run([sys.executable,str(BUILD/'generate_program.py')],cwd=ROOT,check=True)
    class Fixed(torch.fx.Interpreter):
        def __init__(self,model):super().__init__(model);self.clipped={}
        def run_node(self,node):
            value=super().run_node(node)
            if isinstance(value,torch.Tensor):
                self.clipped[node.name]=int(((value< -512)|(value>8388607/16384)).sum());value=torch.round(value*16384).clamp(-8388608,8388607)/16384
            return value
    rows=json.loads((ROOT/'roi256_dataset/manifest_curated.json').read_text())['train'];row=next(r for r in rows if r['group']=='drone' and r['view']=='full');real=Data([row])[0][0][None].double();yy,xx=torch.meshgrid(torch.arange(192),torch.arange(256),indexing='ij');pattern=torch.stack(((xx%17)/16.,(yy%13)/12.,((xx//7+yy//5)%2).double()))[None]
    reference=[];clipping=[];fused=fused.double().eval()
    for i,x in enumerate([torch.zeros_like(real),pattern,real]):
        guard();raw=np.rint(x[0].numpy()*16384).astype(np.int32);padded=np.zeros((1,8,192,256),np.int32);padded[0,:3]=raw;(BUILD/f'input_{i}.bin').write_bytes(padded.transpose(0,2,3,1).copy().tobytes());interpreter=Fixed(fused)
        with torch.no_grad():heads=interpreter.run(x)
        reference.append(np.concatenate([head.permute(0,2,3,1).numpy().reshape(-1) for head in heads]));clipping.append(interpreter.clipped)
    np.save(BUILD/'expected.npy',np.stack(reference));(BUILD/'VECTORS.json').write_text(json.dumps({'vectors':['zero_bias_path','distinct_rgb_xy_checker','registered_train_image'],'real_train_image':row['image_path'],'input_layout':'NCHW8,8signed32physical lanes per256bit word; rawsigned24F14 codes','output_reference_layout':'BHWC P2thenP3, independent TorchFX float64 exact-integer-bound arithmetic with ties-even rounding/saturation each node','clipping':clipping,'scope':'Full3vector numerical reference only, no detector accuracy/fit proof.'},indent=2));print(BUILD,flush=True)

if __name__=='__main__':main()
