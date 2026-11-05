#include "cnn_engine.h"
#include "program.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <vector>
static void read_words(const char* path,Word* out,int count) {
    std::ifstream file(path,std::ios::binary);
    if(!file)throw std::runtime_error("Missing input binary");
    for(int i=0;i<count;i++) {
        uint64_t lo,hi;file.read((char*)&lo,8);file.read((char*)&hi,8);
        if(!file)throw std::runtime_error("Truncated binary");
        out[i].range(63,0)=lo;out[i].range(127,64)=hi;
    }
}
static void write_words(std::ofstream& file,Word* in,int count) {
    for(int i=0;i<count;i++) {
        uint64_t lo=ap_uint<64>(in[i].range(63,0)).to_uint64(),hi=ap_uint<64>(in[i].range(127,64)).to_uint64();
        file.write((char*)&lo,8);file.write((char*)&hi,8);
    }
}
int main() {
    std::vector<Word> memory(FEATURE_WORDS),coefficients(COEFFICIENT_WORDS);
    read_words("coefficients.bin",coefficients.data(),COEFFICIENT_WORDS);
    std::ofstream results("engine_results.bin",std::ios::binary);
    #ifdef RTL_SIM
    const int first=2,last=3; // one REAL TRAIN frame, still the COMPLETE CNN program
    #else
    const int first=0,last=3;
    #endif
    for(int frame=first;frame<last;frame++) {
        for(int i=0;i<FEATURE_WORDS;i++)memory[i]=0;
        std::string input="input_"+std::to_string(frame)+".bin";read_words(input.c_str(),memory.data(),INPUT_WORDS);
        std::cout<<"Complete CNN shared-engine test frame "<<frame<<std::endl;
        cnn_engine(memory.data(),coefficients.data());
        write_words(results,memory.data()+HEAD0_OFFSET,HEAD0_WORDS);
        write_words(results,memory.data()+HEAD1_OFFSET,HEAD1_WORDS);
    }
    std::cout<<"Complete CNN program executed; compare saved raw outputs with fixed-point reference."<<std::endl;
}
