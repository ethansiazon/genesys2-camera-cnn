"""CPU-only actual Vitis ap_int decoder comparison; no HLS/GPU job.
Independent integer reference, full raw heads from3realCNNtestvectors+synthetics.
"""
import hashlib,json,sys
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT/'shared_engine'))
import check_wide_cpp_r4 as host
BUILD=Path.home()/'fpga_builds/g2_roi_decoder_r1';REPORT=BUILD/'HOST_CHECK.json'

def sigmoid(raw,table):return table[((np.asarray(raw,dtype=np.int64)+196608+32)>>6).clip(0,6144)].astype(np.int64)

def reference(flat,meta,table,query):
    _,u,v,mx,my,gate=query;best=None;offset=0;base=0
    for level,head in enumerate(meta['heads']):
        _,c,h,w=head['shape_bchw'];size=24*h*w;fields=flat[offset:offset+size].reshape(3,h,w,8).transpose(0,3,1,2).reshape(24,h,w).astype(np.int64);offset+=size;yy,xx=np.mgrid[:h,:w];stride=[4,8][level]
        for anchor in range(3):
            z=fields[anchor*7:anchor*7+5];x=(2*sigmoid(z[0],table)-32768+xx*65536)*stride;y=(2*sigmoid(z[1],table)-32768+yy*65536)*stride;a=meta['anchor_q16'][level][anchor];bw=((2*sigmoid(z[2],table))**2*a[0]+2**31)>>32;bh=((2*sigmoid(z[3],table))**2*a[1]+2**31)>>32;allowed=np.ones((h,w),bool) if not gate else (np.abs(x-u)<=bw//2+mx)&(np.abs(y-v)<=bh//2+my);scores=np.where(allowed,z[4],-8388609);pixel=int(scores.argmax());raw=int(scores.flat[pixel]);key=base+anchor*h*w+pixel
            if raw>=-8388608 and (best is None or raw>best[0] or raw==best[0] and key<best[1]):best=(raw,key,int(x.flat[pixel]),int(y.flat[pixel]),int(bw.flat[pixel]),int(bh.flat[pixel]))
        base+=3*h*w
    if best is None:return [0,0,0,0,0,-8388608,0,0]
    raw,key,x,y,w,h=best;return [x,y,w,h,int(sigmoid(raw,table)),raw,key,1]

def main():
    if REPORT.exists():raise RuntimeError('Prior decoder host evidence preserved')
    meta=json.loads((BUILD/'PREPARED.json').read_text());cnn=Path(meta['cnn_build']);table=np.load(BUILD/'sigmoid_lut.npy');heads=meta['heads'];length=sum(24*h['shape_bchw'][2]*h['shape_bchw'][3] for h in heads);actual=np.fromfile(cnn/'engine_results.bin',np.int32)
    if actual.size!=3*length:raise RuntimeError('Need actual3fullCNNhostvectors')
    cases=list(actual.reshape(3,length));synthetic=[]
    for extreme in [False,True]:
        values=[]
        for level,head in enumerate(heads):
            _,c,h,w=head['shape_bchw'];field=np.zeros((24,h,w),np.int32)
            for anchor in range(3):field[anchor*7+4]=-8*16384
            if level==0:
                field[7+4,17,22]=(26 if extreme else 4)*16384
                if extreme:field[7:7+4,17,22]=np.array([12,-12,12,-12])*16384
            else:field[14+4,15,30]=(25 if extreme else 5)*16384
            values.append(field.reshape(3,8,h,w).transpose(0,2,3,1).reshape(-1))
        synthetic.append(np.concatenate(values))
    cases+=synthetic;queries=[[0,128*65536,96*65536,round(25.6*65536),round(25.6*65536),1],[1,0,0,0,0,1],[2,90*65536,70*65536,0,0,1],[3,100000*65536 if False else 100000000,100000000,0,0,1],[4,0,0,0,0,0]]
    np.stack(cases).astype(np.int32).tofile(BUILD/'cases.bin');(BUILD/'queries.txt').write_text('\n'.join(' '.join(map(str,row)) for row in queries)+'\n')
    # A separate translation unit exercises the actual C++ integer data widths,
    # NCHW8 unpacking, allrawheads, gate, ties and no-candidate branch.
    cpp=r'''#include "decoder.h"
#include "model_shape.h"
#include <fstream>
#include <vector>
#include <cstdint>
#include <iostream>
int main(){
 const int count=24*(HEAD_WIDTH[0]*HEAD_HEIGHT[0]+HEAD_WIDTH[1]*HEAD_HEIGHT[1]);
 std::ifstream input("cases.bin",std::ios::binary);std::ofstream output("decoder_results.csv");
 if(!input||!output)return2;
 std::vector<int32_t> raw(count);std::vector<DecoderWord> memory(DECODER_FEATURE_WORDS);
 for(int frame=0;frame<5;frame++){
  input.read(reinterpret_cast<char*>(raw.data()),count*4);if(input.gcount()!=count*4)return3;
  int cursor=0;
  for(int level=0;level<2;level++)for(int word=0;word<3*HEAD_WIDTH[level]*HEAD_HEIGHT[level];word++){
   DecoderWord packed=0;for(int lane=0;lane<8;lane++)packed.range(lane*32+31,lane*32)=ap_uint<32>(raw[cursor++]);
   memory[HEAD_OFFSET[level]+word]=packed;
  }
  std::ifstream queries("queries.txt");int id,u,v,mx,my,gate;
  while(queries>>id>>u>>v>>mx>>my>>gate){
   Candidate best;decode_heads(memory.data(),u,v,mx,my,gate,best);
   output<<frame<<","<<id<<","<<best.x.to_int()<<","<<best.y.to_int()<<","<<best.w.to_int()<<","<<best.h.to_int()<<","<<best.confidence.to_uint()<<","<<best.raw_objectness.to_int()<<","<<best.index.to_uint()<<","<<best.valid.to_uint()<<"\n";
  }
 }
 std::cout<<"FULL_RAW_HEAD_DECODER_HOST_DONE\n";return0;
}
'''.replace('return2','return 2').replace('return3','return 3').replace('return0','return 0');(BUILD/'test_decoder.cpp').write_text(cpp)
    plan={'case_sources':['actualfinalROI11zero','actualfinalROI11RGBXYchecker','actualfinalROI11registeredTRAINimage','syntheticmotiongate_distractor','syntheticwidearithmetic_extremes'],'queries':queries,'scope':'NumericalintegercomponenttestONLY, no modelquality/FPGAresources/timing/boardproof. ActualCNNrawinput provenance retained; syntheticcases notvalidationaccuracy.'};(BUILD/'HOST_TEST_PLAN.json').write_text(json.dumps(plan,indent=2));host.BUILD=BUILD
    host.run('host_compile_decoder',[r'C:\msys64\ucrt64\bin\g++.exe','-std=c++14','-O2',r'-IC:\AMDDesignTools\2026.1\Vitis\include','decoder.cpp','test_decoder.cpp','-o','test_decoder.exe'],300);host.run('host_run_decoder',[str(BUILD/'test_decoder.exe')],300);observed=np.loadtxt(BUILD/'decoder_results.csv',delimiter=',',dtype=np.int64);expected=[]
    for frame,values in enumerate(cases):
        for query in queries:expected.append([frame,query[0],*reference(values,meta,table,query)])
    expected=np.array(expected);passed=observed.shape==expected.shape and np.array_equal(observed,expected);result={'passed':bool(passed),'queries':len(expected),'cases':len(cases),'compared_integer_fields':expected[:,2:].size,'different_fields':int(np.sum(observed[:,2:]!=expected[:,2:])) if observed.shape==expected.shape else None,'lut_max_abs_probability_error':meta['lut_max_abs_probability_error_exhaustive_all393217A24codes_minus12_to12'],'source_sha256':{name:hashlib.sha256((BUILD/name).read_bytes()).hexdigest() for name in ['decoder.cpp','decoder.h','model_shape.h','sigmoid_lut.h','test_decoder.cpp']},'scope':'ActualVitisap_int nativeC++ROIdecoder vsindependentPythonINTEGERreference, all3realCNNrawheadvectors+2synthetics,25queries. NoHLS/RTL/resource/timing or fullquantizedmodelqualityclaim. Sigmoidapproximation/float32saturationties stillrequireendtoendnativevalidation. Nativecamera-coordinateconversion/controller/MIGnotimplemented.'};(BUILD/'HOST_CHECK.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    if not passed:
        np.save(BUILD/'expected_integer_results.npy',expected);raise RuntimeError('Decoderactualintegerparityfailed; inspect savedvalues/noidenticalretry')

if __name__=='__main__':main()
