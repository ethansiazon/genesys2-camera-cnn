"""Schedule the ENTIRE actual CNN on one runtime-tiled engine, coefficients in DDR.
No source model changes. Original parallel build, vectors and failures preserved.
"""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
import environment
import hashlib,json,math,operator
import numpy as np,torch
from torch import nn
from torch.fx.passes.shape_prop import ShapeProp
from state import save,status

def pack(array):
    c,h,w=array.shape;out=np.zeros(((c+7)//8,8,h,w),np.int16)
    out.reshape(-1,h,w)[:c]=array
    return out.transpose(0,2,3,1).copy()

def main():
    if (HERE/'program.json').exists():raise RuntimeError('Program exists; preserve frozen source/coefficients')
    torch.set_num_threads(4);net=torch.load(ROOT/'trial03_quantized_fx.pt',map_location='cpu',weights_only=False).eval()
    ShapeProp(net).propagate(torch.zeros(1,3,288,384))
    modules=dict(net.named_modules());offset={};shapes={};ops=[];weights=[];records=[];address=0;weight_words=0;heads=[]
    for node in net.graph.nodes:
        if node.op=='output':heads=[n.name for n in node.args[0]];continue
        shape=tuple(node.meta['tensor_meta'].shape);_,c,h,w=shape;shapes[node.name]=shape
        if node.op=='call_module' and isinstance(modules[node.target],nn.ReLU):
            parent=node.args[0]
            if parent.op=='call_module' and isinstance(modules[parent.target],nn.Conv2d) and len(parent.users)==1:
                offset[node.name]=offset[parent.name];continue
        offset[node.name]=address;address+=((c+7)//8)*h*w
        if node.op=='placeholder':continue
        left=node.args[0][0] if node.op=='call_function' and node.target is torch.cat else node.args[0]
        _,ci,ih,iw=shapes[left.name]
        op=dict(kind=0,a=offset[left.name],b=0,o=offset[node.name],ih=ih,iw=iw,ic=ci,oh=h,ow=w,oc=c,k=0,s=0,p=0,wo=0,bo=0,q=0,relu=0,bc=0)
        if node.op=='call_module':
            module=modules[node.target]
            if isinstance(module,nn.Conv2d):
                assert module.groups==1 and module.kernel_size[0]==module.kernel_size[1] and module.kernel_size[0] in [1,3,6]
                assert module.stride[0]==module.stride[1] and module.stride[0] in [1,2] and module.dilation==(1,1)
                cfg=next(x for x in json.loads((ROOT/'TRIAL03_CODEGEN_GATE.json').read_text())['conv_configs'] if x['name']==node.name)
                q=12-cfg['weight_integer'];k=module.kernel_size[0];raw=np.rint(module.weight.detach().numpy()*2.**q).astype(np.int16)
                assert raw.min()>=-2048 and raw.max()<=2047
                if k==6:
                    assert module.stride==(2,2) and module.padding==(2,2) and ih%2==0 and iw%2==0
                    original=raw.copy();oldci=ci
                    raw=raw.reshape(c,ci,3,2,3,2).transpose(0,1,3,5,2,4).copy().reshape(c,ci*4,3,3)
                    probe=torch.randn(1,ci,32,48,dtype=torch.float64);ow=torch.from_numpy(original).double();nw=torch.from_numpy(raw).double()
                    aa=torch.nn.functional.conv2d(probe,ow,stride=2,padding=2)
                    bb=torch.nn.functional.conv2d(torch.nn.functional.pixel_unshuffle(probe,2),nw,padding=1)
                    if float((aa-bb).abs().max())>1e-9:raise RuntimeError('Exact6x6 stem reindexing failed')
                    pre=dict(op);pre.update(kind=6,o=address,oh=ih//2,ow=iw//2,oc=ci*4)
                    ops.append(pre);records.append({'name':'pixel_unshuffle_stem_exact',**pre})
                    address+=((ci*4+7)//8)*(ih//2)*(iw//2)
                    ci*=4;ih//=2;iw//=2;k=3
                    op.update(a=pre['o'],ih=ih,iw=iw,ic=ci)
                padded=np.zeros((((c+15)//16)*16,((ci+7)//8)*8,k,k),np.int16);padded[:c,:ci]=raw
                blocked=padded.reshape((c+15)//16,16,(ci+7)//8,8,k,k).transpose(0,2,4,5,1,3).copy()
                op.update(kind=1,k=k,s=1 if module.kernel_size[0]==6 else module.stride[0],p=1 if module.kernel_size[0]==6 else module.padding[0],q=q,wo=weight_words)
                weights.append(blocked.tobytes());weight_words+=blocked.nbytes//16
                bias=np.zeros(((c+3)//4)*4,np.int32);bias[:c]=np.rint(module.bias.detach().numpy()*16384).astype(np.int32)
                op['bo']=weight_words;weights.append(bias.tobytes());weight_words+=bias.nbytes//16
                if len(node.users)==1:
                    user=next(iter(node.users));op['relu']=int(user.op=='call_module' and isinstance(modules[user.target],nn.ReLU))
            elif isinstance(module,nn.Upsample):
                assert module.mode=='nearest' and h==ih*2 and w==iw*2;op['kind']=4
            elif isinstance(module,nn.ReLU):op['kind']=5
            else:raise RuntimeError('Unsupported module '+str(module))
        elif node.op=='call_function' and node.target is operator.add:
            assert shapes[node.args[1].name]==shape;op.update(kind=2,b=offset[node.args[1].name])
        elif node.op=='call_function' and node.target is torch.cat:
            sources=node.args[0];assert len(sources)==2 and node.kwargs['dim']==1 and ci%8==0
            other=sources[1];assert shapes[other.name][2:]==(h,w);op.update(kind=3,b=offset[other.name],bc=shapes[other.name][1])
        else:raise RuntimeError('Unsupported operator '+str(node))
        assert op['kind']!=0;ops.append(op);records.append({'name':node.name,**op})
    keys=['kind','a','b','o','ih','iw','ic','oh','ow','oc','k','s','p','wo','bo','q','relu','bc']
    header='#ifndef G2_CNN_PROGRAM_H\n#define G2_CNN_PROGRAM_H\n#include "cnn_engine.h"\n'
    header+=f'#define FEATURE_WORDS {address}\n#define COEFFICIENT_WORDS {weight_words}\n#define PROGRAM_LENGTH {len(ops)}\n#define INPUT_WORDS {288*384}\n'
    header+='static const Op PROGRAM[PROGRAM_LENGTH]={\n'+',\n'.join('{'+','.join(str(op[k]) for k in keys)+'}' for op in ops)+'\n};\n'
    for i,name in enumerate(heads):
        _,c,h,w=shapes[name];header+=f'#define HEAD{i}_OFFSET {offset[name]}\n#define HEAD{i}_WORDS {((c+7)//8)*h*w}\n'
    header+='#endif\n';(HERE/'program.h').write_text(header);(HERE/'coefficients.bin').write_bytes(b''.join(weights))
    source=Path(json.loads((ROOT/'TRIAL03_CODEGEN_GATE.json').read_text())['build_directory'])
    inputs=np.loadtxt(source/'tb_data/tb_input_features.dat').reshape(3,288,384,3)
    for i,x in enumerate(inputs):
        raw=np.rint(x.transpose(2,0,1)*1024).astype(np.int16);(HERE/f'input_{i}.bin').write_bytes(pack(raw).tobytes())
    result={'scope':'Complete initialized two-class P2/P3 CNN scheduled on shared circuit. No training accuracy or synthesis/RTL/board claim.',
        'model_sha256':hashlib.sha256((ROOT/'trial03_quantized_fx.pt').read_bytes()).hexdigest(),'instruction_count':len(ops),'instructions':records,
        'feature_ddr_words':address,'feature_ddr_bytes':address*16,'coefficient_ddr_words':weight_words,'coefficient_ddr_bytes':weight_words*16,
        'layout':'NCHW8, 128bit words, signed16activation codes frac10; signed12weight codes with per-layerfraction; signed32bias codes frac14',
        'heads':[{'name':n,'offset_words':offset[n],'shape_bchw':shapes[n]} for n in heads],
        'tile':{'input_channels':8,'output_channels':16,'output_xy':[8,8],'max_kernel':3,'max_stride':2,'planned_parallel_multipliers':128},
        'reference_source':'https://github.com/dhm2013724/yolov2_xilinx_fpga/tree/d9d283fa022971954c93040487ea92881375f89a',
        'source_caveat':'MIT reference inspected for loop/channel/spatial tiling; author warns newer HLS/manual ping-pong and lacks RTL cosim. New implementation does not inherit false-dependence directives or assume reference proves our board behavior.'}
    save(HERE/'program.json',result);status('Complete CNN shared-engine schedule prepared',instructions=len(ops),feature_ddr_mib=address*16/2**20,coefficient_ddr_mib=weight_words*16/2**20)

if __name__=='__main__':main()
