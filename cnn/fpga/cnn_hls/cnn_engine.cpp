// New implementation inspired by channel/spatial tiling in the MIT-licensed
// dhm2013724/yolov2_xilinx_fpga (pinned reference saved alongside campaign).
// No unverified manual ping-pong or false dependence directives are inherited.
#include "cnn_engine.h"
#include "program.h"

static ap_int<24> lane(FeatureWord word,int n) {
    #pragma HLS INLINE
    ap_int<24> value;value.range(23,0)=word.range(n*32+23,n*32);return value;
}
static ap_int<16> coefficient_lane(Word word,int n) {
    #pragma HLS INLINE
    ap_int<16> value;value.range(15,0)=word.range(n*16+15,n*16);return value;
}
static ap_int<24> saturate(ap_int<48> value) {
    #pragma HLS INLINE
    if(value>8388607)return 8388607;
    if(value< -8388608)return -8388608;
    return ap_int<24>(value);
}
static ap_int<24> rounded(ap_int<48> value,int shift,bool relu) {
    #pragma HLS INLINE
    ap_int<48> base=value>>shift;
    ap_uint<48> remainder=ap_uint<48>(value-(base<<shift));
    ap_uint<48> half=ap_uint<48>(1)<<(shift-1);
    if(remainder>half || (remainder==half && base[0]))base++;
    if(relu && base<0)base=0;
    return saturate(base);
}

static void convolve(FeatureWord* memory,const Word* coefficients,Op op) {
    #pragma HLS INLINE off
    ap_int<24> input[8][18][18];
    ap_int<16> weight[32][8][9];
    ap_int<48> accum[32][64];
    #pragma HLS ARRAY_PARTITION variable=input complete dim=1
    #pragma HLS ARRAY_PARTITION variable=weight complete dim=1
    #pragma HLS ARRAY_PARTITION variable=weight complete dim=2
    #pragma HLS ARRAY_PARTITION variable=accum complete dim=1
    #pragma HLS BIND_STORAGE variable=input type=ram_1p impl=bram
    #pragma HLS BIND_STORAGE variable=weight type=ram_1p impl=lutram
    #pragma HLS BIND_STORAGE variable=accum type=ram_s2p impl=lutram
    Word cached_weights[32][144];
    #pragma HLS ARRAY_PARTITION variable=cached_weights complete dim=1
    #pragma HLS BIND_STORAGE variable=cached_weights type=ram_1p impl=bram
    const int ci_blocks=(op.ic+7)/8,co_blocks=(op.oc+7)/8;
    const int fraction=(14+op.q>14)?14+op.q:14;
    const int product_shift=fraction-14-op.q,bias_shift=fraction-14;
OutputGroupsCached:
    for(int mo=0;mo<op.oc;mo+=32) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=4
    CacheOutputSubgroups:
        for(int half=0;half<2;half++) {
            #pragma HLS LOOP_TRIPCOUNT min=2 max=2
            if(mo+half*16<op.oc) {
            CacheOutputGroupWeights:
                for(int slot=0;slot<ci_blocks*op.k*op.k;slot++) {
                    #pragma HLS LOOP_TRIPCOUNT min=1 max=144
                    for(int m=0;m<16;m++) {
                        #pragma HLS PIPELINE II=1
                        cached_weights[half*16+m][slot]=coefficients[op.wo+(((mo/16)+half)*ci_blocks*op.k*op.k+slot)*16+m];
                    }
                }
            }
        }
                ap_int<48> bias[32];
                #pragma HLS ARRAY_PARTITION variable=bias complete
                for(int m=0;m<32;m++) {
                    #pragma HLS PIPELINE II=1
                    const int channel=mo+m;ap_int<32> code=0;
                    if(channel<op.oc) {Word word=coefficients[op.bo+channel/4];code.range(31,0)=word.range((channel%4)*32+31,(channel%4)*32);}
                    bias[m]=ap_int<48>(code)<<bias_shift;
                }
TileRows:
    for(int ty=0;ty<op.oh;ty+=8) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=36
    TileCols:
        for(int tx=0;tx<op.ow;tx+=8) {
            #pragma HLS LOOP_TRIPCOUNT min=1 max=48
            const int tr=(op.oh-ty<8)?op.oh-ty:8;
            const int tc=(op.ow-tx<8)?op.ow-tx:8;
            const int ir=(tr-1)*op.s+op.k,ic=(tc-1)*op.s+op.k;
                for(int pos=0;pos<64;pos++) {
                    #pragma HLS PIPELINE II=1
                    for(int m=0;m<32;m++) {
                        #pragma HLS UNROLL
                        accum[m][pos]=bias[m];
                    }
                }
            InputGroups:
                for(int ni=0;ni<ci_blocks;ni++) {
                    #pragma HLS LOOP_TRIPCOUNT min=1 max=16
                    const bool has_padding=(tx*op.s-op.p<0 || ty*op.s-op.p<0 ||
                        tx*op.s-op.p+ic>op.iw || ty*op.s-op.p+ir>op.ih);
                    if(has_padding) {
                ClearInputRows:
                    for(int y=0;y<ir;y++)for(int x=0;x<ic;x++) {
                        #pragma HLS PIPELINE II=1
                        for(int n=0;n<8;n++) {
                            #pragma HLS UNROLL
                            input[n][y][x]=0;
                        }
                    }
                    }
                    const int source_x=tx*op.s-op.p;
                    const int valid_left=source_x<0?-source_x:0;
                    const int valid_right=(ic<op.iw-source_x)?ic:op.iw-source_x;
                LoadValidRows:
                    for(int y=0;y<ir;y++) {
                        #pragma HLS LOOP_TRIPCOUNT min=1 max=17
                        const int sy=ty*op.s+y-op.p;
                        if(sy>=0 && sy<op.ih && valid_right>valid_left) {
                            const int base=op.a+(ni*op.ih+sy)*op.iw+source_x+valid_left;
                            const int length=valid_right-valid_left;
                        LoadValidSpan:
                            for(int x=0;x<length;x++) {
                                #pragma HLS LOOP_TRIPCOUNT min=1 max=17
                                #pragma HLS PIPELINE II=1
                                FeatureWord word=memory[base+x];
                                for(int n=0;n<8;n++) {
                                    #pragma HLS UNROLL
                                    input[n][y][valid_left+x]=lane(word,n);
                                }
                            }
                        }
                    }
                LoadCachedKernel:
                    for(int kk=0;kk<op.k*op.k;kk++) {
                        #pragma HLS LOOP_TRIPCOUNT min=1 max=9
                        #pragma HLS PIPELINE II=1
                        for(int m=0;m<32;m++) {
                            #pragma HLS UNROLL
                            Word word=(mo+m<op.oc)?cached_weights[m][ni*op.k*op.k+kk]:Word(0);
                            for(int n=0;n<8;n++) {
                                #pragma HLS UNROLL
                                weight[m][n][kk]=coefficient_lane(word,n);
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
                                    ap_int<24> values[8];
                                    #pragma HLS ARRAY_PARTITION variable=values complete
                                    for(int n=0;n<8;n++) {
                                        #pragma HLS UNROLL
                                        values[n]=input[n][y*op.s+ky][x*op.s+kx];
                                    }
                                    for(int m=0;m<32;m++) {
                                        #pragma HLS UNROLL
                                        ap_int<40> products[8];
                                        #pragma HLS ARRAY_PARTITION variable=products complete
                                        for(int n=0;n<8;n++) {
                                            #pragma HLS UNROLL
                                            products[n]=values[n]*weight[m][n][ky*op.k+kx];
                                        }
                                        ap_int<41> a=ap_int<41>(products[0])+products[1],b=ap_int<41>(products[2])+products[3];
                                        ap_int<41> c=ap_int<41>(products[4])+products[5],d=ap_int<41>(products[6])+products[7];
                                        ap_int<42> ab=ap_int<42>(a)+b,cd=ap_int<42>(c)+d;
                                        ap_int<43> total=ap_int<43>(ab)+cd;
                                        accum[m][pos]+=ap_int<48>(total)<<product_shift;
                                    }
                                }
                            }
                        }
                    }
                }
                for(int group=0;group<4;group++)for(int y=0;y<tr;y++)for(int x=0;x<tc;x++) {
                    #pragma HLS PIPELINE II=1
                    FeatureWord word=0;const int cb=mo/8+group;
                    for(int n=0;n<8;n++) {
                        #pragma HLS UNROLL
                        const int channel=mo+group*8+n;
                        ap_int<24> value=channel<op.oc?rounded(accum[group*8+n][y*8+x],fraction-14,op.relu!=0):ap_int<24>(0);
                        ap_int<32> packed=value;word.range(n*32+31,n*32)=packed.range(31,0);
                    }
                    if(cb<co_blocks)memory[op.o+(cb*op.oh+ty+y)*op.ow+tx+x]=word;
                }
            }
        }
    }
}

static void vector_operation(FeatureWord* memory,Op op) {
    #pragma HLS INLINE off
    FeatureWord first[64],second[64],even[128],odd[128];
    #pragma HLS BIND_STORAGE variable=first type=ram_2p impl=bram
    #pragma HLS BIND_STORAGE variable=second type=ram_2p impl=bram
    #pragma HLS BIND_STORAGE variable=even type=ram_2p impl=bram
    #pragma HLS BIND_STORAGE variable=odd type=ram_2p impl=bram
    const int blocks=(op.oc+7)/8;
    if(op.kind==6) {
        for(int y=0;y<op.oh;y++)for(int tx=0;tx<op.ow;tx+=64) {
            const int length=(op.ow-tx<64)?op.ow-tx:64;
            const int row0=op.a+(y*2)*op.iw+tx*2,row1=row0+op.iw;
            for(int x=0;x<2*length;x++) {
                #pragma HLS PIPELINE II=1
                even[x]=memory[row0+x];
            }
            for(int x=0;x<2*length;x++) {
                #pragma HLS PIPELINE II=1
                odd[x]=memory[row1+x];
            }
            for(int c=0;c<blocks;c++) {
                const int destination=op.o+(c*op.oh+y)*op.ow+tx;
                for(int x=0;x<length;x++) {
                    #pragma HLS PIPELINE II=1
                    FeatureWord p00=even[x*2],p01=even[x*2+1],p10=odd[x*2],p11=odd[x*2+1],word=0;
                    for(int n=0;n<8;n++) {
                        #pragma HLS UNROLL
                        const int channel=c*8+n,source=channel/4;FeatureWord pixel;
                        if(channel%4==0)pixel=p00;else if(channel%4==1)pixel=p01;else if(channel%4==2)pixel=p10;else pixel=p11;
                        ap_int<24> value=source<op.ic?lane(pixel,source):ap_int<24>(0);
                        ap_int<32> packed=value;word.range(n*32+31,n*32)=packed.range(31,0);
                    }
                    memory[destination+x]=word;
                }
            }
        }
        return;
    }
    for(int c=0;c<blocks;c++)for(int y=0;y<op.oh;y++)for(int tx=0;tx<op.ow;tx+=64) {
        const int length=(op.ow-tx<64)?op.ow-tx:64;
        if(op.kind==4) {
            const int base=op.a+(c*op.ih+y/2)*op.iw+tx/2;
            for(int x=0;x<(length+1)/2;x++) {
                #pragma HLS PIPELINE II=1
                first[x]=memory[base+x];
            }
        } else {
            const int left=(op.ic+7)/8;
            const int base=op.kind==3 && c>=left?op.b+((c-left)*op.oh+y)*op.ow+tx:op.a+(c*op.oh+y)*op.ow+tx;
            for(int x=0;x<length;x++) {
                #pragma HLS PIPELINE II=1
                first[x]=memory[base+x];
            }
            if(op.kind==2) {
                const int other=op.b+(c*op.oh+y)*op.ow+tx;
                for(int x=0;x<length;x++) {
                    #pragma HLS PIPELINE II=1
                    second[x]=memory[other+x];
                }
            }
        }
        const int destination=op.o+(c*op.oh+y)*op.ow+tx;
        for(int x=0;x<length;x++) {
            #pragma HLS PIPELINE II=1
            FeatureWord word;
            if(op.kind==4)word=first[x/2];
            else if(op.kind==3)word=first[x];
            else {
                FeatureWord a=first[x],b=op.kind==2?second[x]:FeatureWord(0);word=0;
                for(int n=0;n<8;n++) {
                    #pragma HLS UNROLL
                    ap_int<48> value=lane(a,n);
                    if(op.kind==2)value+=lane(b,n);
                    if(op.kind==5 && value<0)value=0;
                    ap_int<24> q=saturate(value);ap_int<32> packed=q;word.range(n*32+31,n*32)=packed.range(31,0);
                }
            }
            memory[destination+x]=word;
        }
    }
}

void cnn_engine(FeatureWord* features,const Word* coefficients) {
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
