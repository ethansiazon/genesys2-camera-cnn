#include "decoder_work_r2.h"
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
   out<<frame<<","<<id<<","<<best.x.to_int()<<","<<best.y.to_int()<<","<<best.w.to_int()<<","<<best.h.to_int()<<","<<best.confidence.to_uint()<<","<<best.raw_objectness.to_int()<<","<<best.index.to_uint()<<","<<best.valid.to_uint()<<"\n";
  }
 }
 return 0;
}
