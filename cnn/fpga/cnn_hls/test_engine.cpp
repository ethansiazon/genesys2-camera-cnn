#include "cnn_engine.h"
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
