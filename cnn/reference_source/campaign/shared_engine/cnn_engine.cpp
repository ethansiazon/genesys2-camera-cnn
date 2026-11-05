// New implementation inspired by channel/spatial tiling in the MIT-licensed
// dhm2013724/yolov2_xilinx_fpga (pinned reference saved alongside campaign).
// No unverified manual ping-pong or false dependence directives are inherited.
#include "cnn_engine.h"
#include "program.h"

static ap_int<16> lane(Word word,int n) {
    #pragma HLS INLINE
    ap_int<16> value;value.range(15,0)=word.range(n*16+15,n*16);return value;
}
static ap_int<16> saturate(ap_int<48> value) {
    #pragma HLS INLINE
    if(value>32767)return 32767;
    if(value< -32768)return -32768;
    return ap_int<16>(value);
}
static ap_int<16> rounded(ap_int<48> value,int shift,bool relu) {
    #pragma HLS INLINE
    ap_int<48> base=value>>shift;
    ap_uint<48> remainder=ap_uint<48>(value-(base<<shift));
    ap_uint<48> half=ap_uint<48>(1)<<(shift-1);
    if(remainder>half || (remainder==half && base[0]))base++;
    if(relu && base<0)base=0;
    return saturate(base);
}

static void convolve(Word* memory,const Word* coefficients,Op op) {
    #pragma HLS INLINE off
    ap_int<16> input[8][18][18];
    ap_int<12> weight[16][8][9];
    ap_int<48> accum[16][64];
    #pragma HLS ARRAY_PARTITION variable=input complete dim=1
    #pragma HLS ARRAY_PARTITION variable=weight complete dim=1
    #pragma HLS ARRAY_PARTITION variable=weight complete dim=2
    #pragma HLS ARRAY_PARTITION variable=accum complete dim=1
    #pragma HLS BIND_STORAGE variable=input type=ram_1p impl=bram
    #pragma HLS BIND_STORAGE variable=weight type=ram_1p impl=lutram
    #pragma HLS BIND_STORAGE variable=accum type=ram_s2p impl=lutram
    const int ci_blocks=(op.ic+7)/8,co_blocks=(op.oc+7)/8;
    const int fraction=(10+op.q>14)?10+op.q:14;
    const int product_shift=fraction-10-op.q,bias_shift=fraction-14;
TileRows:
    for(int ty=0;ty<op.oh;ty+=8) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=36
    TileCols:
        for(int tx=0;tx<op.ow;tx+=8) {
            #pragma HLS LOOP_TRIPCOUNT min=1 max=48
            const int tr=(op.oh-ty<8)?op.oh-ty:8;
            const int tc=(op.ow-tx<8)?op.ow-tx:8;
            const int ir=(tr-1)*op.s+op.k,ic=(tc-1)*op.s+op.k;
        OutputGroups:
            for(int mo=0;mo<op.oc;mo+=16) {
                #pragma HLS LOOP_TRIPCOUNT min=1 max=8
                ap_int<48> bias[16];
                #pragma HLS ARRAY_PARTITION variable=bias complete
                for(int m=0;m<16;m++) {
                    #pragma HLS PIPELINE II=1
                    const int channel=mo+m;ap_int<32> code=0;
                    if(channel<op.oc) {Word word=coefficients[op.bo+channel/4];code.range(31,0)=word.range((channel%4)*32+31,(channel%4)*32);}
                    bias[m]=ap_int<48>(code)<<bias_shift;
                }
                for(int pos=0;pos<64;pos++) {
                    #pragma HLS PIPELINE II=1
                    for(int m=0;m<16;m++) {
                        #pragma HLS UNROLL
                        accum[m][pos]=bias[m];
                    }
                }
            InputGroups:
                for(int ni=0;ni<ci_blocks;ni++) {
                    #pragma HLS LOOP_TRIPCOUNT min=1 max=16
                LoadRows:
                    for(int y=0;y<ir;y++) {
                        #pragma HLS LOOP_TRIPCOUNT min=1 max=17
                    LoadCols:
                        for(int x=0;x<ic;x++) {
                            #pragma HLS LOOP_TRIPCOUNT min=1 max=17
                            #pragma HLS PIPELINE II=1
                            const int sy=ty*op.s+y-op.p,sx=tx*op.s+x-op.p;
                            Word word=0;
                            if(sy>=0 && sy<op.ih && sx>=0 && sx<op.iw)word=memory[op.a+(ni*op.ih+sy)*op.iw+sx];
                            for(int n=0;n<8;n++) {
                                #pragma HLS UNROLL
                                input[n][y][x]=lane(word,n);
                            }
                        }
                    }
                    for(int kk=0;kk<op.k*op.k;kk++) {
                        #pragma HLS LOOP_TRIPCOUNT min=1 max=9
                        for(int m=0;m<16;m++) {
                            #pragma HLS PIPELINE II=1
                            Word word=coefficients[op.wo+(((mo/16)*ci_blocks+ni)*op.k*op.k+kk)*16+m];
                            for(int n=0;n<8;n++) {
                                #pragma HLS UNROLL
                                weight[m][n][kk]=ap_int<12>(lane(word,n));
                            }
                        }
                    }
                KernelRows:
                    for(int ky=0;ky<op.k;ky++) {
                        #pragma HLS LOOP_TRIPCOUNT min=1 max=3
                    KernelCols:
                        for(int kx=0;kx<op.k;kx++) {
                            #pragma HLS LOOP_TRIPCOUNT min=1 max=3
                        TilePixels:
                            for(int pos=0;pos<64;pos++) {
                                #pragma HLS PIPELINE II=1
                                const int y=pos/8,x=pos%8;
                                if(y<tr && x<tc) {
                                    ap_int<16> values[8];
                                    #pragma HLS ARRAY_PARTITION variable=values complete
                                    for(int n=0;n<8;n++) {
                                        #pragma HLS UNROLL
                                        values[n]=input[n][y*op.s+ky][x*op.s+kx];
                                    }
                                    for(int m=0;m<16;m++) {
                                        #pragma HLS UNROLL
                                        ap_int<28> products[8];
                                        #pragma HLS ARRAY_PARTITION variable=products complete
                                        for(int n=0;n<8;n++) {
                                            #pragma HLS UNROLL
                                            products[n]=values[n]*weight[m][n][ky*op.k+kx];
                                        }
                                        ap_int<29> a=ap_int<29>(products[0])+products[1],b=ap_int<29>(products[2])+products[3];
                                        ap_int<29> c=ap_int<29>(products[4])+products[5],d=ap_int<29>(products[6])+products[7];
                                        ap_int<30> ab=ap_int<30>(a)+b,cd=ap_int<30>(c)+d;
                                        ap_int<31> total=ap_int<31>(ab)+cd;
                                        accum[m][pos]+=ap_int<48>(total)<<product_shift;
                                    }
                                }
                            }
                        }
                    }
                }
                for(int group=0;group<2;group++)for(int y=0;y<tr;y++)for(int x=0;x<tc;x++) {
                    #pragma HLS PIPELINE II=1
                    Word word=0;const int cb=mo/8+group;
                    for(int n=0;n<8;n++) {
                        #pragma HLS UNROLL
                        const int channel=mo+group*8+n;
                        ap_int<16> value=channel<op.oc?rounded(accum[group*8+n][y*8+x],fraction-10,op.relu!=0):ap_int<16>(0);
                        word.range(n*16+15,n*16)=value.range(15,0);
                    }
                    if(cb<co_blocks)memory[op.o+(cb*op.oh+ty+y)*op.ow+tx+x]=word;
                }
            }
        }
    }
}

static void vector_operation(Word* memory,Op op) {
    #pragma HLS INLINE off
    const int blocks=(op.oc+7)/8;
    for(int c=0;c<blocks;c++)for(int y=0;y<op.oh;y++)for(int x=0;x<op.ow;x++) {
        #pragma HLS PIPELINE II=1
        int offset=(c*op.oh+y)*op.ow+x;Word word;
        if(op.kind==3) { // channel concat, all internal input channels multiples of8
            int left=(op.ic+7)/8;word=memory[c<left?op.a+offset:op.b+((c-left)*op.oh+y)*op.ow+x];
        } else if(op.kind==6) { // exact pixel-unshuffle2 of RGB stem
            Word p00=memory[op.a+(y*2)*op.iw+x*2],p01=memory[op.a+(y*2)*op.iw+x*2+1];
            Word p10=memory[op.a+(y*2+1)*op.iw+x*2],p11=memory[op.a+(y*2+1)*op.iw+x*2+1];
            word=0;
            for(int n=0;n<8;n++) {
                #pragma HLS UNROLL
                int channel=c*8+n,source=channel/4;Word pixel;
                if(channel%4==0)pixel=p00;else if(channel%4==1)pixel=p01;else if(channel%4==2)pixel=p10;else pixel=p11;
                ap_int<16> value=source<op.ic?lane(pixel,source):ap_int<16>(0);
                word.range(n*16+15,n*16)=value.range(15,0);
            }
        } else if(op.kind==4) { // integer nearest-neighbour2x
            word=memory[op.a+(c*op.ih+y/2)*op.iw+x/2];
        } else {
            Word a=memory[op.a+offset],b=0;word=0;
            if(op.kind==2)b=memory[op.b+offset];
            for(int n=0;n<8;n++) {
                #pragma HLS UNROLL
                ap_int<48> value=lane(a,n);
                if(op.kind==2)value+=lane(b,n);
                if(op.kind==5 && value<0)value=0;
                ap_int<16> q=saturate(value);word.range(n*16+15,n*16)=q.range(15,0);
            }
        }
        memory[op.o+offset]=word;
    }
}

void cnn_engine(Word* features,const Word* coefficients) {
    #pragma HLS INTERFACE m_axi port=features offset=slave bundle=feature_ddr depth=FEATURE_WORDS max_read_burst_length=64 max_write_burst_length=64 num_read_outstanding=2 num_write_outstanding=2
    #pragma HLS INTERFACE m_axi port=coefficients offset=slave bundle=coefficient_ddr depth=COEFFICIENT_WORDS max_read_burst_length=64 num_read_outstanding=2
    #pragma HLS INTERFACE s_axilite port=features bundle=control
    #pragma HLS INTERFACE s_axilite port=coefficients bundle=control
    #pragma HLS INTERFACE s_axilite port=return bundle=control
    #pragma HLS ALLOCATION function instances=convolve limit=1
Program:
    for(int pc=0;pc<PROGRAM_LENGTH;pc++) {
        #pragma HLS PIPELINE off
        Op op=PROGRAM[pc];
        if(op.kind==1)convolve(features,coefficients,op);
        else vector_operation(features,op);
    }
}
