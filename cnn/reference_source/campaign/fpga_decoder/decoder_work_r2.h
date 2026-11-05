// Integer ROI-to-working-image decode for the actual two-class V5 P2/P3 heads.
// Upstream YOLOv5 v7 raw-head equations and GPL3 attribution retained in vendor.
#pragma once
#include <ap_int.h>
using DecoderWord=ap_uint<256>;
struct DecodeConfig {
 int sx,sy,ox,oy; // Q16 working pixels per CNN pixel; Q16 working offsets
 int u,v,mx,my,use_motion;
 int rx,ry,rw,rh,use_association; // past predicted reference; no labels
};
struct Candidate {
 ap_int<32> x,y,w,h; // working image (640-wide), Q16
 ap_uint<17> confidence;
 ap_int<24> raw_objectness;
 ap_uint<16> index;
 ap_uint<1> valid; // geometry-passing candidate, not a declared drone detection
};
void decode_work_heads(const DecoderWord* features,DecodeConfig cfg,Candidate &best);
