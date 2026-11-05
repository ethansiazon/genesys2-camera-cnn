"""Guarded host gates for full Nano and signed SiLU/SPPF edge cases."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import environment
import hashlib,json
import numpy as np,torch
from nano_fixed_r1 import LutSiLU
from state import guard,save,status
import check_wide_cpp_r4 as host

BUILD=Path.home()/'fpga_builds/g2_yolov5n_initial_silu_r1'


def main():
    if (BUILD/'HOST_NUMERICAL_CHECK.json').exists():raise RuntimeError('Existing host attempt preserved')
    guard();torch.set_num_threads(2);host.BUILD=BUILD
    prepared=json.loads((BUILD/'PREPARED.json').read_text())
    for name,digest in prepared['source_hashes'].items():
        if hashlib.sha256((BUILD/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Prepared source changed:'+name)
    result={'status':'running','passed':False,'scope':'Complete initialized Nano 88 instructions, 3 heads; actual Vitis ap_int host arithmetic, not HLS/RTL/fit/drone accuracy.'}
    save(BUILD/'HOST_NUMERICAL_CHECK.json',result)
    try:
        # Exhaustive LUT transition interval plus far tails/random full A24 range.
        rng=np.random.default_rng(20261021)
        codes=np.unique(np.concatenate((np.arange(-196608,196609,dtype=np.int32),rng.integers(-8388608,8388608,4096,dtype=np.int32),np.array([-8388608,-8388607,-196609,-33,-32,-1,0,1,32,33,196609,8388606,8388607],np.int32))))
        codes.tofile(BUILD/'primitive_input.bin')
        src='''#include "cnn_engine.cpp"
#include <fstream>
#include <cstdint>
#include <vector>
int main(){
 std::ifstream input("primitive_input.bin",std::ios::binary);
 std::ofstream out("primitive_output.bin",std::ios::binary);
 int32_t code;
 while(input.read((char*)&code,4))for(int n=0;n<8;n++){
  int32_t actual=activated_round(ap_int<48>(code)*256,8,2,n).to_int();
  out.write((char*)&actual,4);
 }
 // All-negative and mixed-sign border pools, including incomplete channel pack.
 for(int trial=0;trial<2;trial++){
  const int C=9,H=3,W=4,WORDS=2*H*W;
  std::vector<FeatureWord> memory(WORDS*2);
  for(int cb=0;cb<2;cb++)for(int y=0;y<H;y++)for(int x=0;x<W;x++){
   FeatureWord word=0;
   for(int n=0;n<8;n++){
    int c=cb*8+n;int32_t v=c<C?-1000+c*11+y*7+x:0;
    if(trial && c<C)v=(y==1 && x==2)?100+c:-3000;
    ap_int<32> p=v;word.range(n*32+31,n*32)=p.range(31,0);
   }
   memory[(cb*H+y)*W+x]=word;
  }
  Op op={};op.kind=7;op.a=0;op.o=WORDS;op.ih=op.oh=H;op.iw=op.ow=W;op.ic=op.oc=C;
  maxpool5(memory.data(),op);
  for(int cb=0;cb<2;cb++)for(int y=0;y<H;y++)for(int x=0;x<W;x++)for(int n=0;n<8;n++){
   int32_t v=lane(memory[WORDS+(cb*H+y)*W+x],n).to_int();out.write((char*)&v,4);
  }
 }
 return 0;
}
'''
        (BUILD/'primitive_test.cpp').write_text(src)
        host.run('primitive_compile',[r'C:\msys64\ucrt64\bin\g++.exe','-std=c++14','-O2',r'-IC:\AMDDesignTools\2026.1\Vitis\include','primitive_test.cpp','-o','primitive_test.exe'],300)
        host.run('primitive_run',[str(BUILD/'primitive_test.exe')],180)
        values=np.fromfile(BUILD/'primitive_output.bin',np.int32);raw=torch.from_numpy(codes.astype(np.int64))
        with torch.no_grad():expected=torch.round(LutSiLU()(raw.double()/16384)*16384).numpy().astype(np.int32)
        count=len(codes)*8
        if not np.array_equal(values[:count].reshape(-1,8),np.repeat(expected[:,None],8,axis=1)):raise RuntimeError('Actual signed LUT C++ differs from independent integer reference')
        pools=[]
        for trial in range(2):
            c,y,x=torch.meshgrid(torch.arange(9),torch.arange(3),torch.arange(4),indexing='ij')
            a=(-1000+c*11+y*7+x).double()
            if trial:a=torch.where((y==1)&(x==2),100+c,-3000).double()
            pooled=torch.nn.functional.max_pool2d(a[None],5,1,2)[0].numpy().astype(np.int32)
            padded=np.zeros((16,3,4),np.int32);padded[:9]=pooled
            pools.append(padded.reshape(2,8,3,4).transpose(0,2,3,1).copy().reshape(-1))
        if not np.array_equal(values[count:],np.concatenate(pools)):raise RuntimeError('Signed maxpool padding/channel guard differs')
        approx=np.abs(expected/16384-(raw.double()/16384*torch.sigmoid(raw.double()/16384)).numpy())
        primitive={'passed':True,'distinct_input_codes':len(codes),'all_eight_banks_values':count,'maxpool_border_cases':2,'max_abs_silu_approx_error_on_tested_codes':float(approx.max()),'scope':'Exhaustive all393217 A24 codes from -12 through12, 4096 random full-range codes/tails; all8 physicalbanks. All-negative borderpool proves zero padding would be wrong. TwoC9 cases include invalidlane guard. Not trained quantized quality.'}
        save(BUILD/'PRIMITIVE_CHECK.json',primitive);status('Nano signed SiLU and pool edge checks passed',codes=len(codes),banks=8)
        host.run('host_compile',[r'C:\msys64\ucrt64\bin\g++.exe','-std=c++14','-O2',r'-IC:\AMDDesignTools\2026.1\Vitis\include','cnn_engine.cpp','test_engine.cpp','-o','test_engine.exe'],300)
        host.run('complete_cpp',[str(BUILD/'test_engine.exe')],1200)
        numerical=host.compare();result.update(status='complete' if numerical['passed'] else 'needs_attention',passed=numerical['passed'],primitive=primitive,numerical=numerical)
        save(BUILD/'HOST_NUMERICAL_CHECK.json',result)
        if not numerical['passed']:raise RuntimeError('Full three-head Nano mismatch; diagnose before HLS')
        status('Complete Nano integer host comparison passed',**numerical)
    except BaseException as exc:
        result.update(status='needs_attention',error=str(exc));save(BUILD/'HOST_NUMERICAL_CHECK.json',result);raise


if __name__=='__main__':main()
