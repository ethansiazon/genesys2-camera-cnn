"""Prepare a VERSIONED wider arithmetic engine; no FPGA compiler or GPU use.
Actual host/RTL/synthesis tests are separate mandatory gates before adoption.
"""
from pathlib import Path
import difflib,hashlib,re

HERE=Path(__file__).resolve().parent
SOURCE=Path.home()/'fpga_builds/g2_shared_engine_20261017_vector_r3'
BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_wide_r4_roi256'

def replace(text,old,new,count=None):
    n=text.count(old)
    if not n or count is not None and n!=count:raise RuntimeError(f'Unexpected source pattern count {n}: {old}')
    return text.replace(old,new)

def main():
    if BUILD.exists():raise RuntimeError('Existing wider engine build preserved')
    original=(SOURCE/'cnn_engine.cpp').read_text();text=original
    helper='''static ap_int<16> lane(Word word,int n) {
    #pragma HLS INLINE
    ap_int<16> value;value.range(15,0)=word.range(n*16+15,n*16);return value;
}'''
    new='''static ap_int<24> lane(FeatureWord word,int n) {
    #pragma HLS INLINE
    ap_int<24> value;value.range(23,0)=word.range(n*32+23,n*32);return value;
}
static ap_int<16> coefficient_lane(Word word,int n) {
    #pragma HLS INLINE
    ap_int<16> value;value.range(15,0)=word.range(n*16+15,n*16);return value;
}'''
    # Transform the original narrow body before injecting the distinct lane helpers.
    text=replace(text,helper,'__LANE_HELPERS__',1)
    text=re.sub(r'\bWord\b','FeatureWord',text)
    text=replace(text,'const FeatureWord* coefficients','const Word* coefficients')
    text=replace(text,'FeatureWord word=coefficients[','Word word=coefficients[')
    text=replace(text,'ap_int<16>','ap_int<24>')
    text=replace(text,'ap_int<12>','ap_int<16>')
    for old,width in [(28,40),(29,41),(30,42),(31,43)]:text=replace(text,f'ap_int<{old}>',f'ap_int<{width}>')
    text=replace(text,'weight[m][n][kk]=ap_int<16>(lane(word,n));','weight[m][n][kk]=coefficient_lane(word,n);',1)
    text=replace(text,'if(value>32767)return 32767;','if(value>8388607)return 8388607;',1)
    text=replace(text,'if(value< -32768)return -32768;','if(value< -8388608)return -8388608;',1)
    text=replace(text,'10+op.q','14+op.q')
    text=replace(text,'fraction-10','fraction-14')
    text=replace(text,'word.range(n*16+15,n*16)=value.range(15,0);','ap_int<32> packed=value;word.range(n*32+31,n*32)=packed.range(31,0);',2)
    text=replace(text,'ap_int<24> q=saturate(value);word.range(n*16+15,n*16)=q.range(15,0);','ap_int<24> q=saturate(value);ap_int<32> packed=q;word.range(n*32+31,n*32)=packed.range(31,0);',1)
    text=text.replace('__LANE_HELPERS__',new)
    header=(SOURCE/'cnn_engine.h').read_text().replace('typedef ap_uint<128> Word;','typedef ap_uint<128> Word;\ntypedef ap_uint<256> FeatureWord;').replace('void cnn_engine(Word* features','void cnn_engine(FeatureWord* features')
    host='''#include "cnn_engine.h"
#include "program.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
template<int B> static void read_words(const char* path,ap_uint<B>* out,int count) {
 std::ifstream file(path,std::ios::binary);if(!file)throw std::runtime_error("Missing input binary");
 for(int i=0;i<count;i++)for(int k=0;k<B/64;k++){uint64_t value;file.read((char*)&value,8);if(!file)throw std::runtime_error("Truncated input");out[i].range(k*64+63,k*64)=value;}
}
template<int B> static void write_words(std::ofstream& file,ap_uint<B>* in,int count) {
 for(int i=0;i<count;i++)for(int k=0;k<B/64;k++){uint64_t value=ap_uint<64>(in[i].range(k*64+63,k*64)).to_uint64();file.write((char*)&value,8);}
}
int main(){
 std::vector<FeatureWord> memory(FEATURE_WORDS);std::vector<Word> coefficients(COEFFICIENT_WORDS);read_words("coefficients.bin",coefficients.data(),COEFFICIENT_WORDS);
 std::ofstream results("engine_results.bin",std::ios::binary);
 #ifdef RTL_SIM
 const int first=2,last=3;
 #else
 const int first=0,last=3;
 #endif
 for(int frame=first;frame<last;frame++){
  for(int i=0;i<FEATURE_WORDS;i++)memory[i]=0;
  std::string input="input_"+std::to_string(frame)+".bin";read_words(input.c_str(),memory.data(),INPUT_WORDS);
  std::cout<<"Wide complete CNN frame "<<frame<<std::endl;cnn_engine(memory.data(),coefficients.data());
  write_words(results,memory.data()+HEAD0_OFFSET,HEAD0_WORDS);write_words(results,memory.data()+HEAD1_OFFSET,HEAD1_WORDS);
 }
 return 0;
}
'''
    BUILD.mkdir();(BUILD/'cnn_engine.cpp').write_text(text);(BUILD/'cnn_engine.h').write_text(header);(BUILD/'test_engine.cpp').write_text(host)
    (BUILD/'SOURCE_CHANGE.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='R3 A16F10 W12',tofile='R4 A24F14 W16')))
    import json
    (BUILD/'SOURCE_PROVENANCE.json').write_text(json.dumps({'parent':str(SOURCE),'parent_cpp_sha256':hashlib.sha256(original.encode()).hexdigest(),'new_cpp_sha256':hashlib.sha256(text.encode()).hexdigest(),
        'scope':'Prepared source only, no compiler/numerical/resource/timing proof. Separate 256bit feature DDR words containing8signextended32bit lanes of signed24F14 activations,128bit coefficient words with8signed16 weights.48bit accumulator,40/41/42/43bit exact product/add tree. Same staged-vector controller and128parallelMACs. See diff; CPP/actualRTL must pass before adoption.'},indent=2))
    print(BUILD)

if __name__=='__main__':main()
