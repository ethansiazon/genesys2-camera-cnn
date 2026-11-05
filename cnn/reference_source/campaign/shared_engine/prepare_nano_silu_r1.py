"""Versioned full Nano export and SiLU/SPPF circuit preparation. CPU only.

Original R7 source and initialized COCO-transfer checkpoint remain untouched.
SiLU's signed product, negative maxpool padding and three heads are explicit.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import environment
import copy, hashlib, json, math, operator, shutil
import cv2, numpy as np, torch
from torch import nn
from torch.fx.passes.shape_prop import ShapeProp
from nano_fixed_r1 import LutSiLU, FixedReference, sigmoid_table
from state import guard, save, status

SOURCE = Path.home() / 'fpga_builds/g2_roi_epoch11_output32_r7'
BUILD = Path.home() / 'fpga_builds/g2_yolov5n_initial_silu_r1'
TRIAL = ROOT / 'trial06_yolov5n_coco'
KEYS = ['kind','a','b','o','ih','iw','ic','oh','ow','oc','k','s','p','wo','bo','q','relu','bc']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def allocate(ops, heads, input_words):
    sizes = {0: input_words}; last = {}
    for pc, op in enumerate(ops):
        sizes[op['o']] = ((op['oc'] + 7)//8) * op['oh'] * op['ow']
        last[op['a']] = pc
        if op['kind'] in (2,3): last[op['b']] = pc
    for head in heads: last[head['offset_words']] = len(ops)
    for pc, op in enumerate(ops): last.setdefault(op['o'], pc)
    addresses = {0:0}; active = {0}; free = []; high = input_words; result = []; audit = []
    def release(base, size):
        free.append((base,size)); free.sort(); merged = []
        for a,n in free:
            if merged and merged[-1][0]+merged[-1][1] == a: merged[-1] = (merged[-1][0], merged[-1][1]+n)
            else: merged.append((a,n))
        free[:] = merged
    for pc, op in enumerate(ops):
        inputs = [op['a']] + ([op['b']] if op['kind'] in (2,3) else [])
        if any(i not in active for i in inputs): raise RuntimeError('Read after last use')
        count = sizes[op['o']]; slot = next((i for i,(_,n) in enumerate(free) if n>=count), None)
        if slot is None: base = high; high += count
        else:
            base,n = free.pop(slot)
            if n>count: free.insert(slot,(base+count,n-count))
        for source in active:
            if max(base,addresses[source]) < min(base+count,addresses[source]+sizes[source]):
                raise RuntimeError('Still-live tensor aliases output')
        addresses[op['o']] = base; active.add(op['o']); new = dict(op,a=addresses[op['a']],o=base)
        if op['kind'] in (2,3): new['b'] = addresses[op['b']]
        result.append(new)
        for source in list(active):
            if last[source] == pc:
                active.remove(source); release(addresses[source],sizes[source])
        audit.append({'pc':pc,'output':base,'words':count,'live_words':sum(sizes[i] for i in active)})
    for head in heads: head['offset_words'] = addresses[head['offset_words']]
    return result, high, audit


def adapt_kernel():
    src = (SOURCE/'cnn_engine.cpp').read_text()
    if sha(SOURCE/'cnn_engine.cpp') != '8020b79cc29f5ccae6868975a889b80d0057838ad7f36502e982e2e138c6de1d':
        raise RuntimeError('Frozen proven R7 source changed')
    src = src.replace('#include "program.h"', '#include "program.h"\n#include "silu_lut.h"')
    start = src.index('\nstatic void convolve(')
    helper = '''
// One ROM per packed output lane; eight simultaneous lookups, not 32.
static ap_int<24> activated_round(ap_int<48> value,int shift,int activation,int n) {
    #pragma HLS INLINE
    #pragma HLS ARRAY_PARTITION variable=SILU_TABLE complete dim=1
    #pragma HLS BIND_STORAGE variable=SILU_TABLE type=rom_1p impl=bram
    ap_int<24> raw=rounded(value,shift,activation==1);
    if(activation!=2)return raw;
    int index=(int(raw)+196608+32)>>6;
    if(index<0)index=0;
    if(index>6144)index=6144;
    // Signed18 is essential: signed17 cannot represent sigmoid's +65536.
    ap_int<18> probability=ap_int<18>(SILU_TABLE[n][index]);
    ap_int<42> product=raw*probability;
    return rounded(ap_int<48>(product),16,false);
}

static void maxpool5(FeatureWord* memory,Op op) {
    #pragma HLS INLINE off
    const int blocks=(op.ic+7)/8;
    for(int c=0;c<blocks;c++)for(int y=0;y<op.oh;y++)for(int x=0;x<op.ow;x++) {
        ap_int<24> best[8];
        #pragma HLS ARRAY_PARTITION variable=best complete
        for(int n=0;n<8;n++) {
            #pragma HLS UNROLL
            best[n]=-8388608;
        }
        for(int ky=0;ky<5;ky++)for(int kx=0;kx<5;kx++) {
            #pragma HLS PIPELINE II=1
            const int sy=y+ky-2,sx=x+kx-2;
            if(sy>=0 && sx>=0 && sy<op.ih && sx<op.iw) {
                FeatureWord word=memory[op.a+(c*op.ih+sy)*op.iw+sx];
                for(int n=0;n<8;n++) {
                    #pragma HLS UNROLL
                    ap_int<24> value=lane(word,n);
                    if(value>best[n])best[n]=value;
                }
            }
        }
        FeatureWord out=0;
        for(int n=0;n<8;n++) {
            #pragma HLS UNROLL
            ap_int<32> value=(c*8+n<op.oc)?best[n]:ap_int<24>(0);
            out.range(n*32+31,n*32)=value.range(31,0);
        }
        memory[op.o+(c*op.oh+y)*op.ow+x]=out;
    }
}
'''
    src = src[:start] + '\n' + helper + src[start:]
    before = 'rounded(accum[group*8+n][y*8+x],fraction-14,op.relu!=0)'
    if src.count(before)!=1: raise RuntimeError('Activation insertion anchor changed')
    src = src.replace(before,'activated_round(accum[group*8+n][y*8+x],fraction-14,op.relu,n)')
    src = src.replace('else vector_operation(features,op);','else if(op.kind==7)maxpool5(features,op);\n        else vector_operation(features,op);')
    src = src.replace('LOOP_TRIPCOUNT min=1 max=4\n    CacheOutputSubgroups:', 'LOOP_TRIPCOUNT min=1 max=8\n    CacheOutputSubgroups:')
    src = src.replace('LOOP_TRIPCOUNT min=1 max=16\n                    const bool has_padding', 'LOOP_TRIPCOUNT min=1 max=64\n                    const bool has_padding')
    (BUILD/'cnn_engine.cpp').write_text(src)
    shutil.copy2(SOURCE/'cnn_engine.h',BUILD/'cnn_engine.h')
    test = (SOURCE/'test_engine.cpp').read_text().replace('write_words(results,memory.data()+HEAD1_OFFSET,HEAD1_WORDS);','write_words(results,memory.data()+HEAD1_OFFSET,HEAD1_WORDS);write_words(results,memory.data()+HEAD2_OFFSET,HEAD2_WORDS);')
    (BUILD/'test_engine.cpp').write_text(test)
    table = sigmoid_table().tolist(); bank = '{'+','.join(map(str,table))+'}'
    (BUILD/'silu_lut.h').write_text('#pragma once\n#include <ap_int.h>\nstatic const ap_uint<17> SILU_TABLE[8][6145]={\n'+',\n'.join([bank]*8)+'\n};\n')


def main():
    if BUILD.exists(): raise RuntimeError('Existing versioned Nano preparation preserved')
    guard(); torch.set_num_threads(2); cv2.setNumThreads(1); torch.manual_seed(20261021)
    net = torch.load(TRIAL/'initial_fused_fx.pt',map_location='cpu',weights_only=False).eval()
    ShapeProp(net).propagate(torch.zeros(1,3,192,256)); modules = dict(net.named_modules())
    configs = []; weights = []; weight_words = 0; address = 0; offsets = {}; shapes = {}; ops = []; heads = []
    for node in net.graph.nodes:
        if node.op=='output':
            heads=[{'name':n.name,'offset_words':offsets[n.name],'shape_bchw':list(shapes[n.name])} for n in node.args[0]]; continue
        _,c,h,w = shape = tuple(node.meta['tensor_meta'].shape); shapes[node.name] = shape
        if node.op=='call_module' and isinstance(modules[node.target],nn.SiLU):
            parent=node.args[0]
            if not isinstance(modules.get(parent.target),nn.Conv2d) or len(parent.users)!=1: raise RuntimeError('Unfusable SiLU')
            offsets[node.name]=offsets[parent.name]; continue
        offsets[node.name]=address; address+=((c+7)//8)*h*w
        if node.op=='placeholder': continue
        left=node.args[0][0] if node.op=='call_function' and node.target is torch.cat else node.args[0]
        _,ci,ih,iw=shapes[left.name]
        op=dict(name=node.name,kind=0,a=offsets[left.name],b=0,o=offsets[node.name],ih=ih,iw=iw,ic=ci,oh=h,ow=w,oc=c,k=0,s=0,p=0,wo=0,bo=0,q=0,relu=0,bc=0)
        if node.op=='call_module':
            m=modules[node.target]
            if isinstance(m,nn.Conv2d):
                if m.groups!=1 or m.dilation!=(1,1) or m.kernel_size[0] not in (1,3,6): raise RuntimeError('Unsupported convolution')
                maximum=float(m.weight.abs().max()); q=min(20,15-math.ceil(math.log2(max(maximum,1e-12)+1e-9)))
                bias=np.rint(m.bias.detach().numpy().astype(np.float64)*16384).astype(np.int64)
                if bias.min()<-(1<<23) or bias.max()>=(1<<23): raise RuntimeError('Bias A24 overflow')
                while q>=5:
                    codes=np.rint(m.weight.detach().numpy().astype(np.float64)*2.**q).astype(np.int64)
                    bounds=np.abs(codes).reshape(c,-1).sum(axis=1)*(1<<23)+np.abs(bias)*(1<<q)
                    if codes.min()>=-32768 and codes.max()<=32767 and bounds.max()<(1<<47): break
                    q-=1
                if q<5: raise RuntimeError('No safe precision/48bit accumulator bound')
                with torch.no_grad():m.weight.copy_(torch.from_numpy(codes/2.**q));m.bias.copy_(torch.from_numpy(bias/16384))
                configs.append({'name':node.name,'weight_fraction':q,'raw_accumulator_abs_bound':int(bounds.max()),'weights':codes.size})
                k=m.kernel_size[0]; raw=codes.astype(np.int16)
                if k==6:
                    if m.stride!=(2,2) or m.padding!=(2,2) or ci!=3 or ih%2 or iw%2: raise RuntimeError('Stem transform geometry')
                    original=raw.copy(); raw=raw.reshape(c,ci,3,2,3,2).transpose(0,1,3,5,2,4).copy().reshape(c,ci*4,3,3)
                    probe=torch.randint(-7,8,(1,ci,16,24)).double()
                    aa=torch.nn.functional.conv2d(probe,torch.from_numpy(original).double(),stride=2,padding=2)
                    bb=torch.nn.functional.conv2d(torch.nn.functional.pixel_unshuffle(probe,2),torch.from_numpy(raw).double(),padding=1)
                    if not torch.equal(aa,bb): raise RuntimeError('Exact stem transform failed')
                    pre=dict(op,name='pixel_unshuffle_stem_exact',kind=6,o=address,oh=ih//2,ow=iw//2,oc=ci*4)
                    ops.append(pre);address+=((ci*4+7)//8)*(ih//2)*(iw//2)
                    ci*=4;ih//=2;iw//=2;k=3;op.update(a=pre['o'],ih=ih,iw=iw,ic=ci)
                if (ci+7)//8*k*k>144 or c>256 or ci>512: raise RuntimeError('Runtime cache bounds')
                padded=np.zeros((((c+15)//16)*16,((ci+7)//8)*8,k,k),np.int16);padded[:c,:ci]=raw
                blocked=padded.reshape((c+15)//16,16,(ci+7)//8,8,k,k).transpose(0,2,4,5,1,3).copy()
                op.update(kind=1,k=k,s=1 if m.kernel_size[0]==6 else m.stride[0],p=1 if m.kernel_size[0]==6 else m.padding[0],q=q,wo=weight_words)
                weights.append(blocked.tobytes());weight_words+=blocked.nbytes//16
                b=np.zeros(((c+3)//4)*4,np.int32);b[:c]=bias;op['bo']=weight_words;weights.append(b.tobytes());weight_words+=b.nbytes//16
                if len(node.users)==1:
                    user=next(iter(node.users));op['relu']=2 if user.op=='call_module' and isinstance(modules[user.target],nn.SiLU) else 0
            elif isinstance(m,nn.Upsample):
                if m.mode!='nearest' or h!=ih*2 or w!=iw*2: raise RuntimeError('Upsample geometry')
                op['kind']=4
            elif isinstance(m,nn.MaxPool2d):
                if m.kernel_size!=5 or m.stride!=1 or m.padding!=2 or m.ceil_mode or m.dilation!=1: raise RuntimeError('Pool geometry')
                op.update(kind=7,k=5,s=1,p=2)
            else: raise RuntimeError('Unsupported module '+str(m))
        elif node.op=='call_function' and node.target is operator.add:
            if shapes[node.args[1].name]!=shape: raise RuntimeError('Add shape')
            op.update(kind=2,b=offsets[node.args[1].name])
        elif node.op=='call_function' and node.target is torch.cat:
            sources=node.args[0]
            if len(sources)!=2 or node.kwargs['dim']!=1 or ci%8: raise RuntimeError('Concat packing')
            other=sources[1]
            if shapes[other.name][2:]!=(h,w): raise RuntimeError('Concat shape')
            op.update(kind=3,b=offsets[other.name],bc=shapes[other.name][1])
        else: raise RuntimeError('Unsupported graph node '+str(node))
        if not op['kind']: raise RuntimeError('Undefined op')
        ops.append(op)
    ops,high,audit=allocate(ops,heads,192*256)
    BUILD.mkdir();adapt_kernel()
    header='#pragma once\n#include "cnn_engine.h"\n'
    header+=f'#define FEATURE_WORDS {high}\n#define COEFFICIENT_WORDS {weight_words}\n#define PROGRAM_LENGTH {len(ops)}\n#define INPUT_WORDS {192*256}\n'
    header+='static const Op PROGRAM[PROGRAM_LENGTH]={\n'+',\n'.join('{'+','.join(str(op[k]) for k in KEYS)+'}' for op in ops)+'\n};\n'
    for i,head in enumerate(heads):
        _,c,h,w=head['shape_bchw'];header+=f'#define HEAD{i}_OFFSET {head["offset_words"]}\n#define HEAD{i}_WORDS {((c+7)//8)*h*w}\n'
    (BUILD/'program.h').write_text(header);(BUILD/'coefficients.bin').write_bytes(b''.join(weights))
    program={'scope':'Complete initialized COCO-transfer Nano target, no drone training/accuracy/fit claim.','model_sha256':sha(TRIAL/'initial.pt'),'instruction_count':len(ops),'instructions':ops,'feature_ddr_words':high,'feature_ddr_bytes':high*32,'coefficient_ddr_words':weight_words,'coefficient_ddr_bytes':weight_words*16,'heads':heads,'layout':'NCHW8 signed24F14 in32bit lanes, 256bit feature words; W16 per-layerq; bias24F14; signed48 accumulators','memory_plan':{'live_interval_overlap_checks_passed':True,'original_feature_words':address,'allocated_words':high}}
    save(BUILD/'program.json',program);save(BUILD/'LIVENESS_AUDIT.json',audit)
    for name,m in list(net.named_modules()):
        if isinstance(m,nn.SiLU):
            parent,_,leaf=name.rpartition('.');setattr(net.get_submodule(parent),leaf,LutSiLU())
    net=net.double().eval();torch.save(net,BUILD/'quantized_lut_fx.pt')
    save(BUILD/'QUANTIZED_MODEL_METADATA.json',{'conv_configs':configs,'format':program['layout'],'initialized_not_drone_trained':True})
    # One registered TRAIN image, never a development/test frame.
    from data_roi256 import Data
    rows=json.loads((ROOT/'roi256_dataset/manifest_native_all_v3.json').read_text())['train']
    row=next(r for r in rows if r['group']=='drone' and r['view']=='full');real=Data([row])[0][0][None].double()
    yy,xx=torch.meshgrid(torch.arange(192),torch.arange(256),indexing='ij')
    pattern=torch.stack(((xx%17)/16.,(yy%13)/12.,((xx//7+yy//5)%2).double()))[None]
    expected=[];clips=[]
    for i,x in enumerate((torch.zeros_like(real),pattern,real)):
        guard();status('Checking new Nano full integer reference',vector=i,total=3)
        padded=np.zeros((1,8,192,256),np.int32);padded[0,:3]=np.rint(x[0].numpy()*16384).astype(np.int32)
        (BUILD/f'input_{i}.bin').write_bytes(padded.transpose(0,2,3,1).copy().tobytes())
        ref=FixedReference(net)
        with torch.no_grad():outputs=ref.run(x)
        expected.append(np.concatenate([o.permute(0,2,3,1).numpy().reshape(-1) for o in outputs]));clips.append(ref.clipped)
    np.save(BUILD/'expected.npy',np.stack(expected));save(BUILD/'VECTORS.json',{'vectors':['zero_bias_path','distinct_rgb_xy_checker','registered_train_image'],'real_train_image':row['image_path'],'clipping':clips,'scope':'Independent float64/integer-bound reference; all three raw heads, not detector performance.'})
    prepared={'prepared':True,'build':str(BUILD),'checkpoint_sha256':sha(TRIAL/'initial.pt'),'source_kernel_sha256':sha(SOURCE/'cnn_engine.cpp'),'new_sha256':sha(BUILD/'cnn_engine.cpp'),'source_hashes':{n:sha(BUILD/n) for n in ['cnn_engine.cpp','cnn_engine.h','silu_lut.h','program.h','program.json','coefficients.bin','test_engine.cpp']},'instruction_count':len(ops),'heads':heads,'feature_ddr_mib':high*32/2**20,'coefficient_ddr_mib':weight_words*16/2**20,'silu_count':sum(op['relu']==2 for op in ops),'pool_count':sum(op['kind']==7 for op in ops),'scope':'New full initialized Nano hardware numerical experiment. Not trained drone model, HLS fit, routed timing, camera-system or board proof.'}
    save(BUILD/'PREPARED.json',prepared);save(ROOT/'shared_engine/NANO_SILU_R1_PREPARED.json',prepared);status('Full Nano SiLU/SPPF export prepared',instructions=len(ops),three_heads=True,fit_proven=False)


if __name__=='__main__': main()
