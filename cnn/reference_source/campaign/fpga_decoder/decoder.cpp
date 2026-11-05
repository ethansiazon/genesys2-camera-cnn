#include "decoder.h"
#include "model_shape.h"
#include "sigmoid_lut.h"

static ap_uint<17> sigmoid_q(ap_int<24> raw) {
    #pragma HLS INLINE off
    #pragma HLS BIND_STORAGE variable=SIGMOID_LUT type=rom_2p impl=bram
    const int z=raw.to_int();
    if(z<=-196608)return 0;
    if(z>=196608)return 65536;
    return SIGMOID_LUT[(z+196608+32)>>6];
}

static ap_int<24> lane(DecoderWord word,int index) {
    #pragma HLS INLINE
    ap_int<32> physical=word.range(index*32+31,index*32);
    return ap_int<24>(physical);
}

static ap_int<32> width_q(ap_uint<17> probability,unsigned int anchor) {
    #pragma HLS INLINE off
    ap_uint<18> twice=ap_uint<18>(probability)<<1;
    ap_uint<64> product=ap_uint<64>(twice)*ap_uint<64>(twice)*ap_uint<64>(anchor);
    return ap_int<32>((product+(ap_uint<64>(1)<<31))>>32);
}

void decode_heads(const DecoderWord *features,int u_q16,int v_q16,
                  int margin_x_q16,int margin_y_q16,int use_motion_gate,
                  Candidate &best) {
    #pragma HLS INTERFACE m_axi port=features offset=slave bundle=feature_ddr depth=DECODER_FEATURE_WORDS max_read_burst_length=32 num_read_outstanding=1
    #pragma HLS INTERFACE s_axilite port=features bundle=control
    #pragma HLS INTERFACE s_axilite port=u_q16 bundle=control
    #pragma HLS INTERFACE s_axilite port=v_q16 bundle=control
    #pragma HLS INTERFACE s_axilite port=margin_x_q16 bundle=control
    #pragma HLS INTERFACE s_axilite port=margin_y_q16 bundle=control
    #pragma HLS INTERFACE s_axilite port=use_motion_gate bundle=control
    #pragma HLS INTERFACE s_axilite port=best bundle=control
    #pragma HLS INTERFACE s_axilite port=return bundle=control
    #pragma HLS ALLOCATION instances=sigmoid_q limit=1 function
    #pragma HLS ALLOCATION instances=width_q limit=1 function
    best.x=0;best.y=0;best.w=0;best.h=0;best.confidence=0;
    best.raw_objectness=-8388608;best.index=0;best.valid=0;
    int head_base=0;
    for(int level=0;level<2;level++) {
        const int nx=HEAD_WIDTH[level],ny=HEAD_HEIGHT[level],cells=nx*ny;
        for(int pixel=0;pixel<cells;pixel++) {
            DecoderWord words[3];
            #pragma HLS ARRAY_PARTITION variable=words complete
            for(int group=0;group<3;group++)words[group]=features[HEAD_OFFSET[level]+group*cells+pixel];
            ap_int<24> fields[24];
            #pragma HLS ARRAY_PARTITION variable=fields complete
            for(int channel=0;channel<24;channel++) {
                #pragma HLS UNROLL
                fields[channel]=lane(words[channel/8],channel%8);
            }
            for(int anchor=0;anchor<3;anchor++) {
                const int c=anchor*7;
                ap_int<24> raw=fields[c+4];
                const int key=head_base+anchor*cells+pixel;
                // Ranking raw logits avoids quantized-probability ties. This is
                // monotonic mathematical sigmoid ranking, not guaranteed bit-for-
                // bit float32saturationtie behavior; full quality still mandatory.
                if(best.valid && (raw<best.raw_objectness || (raw==best.raw_objectness && key>=best.index)))continue;
                const int px=sigmoid_q(fields[c]).to_uint();
                const int py=sigmoid_q(fields[c+1]).to_uint();
                const ap_int<32> x=(2*px-32768+(pixel%nx)*65536)*HEAD_STRIDE[level];
                const ap_int<32> y=(2*py-32768+(pixel/nx)*65536)*HEAD_STRIDE[level];
                const ap_int<32> w=width_q(sigmoid_q(fields[c+2]),ANCHOR_Q16[level][anchor][0]);
                const ap_int<32> h=width_q(sigmoid_q(fields[c+3]),ANCHOR_Q16[level][anchor][1]);
                const ap_int<33> dx=ap_int<33>(x)-u_q16,dy=ap_int<33>(y)-v_q16;
                const ap_int<33> mx=ap_int<33>(w/2)+margin_x_q16,my=ap_int<33>(h/2)+margin_y_q16;
                if(use_motion_gate && (dx>mx || dx< -mx || dy>my || dy< -my))continue;
                best.x=x;best.y=y;best.w=w;best.h=h;
                best.raw_objectness=raw;best.index=key;best.valid=1;
            }
        }
        head_base+=3*cells;
    }
    if(best.valid)best.confidence=sigmoid_q(best.raw_objectness);
}
