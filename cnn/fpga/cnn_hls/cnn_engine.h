#ifndef G2_CNN_ENGINE_H
#define G2_CNN_ENGINE_H
#include "ap_int.h"
typedef ap_uint<128> Word;
typedef ap_uint<256> FeatureWord;
struct Op {
    int kind,a,b,o,ih,iw,ic,oh,ow,oc,k,s,p,wo,bo,q,relu,bc;
};
void cnn_engine(FeatureWord* features,const Word* coefficients);
#endif
