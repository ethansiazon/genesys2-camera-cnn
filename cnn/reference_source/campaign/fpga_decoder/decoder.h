// FPGA-oriented YOLOv5v7 raw-head decode adaptation; pinned upstream attribution
// and GPL3 retained in campaign/vendor/yolov5. No camera/MIG integration here.
#pragma once
#include <ap_int.h>
using DecoderWord=ap_uint<256>;
struct Candidate {
    ap_int<32> x,y,w,h; // CNN ROI pixels, signed Q16
    ap_uint<17> confidence; // 0..65536 represents0..1; NOT track-active flag
    ap_int<24> raw_objectness;
    ap_uint<16> index;
    ap_uint<1> valid; // Candidate passed geometry, not thresholded drone detection
};
void decode_heads(const DecoderWord *features,int u_q16,int v_q16,
                  int margin_x_q16,int margin_y_q16,int use_motion_gate,
                  Candidate &best);
