"""CPU-only prepare LUT/shape reference for selected verified ROI11 topology.
No HLS execution or claim; final V5shape/anchors must explicitly match later.
"""
import hashlib,json,shutil
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
BUILD=Path.home()/'fpga_builds/g2_roi_decoder_r1'
CNN=Path.home()/'fpga_builds/g2_roi_epoch11_wide_r2_live'

def main():
    if BUILD.exists():raise RuntimeError('Existing decoder preparation preserved')
    proof=json.loads((ROOT/'shared_engine/FINAL_ROI11_CORE_FIT_REVIEW.json').read_text())
    if not proof['core_fit_verified']:raise RuntimeError('Verified full CNN foundation required')
    program=json.loads((CNN/'program.json').read_text());anchors=np.array(json.loads((ROOT/'trial03_p23_consistent_flying/config.json').read_text())['anchors']).reshape(2,3,2);heads=program['heads']
    if [h['shape_bchw'] for h in heads]!=[[1,21,48,64],[1,21,24,32]]:raise RuntimeError('Actual head packing differs')
    x=np.arange(6145)/256-12;table=np.rint(65536/(1+np.exp(-x))).astype(np.uint32);raw=np.arange(-196608,196609);index=((raw+196608+32)>>6).clip(0,6144);error=np.abs(table[index]/65536-1/(1+np.exp(-raw/16384)));maximum=float(error.max())
    if maximum>.00051:raise RuntimeError('LUT approximation bound unexpected')
    BUILD.mkdir()
    for name in ['decoder.cpp','decoder.h']:shutil.copy2(HERE/name,BUILD/name)
    header='#pragma once\n#define DECODER_FEATURE_WORDS '+str(program['feature_ddr_words'])+'\n'
    for name,values in [('HEAD_WIDTH',[h['shape_bchw'][3] for h in heads]),('HEAD_HEIGHT',[h['shape_bchw'][2] for h in heads]),('HEAD_OFFSET',[h['offset_words'] for h in heads]),('HEAD_STRIDE',[4,8])]:header+='static const int '+name+'[2]={'+','.join(map(str,values))+'};\n'
    aq=np.rint(anchors*65536).astype(np.uint32);header+='static const unsigned int ANCHOR_Q16[2][3][2]={'+','.join('{'+','.join('{'+','.join(map(str,pair))+'}' for pair in row)+'}' for row in aq)+'};\n';(BUILD/'model_shape.h').write_text(header)
    lut='#pragma once\n#include <ap_int.h>\nstatic const ap_uint<17> SIGMOID_LUT[6145]={\n'+',\n'.join(','.join(map(str,table[i:i+32])) for i in range(0,len(table),32))+'\n};\n';(BUILD/'sigmoid_lut.h').write_text(lut);np.save(BUILD/'sigmoid_lut.npy',table)
    metadata={'cnn_build':str(CNN),'heads':heads,'feature_words':program['feature_ddr_words'],'anchors_pixels':anchors.tolist(),'anchor_q16':aq.tolist(),'lut_max_abs_probability_error_exhaustive_all393217A24codes_minus12_to12':maximum,'source_hashes':{name:hashlib.sha256((BUILD/name).read_bytes()).hexdigest() for name in ['decoder.cpp','decoder.h','model_shape.h','sigmoid_lut.h']},'scope':'PREPARED CNN ROI-space hardware decoder source/LUT. NO host C++/HLS/RTL/quality/resource/timing proofyet. InputsA24F14physical32lanes, outputsQ16xywh/UF17F16probability/motionpeakgate. Rawlogitmax avoidsLUTties butmaydifferfromfloat32saturationtiebehavior; actualfullnativequality required. No camera/nativecoords/trackcontroller/MIG/systemfit claim. Sameanchors/shape mustexplicitlymatchfutureV5checkpoint.'};(BUILD/'PREPARED.json').write_text(json.dumps(metadata,indent=2));print(json.dumps({'build':str(BUILD),'lut_max_probability_error':maximum}))

if __name__=='__main__':main()
