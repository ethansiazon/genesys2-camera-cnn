"""Light CPU-only actual ap_int host gate; may coexist with guarded route.

New V5 trained raw-head vectors, all geometry/ranking fields independently checked.
Does not launch FPGA tools or change any trained model/inference configuration.
"""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'shared_engine'))
import environment
import hashlib,json,shutil
import numpy as np,torch
from decoder_work_r2 import TABLE,choose,Q
from state import guard,save
import check_wide_cpp_r4 as host

BUILD=Path.home()/'fpga_builds/g2_v5_decoder_work_r2'
CNN=Path.home()/'fpga_builds/g2_roi_v5_epoch08_output32_r2'
BASE=Path.home()/'fpga_builds/g2_roi_decoder_r1'
FIELDS=['sx','sy','ox','oy','u','v','mx','my','use_motion','rx','ry','rw','rh','use_association']


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def pack(fields):
    c,h,w=fields.shape;padded=np.zeros((24,h,w),np.int32);padded[:c]=fields
    return padded.reshape(3,8,h,w).transpose(0,2,3,1).copy().reshape(-1)


def unpack(raw,heads):
    result=[];cursor=0
    for head in heads:
        _,c,h,w=head['shape_bchw'];n=24*h*w
        result.append(raw[cursor:cursor+n].reshape(3,h,w,8).transpose(0,3,1,2).reshape(24,h,w)[:21]);cursor+=n
    return result


def main():
    if BUILD.exists():raise RuntimeError('Existing new decoder attempt preserved')
    guard();torch.set_num_threads(1)
    if not json.loads((ROOT/'shared_engine/V5_R2_ACTUAL_RTL.json').read_text())['rtl_passed']:raise RuntimeError('Actual full trained V5 raw-head numerical proof required')
    program=json.loads((CNN/'program.json').read_text());heads=program['heads'];meta=json.loads((CNN/'QUANTIZED_MODEL_METADATA.json').read_text());checkpoint=Path(meta['checkpoint'])
    if sha(checkpoint)!=meta['checkpoint_sha256']:raise RuntimeError('Actual V5 checkpoint changed')
    snap=torch.load(checkpoint,map_location='cpu',weights_only=False);seed=torch.load(ROOT/snap['config']['seed_checkpoint'],map_location='cpu',weights_only=False)
    anchors=np.array(seed['config']['anchors']).reshape(2,3,2);aq=np.rint(anchors*Q).astype(np.int64);del snap,seed
    if [h['shape_bchw'] for h in heads]!=[[1,21,48,64],[1,21,24,32]]:raise RuntimeError('Unexpected actual V5 packing')
    if not np.array_equal(TABLE,np.load(BASE/'sigmoid_lut.npy')):raise RuntimeError('Prepared LUT definitions differ')
    BUILD.mkdir()
    for name in ['decoder_work_r2.h','decoder_work_r2.cpp']:shutil.copy2(HERE/name,BUILD/name)
    shutil.copy2(BASE/'sigmoid_lut.h',BUILD/'sigmoid_lut.h')
    header='#pragma once\n#define DECODER_FEATURE_WORDS '+str(program['feature_ddr_words'])+'\n'
    for name,values in [('HEAD_WIDTH',[h['shape_bchw'][3] for h in heads]),('HEAD_HEIGHT',[h['shape_bchw'][2] for h in heads]),('HEAD_OFFSET',[h['offset_words'] for h in heads]),('HEAD_STRIDE',[4,8])]:header+='static const int '+name+'[2]={'+','.join(map(str,values))+'};\n'
    header+='static const unsigned int ANCHOR_Q16[2][3][2]={'+','.join('{'+','.join('{'+','.join(map(str,pair))+'}' for pair in row)+'}' for row in aq)+'};\n';(BUILD/'model_shape.h').write_text(header)
    length=sum(24*h['shape_bchw'][2]*h['shape_bchw'][3] for h in heads);actual=np.fromfile(CNN/'engine_results.bin',np.int32)
    if actual.size!=3*length:raise RuntimeError('Need all actual3wholeV5hostrawvectors')
    cases=list(actual.reshape(3,length));rng=np.random.default_rng(20261022)
    for kind in range(5):
        levels=[]
        for level,head in enumerate(heads):
            _,_,h,w=head['shape_bchw'];fields=np.zeros((21,h,w),np.int32)
            for anchor in range(3):fields[anchor*7+4]=-8*16384
            if kind==0:
                if level==0:fields[11,17,22]=4*16384
                else:fields[18,15,30]=5*16384
            elif kind==1:
                # Candidate-index order differs from the pixel-major C++ scan.
                if level==0:fields[4,30,45]=6*16384;fields[11,2,3]=6*16384
            elif kind==2:
                if level==0:fields[7:12,17,22]=np.array([-12,12,-12,12,26])*16384
                else:fields[14:19,15,30]=np.array([12,-12,12,-12,25])*16384
            elif kind==3:
                fields=rng.integers(-12*16384,12*16384+1,(21,h,w),dtype=np.int32)
            else:
                if level==0:fields[4,0,0]=2*16384;fields[0,0,0]=-12*16384
            levels.append(pack(fields))
        cases.append(np.concatenate(levels))
    identity=dict(zip(FIELDS,[Q,Q,0,0,0,0,8*Q,8*Q,0,0,0,0,0,0]));configs=[]
    def add(**updates):configs.append({**identity,**updates})
    add();add(u=90*Q,v=70*Q,use_motion=1);add(rx=90*Q,ry=70*Q,rw=round(16.4*Q),rh=round(11.6*Q),use_association=1)
    add(u=90*Q,v=70*Q,use_motion=1,rx=90*Q,ry=70*Q,rw=round(16.4*Q),rh=round(11.6*Q),use_association=1)
    add(rx=10000*Q,ry=-10000*Q,rw=20*Q,rh=10*Q,use_association=1)
    add(sx=round(.31234*Q),sy=round(.31789*Q),ox=250*Q,oy=140*Q)
    add(sx=round(.31234*Q),sy=round(.31789*Q),ox=250*Q,oy=140*Q,rx=round(278.11*Q),ry=round(162.25*Q),rw=6*Q,rh=4*Q,use_association=1)
    add(sx=1,sy=1,ox=-20000*Q,oy=20000*Q,rx=20000*Q,ry=-20000*Q,rw=4*Q,rh=4*Q,use_association=1)
    add(sx=Q*1000,sy=Q*1000,ox=20000*Q,oy=-20000*Q)
    add(rx=90*Q,ry=70*Q,rw=0,rh=10*Q,use_association=1)
    add(rx=90*Q,ry=70*Q,rw=1,rh=1,use_association=1);add(sx=0)
    np.stack(cases).tofile(BUILD/'cases.bin');(BUILD/'queries.txt').write_text('\n'.join(' '.join(map(str,[i,*[cfg[k] for k in FIELDS]])) for i,cfg in enumerate(configs))+'\n')
    cpp='''#include "decoder_work_r2.h"
#include "model_shape.h"
#include <fstream>
#include <vector>
#include <cstdint>
int main(){
 const int count=24*(HEAD_WIDTH[0]*HEAD_HEIGHT[0]+HEAD_WIDTH[1]*HEAD_HEIGHT[1]);
 std::ifstream input("cases.bin",std::ios::binary);std::ofstream out("decoder_results.csv");
 if(!input||!out)return 2;
 std::vector<int32_t> raw(count);std::vector<DecoderWord> memory(DECODER_FEATURE_WORDS);
 for(int frame=0;frame<8;frame++){
  input.read((char*)raw.data(),count*4);if(input.gcount()!=count*4)return 3;
  int cursor=0;
  for(int level=0;level<2;level++)for(int word=0;word<3*HEAD_WIDTH[level]*HEAD_HEIGHT[level];word++){
   DecoderWord packed=0;for(int n=0;n<8;n++)packed.range(n*32+31,n*32)=ap_uint<32>(raw[cursor++]);memory[HEAD_OFFSET[level]+word]=packed;
  }
  std::ifstream queries("queries.txt");int id;DecodeConfig cfg;
  while(queries>>id>>cfg.sx>>cfg.sy>>cfg.ox>>cfg.oy>>cfg.u>>cfg.v>>cfg.mx>>cfg.my>>cfg.use_motion>>cfg.rx>>cfg.ry>>cfg.rw>>cfg.rh>>cfg.use_association){
   Candidate best;decode_work_heads(memory.data(),cfg,best);
   out<<frame<<","<<id<<","<<best.x.to_int()<<","<<best.y.to_int()<<","<<best.w.to_int()<<","<<best.h.to_int()<<","<<best.confidence.to_uint()<<","<<best.raw_objectness.to_int()<<","<<best.index.to_uint()<<","<<best.valid.to_uint()<<"\\n";
  }
 }
 return 0;
}
''';(BUILD/'test_decoder.cpp').write_text(cpp)
    plan={'cnn_build':str(CNN),'actual_trained_checkpoint_sha256':sha(checkpoint),'heads':heads,'anchor_q16':aq.tolist(),'queries':configs,'cases':['actualV5zero','actualV5checker','actualV5TRAINimage','motion_distractor','raw_logit_ties','wide_saturation_zero_sides','deterministic_random','negative_roi_offset'],'geometry':'IntegerQ16 ROI-to640workmapping/nearestties-even, quarter/fourfold sizeassociation, squaredradiusmax8px/1.5diag (no sqrt), motionpeak8pxmargin; allgatesBEFORE rawranking.','scope':'Componentnumericgate only. Not HLS/RTL/fullnativequantizedquality/wholecamera-system or accuracy claim.'};save(BUILD/'PREPARED.json',plan)
    host.BUILD=BUILD;host.run('compile_decoder_work',[r'C:\msys64\ucrt64\bin\g++.exe','-std=c++14','-O2',r'-IC:\AMDDesignTools\2026.1\Vitis\include','decoder_work_r2.cpp','test_decoder.cpp','-o','test_decoder.exe'],300);host.run('run_decoder_work',[str(BUILD/'test_decoder.exe')],300)
    observed=np.loadtxt(BUILD/'decoder_results.csv',delimiter=',',dtype=np.int64);expected=[]
    for i,case in enumerate(cases):
        decoded=unpack(case,heads)
        for j,cfg in enumerate(configs):
            best=choose(decoded,aq,[4,8],cfg) if cfg['sx']>0 and cfg['sy']>0 else {'box_q16':[0]*4,'confidence_q16':0,'raw_objectness':-8388608,'index':0,'valid':0}
            expected.append([i,j,*best['box_q16'],best['confidence_q16'],best['raw_objectness'],best['index'],best['valid']])
    expected=np.array(expected,np.int64);np.save(BUILD/'expected_results.npy',expected);passed=observed.shape==expected.shape and np.array_equal(observed,expected)
    result={'passed':bool(passed),'cases':len(cases),'queries':len(expected),'compared_integer_fields':expected[:,2:].size,'different_fields':int((observed[:,2:]!=expected[:,2:]).sum()) if observed.shape==expected.shape else None,'source_sha256':{n:sha(BUILD/n) for n in ['decoder_work_r2.cpp','decoder_work_r2.h','model_shape.h','sigmoid_lut.h','test_decoder.cpp']},'scope':'Actual Vitis ap_int host decoder vs independent NumPy integer reference,3actualfullV5CNNrawvectors+5syntheticcases/12configs, includinggatesbeforemax/rawties/signedmappedcoords/overflowboundaries. No HLS/RTL/nativequality/boardproof.'};save(BUILD/'HOST_CHECK.json',result);print(json.dumps(result,indent=2))
    if not passed:raise RuntimeError('New decoder actual integer outputs differ; inspect no identical retry')


if __name__=='__main__':main()
