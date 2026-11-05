#include "decoder_work_r2.h"
#include "model_shape.h"
#include "sigmoid_lut.h"

static ap_int<24> lane(DecoderWord word,int index) {
 #pragma HLS INLINE
 ap_int<24> raw;raw.range(23,0)=word.range(index*32+23,index*32);return raw;
}
static ap_uint<17> sigmoid_q(ap_int<24> raw) {
 #pragma HLS INLINE off
 #pragma HLS BIND_STORAGE variable=SIGMOID_LUT type=rom_2p impl=bram
 const int z=raw.to_int();if(z<=-196608)return 0;if(z>=196608)return 65536;
 return SIGMOID_LUT[(z+196608+32)>>6];
}
static ap_int<32> width_q(ap_uint<17> probability,unsigned int anchor) {
 #pragma HLS INLINE off
 ap_uint<18> twice=ap_uint<18>(probability)<<1;
 ap_uint<64> product=ap_uint<64>(twice)*ap_uint<64>(twice)*ap_uint<64>(anchor);
 return ap_int<32>((product+(ap_uint<64>(1)<<31))>>32);
}
static ap_int<32> transformed(ap_int<32> input,int multiplier,int offset) {
 #pragma HLS INLINE off
 ap_int<64> product=ap_int<64>(input)*ap_int<64>(multiplier);
 ap_int<64> base=product>>16;ap_uint<16> remainder=product.range(15,0);
 if(remainder>32768 || (remainder==32768 && base[0]))base++;
 base+=offset;
 if(base>2147483647LL)return 2147483647;
 if(base< -2147483648LL)return ap_int<32>(-2147483648LL);
 return ap_int<32>(base);
}

void decode_work_heads(const DecoderWord* features,DecodeConfig cfg,Candidate &best) {
 #pragma HLS INTERFACE m_axi port=features offset=slave bundle=feature_ddr depth=DECODER_FEATURE_WORDS max_read_burst_length=32 num_read_outstanding=1
 #pragma HLS INTERFACE s_axilite port=features bundle=control
 #pragma HLS INTERFACE s_axilite port=cfg bundle=control
 #pragma HLS INTERFACE s_axilite port=best bundle=control
 #pragma HLS INTERFACE s_axilite port=return bundle=control
 #pragma HLS ALLOCATION instances=sigmoid_q limit=1 function
 #pragma HLS ALLOCATION instances=width_q limit=1 function
 #pragma HLS ALLOCATION instances=transformed limit=1 function
 best.x=0;best.y=0;best.w=0;best.h=0;best.confidence=0;best.raw_objectness=-8388608;best.index=0;best.valid=0;
 if(cfg.sx<=0 || cfg.sy<=0 || (cfg.use_association && (cfg.rw<=0 || cfg.rh<=0)))return;
 ap_int<64> rw=cfg.rw,rh=cfg.rh;
 ap_uint<68> radius4=ap_uint<68>(rw*rw)+ap_uint<68>(rh*rh);radius4*=9;
 const ap_uint<68> minimum_radius4=ap_uint<68>(4)*524288*524288;
 if(radius4<minimum_radius4)radius4=minimum_radius4;
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
    const int c=anchor*7,key=head_base+anchor*cells+pixel;ap_int<24> raw=fields[c+4];
    if(best.valid && (raw<best.raw_objectness || (raw==best.raw_objectness && key>=best.index)))continue;
    const int px=sigmoid_q(fields[c]).to_uint(),py=sigmoid_q(fields[c+1]).to_uint();
    const ap_int<32> roi_x=(2*px-32768+(pixel%nx)*65536)*HEAD_STRIDE[level];
    const ap_int<32> roi_y=(2*py-32768+(pixel/nx)*65536)*HEAD_STRIDE[level];
    const ap_int<32> roi_w=width_q(sigmoid_q(fields[c+2]),ANCHOR_Q16[level][anchor][0]);
    const ap_int<32> roi_h=width_q(sigmoid_q(fields[c+3]),ANCHOR_Q16[level][anchor][1]);
    const ap_int<32> x=transformed(roi_x,cfg.sx,cfg.ox),y=transformed(roi_y,cfg.sy,cfg.oy);
    const ap_int<32> w=transformed(roi_w,cfg.sx,0),h=transformed(roi_h,cfg.sy,0);
    if(w<=0 || h<=0)continue;
    if(cfg.use_motion) {
     const ap_int<33> dx=ap_int<33>(x)-cfg.u,dy=ap_int<33>(y)-cfg.v;
     const ap_int<33> mx=ap_int<33>(w/2)+cfg.mx,my=ap_int<33>(h/2)+cfg.my;
     if(dx>mx || dx< -mx || dy>my || dy< -my)continue;
    }
    if(cfg.use_association) {
     if(ap_int<35>(w)*4<cfg.rw || ap_int<35>(h)*4<cfg.rh || ap_int<35>(w)>ap_int<35>(cfg.rw)*4 || ap_int<35>(h)>ap_int<35>(cfg.rh)*4)continue;
     const ap_int<33> dx=ap_int<33>(x)-cfg.rx,dy=ap_int<33>(y)-cfg.ry;
     ap_uint<68> distance4=ap_uint<68>(dx*dx)+ap_uint<68>(dy*dy);distance4<<=2;
     if(distance4>radius4)continue;
    }
    best.x=x;best.y=y;best.w=w;best.h=h;best.raw_objectness=raw;best.index=key;best.valid=1;
   }
  }
  head_base+=3*cells;
 }
 if(best.valid)best.confidence=sigmoid_q(best.raw_objectness);
}
