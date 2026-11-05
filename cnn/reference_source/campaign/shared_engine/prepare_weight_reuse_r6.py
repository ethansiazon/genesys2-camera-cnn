"""Prepare versioned same-math latency hypothesis; no compiler job is launched.

Reuse one output-channel group's weights across spatial tiles. Skip input clear
only when the entire input tile is overwritten by the subsequent valid burst.
Preserve the proven R5 source/program/weights and test all full-network vectors.
"""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from state import save
SOURCE=Path.home()/'fpga_builds/g2_roi_epoch11_wide_r2_live'
BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_reuse_r6'

def main():
    if BUILD.exists():raise RuntimeError('Versioned R6 already exists; inspect, do not overwrite')
    src=(SOURCE/'cnn_engine.cpp').read_text()
    expected='72549945a577ae6d5576dc5da46c743453091b174e411f473625a3c0fb0533db'
    if hashlib.sha256((SOURCE/'cnn_engine.cpp').read_bytes()).hexdigest()!=expected:raise RuntimeError('Unexpected proven R5 source')
    start=src.index('static void convolve(');end=src.index('\nstatic void vector_operation(',start)
    old=src[start:end]
    h_end=old.index('TileRows:')
    header=old[:h_end].replace('    const int ci_blocks=', '''    Word cached_weights[16][144];
    #pragma HLS ARRAY_PARTITION variable=cached_weights complete dim=1
    #pragma HLS BIND_STORAGE variable=cached_weights type=ram_1p impl=bram
    const int ci_blocks=''')
    tile_prefix=old[h_end:old.index('        OutputGroups:')]
    bias_start=old.index('                ap_int<48> bias[16];')
    body_start=old.index('                for(int pos=0;pos<64;pos++)')
    bias=old[bias_start:body_start]
    closing='            }\n        }\n    }\n}'
    body_end=old.rindex(closing)
    body=old[body_start:body_end]
    clear_start=body.index('                ClearInputRows:')
    clear_end=body.index('                    const int source_x=',clear_start)
    clear=body[clear_start:clear_end]
    # No input element is reused across tiles. Interior tiles are fully loaded;
    # boundary tiles retain the original complete clear followed by valid loads.
    body=body[:clear_start]+'''                    const bool has_padding=(tx*op.s-op.p<0 || ty*op.s-op.p<0 ||
                        tx*op.s-op.p+ic>op.iw || ty*op.s-op.p+ir>op.ih);
                    if(has_padding) {
'''+clear+'''                    }
'''+body[clear_end:]
    load_start=body.index('                    for(int kk=0;kk<op.k*op.k;kk++)')
    load_end=body.index('                KernelRows:',load_start)
    body=body[:load_start]+'''                LoadCachedKernel:
                    for(int kk=0;kk<op.k*op.k;kk++) {
                        #pragma HLS LOOP_TRIPCOUNT min=1 max=9
                        #pragma HLS PIPELINE II=1
                        for(int m=0;m<16;m++) {
                            #pragma HLS UNROLL
                            Word word=cached_weights[m][ni*op.k*op.k+kk];
                            for(int n=0;n<8;n++) {
                                #pragma HLS UNROLL
                                weight[m][n][kk]=coefficient_lane(word,n);
                            }
                        }
                    }
'''+body[load_end:]
    outer='''OutputGroupsCached:
    for(int mo=0;mo<op.oc;mo+=16) {
        #pragma HLS LOOP_TRIPCOUNT min=1 max=8
    CacheOutputGroupWeights:
        for(int slot=0;slot<ci_blocks*op.k*op.k;slot++) {
            #pragma HLS LOOP_TRIPCOUNT min=1 max=144
            for(int m=0;m<16;m++) {
                #pragma HLS PIPELINE II=1
                cached_weights[m][slot]=coefficients[op.wo+((mo/16)*ci_blocks*op.k*op.k+slot)*16+m];
            }
        }
'''
    changed=header+outer+bias+tile_prefix+body+closing+'\n'
    result=src[:start]+changed+src[end:]
    if result.count('CacheOutputGroupWeights:')!=1 or result.count('OutputGroups:'):raise RuntimeError('Transformation guard failed')
    BUILD.mkdir()
    for name in ['cnn_engine.h','program.h','program.json','coefficients.bin','input_0.bin','input_1.bin','input_2.bin','expected.npy','test_engine.cpp','SOURCE_PROVENANCE.json','QUANTIZED_MODEL_METADATA.json']:
        shutil.copy2(SOURCE/name,BUILD/name)
    (BUILD/'cnn_engine.cpp').write_text(result)
    audit={'prepared':True,'source':str(SOURCE),'build':str(BUILD),'source_sha256':expected,'new_sha256':hashlib.sha256((BUILD/'cnn_engine.cpp').read_bytes()).hexdigest(),'changes':['Output-group outermost: cache all input-channel/kernel weights once before spatial tiles','Sixteen independently addressed packed coefficient BRAM banks; same 128-MAC datapath','Skip full input clear only for interior tiles whose every position is subsequently overwritten'],'unchanged':['Final ROI11 trained coefficients and per-layer scales','All 55 instructions, operators, round-to-even and saturation','A24F14 features, W16 coefficients,48-bit accumulators','Input and output memory layout, all three independent full-network expected vectors'],'hypothesis':'Reduce repeated coefficient DDR traffic and interior clear cycles; actual HLS/RTL cycles, timing and resources MUST be measured before accepting','not_claimed':['Speedup','FPGA resource fit','RTL equivalence','New V5 weight quality','Physical DDR or board performance']}
    save(BUILD/'PREPARED.json',audit);save(ROOT/'shared_engine/WEIGHT_REUSE_R6_PREPARED.json',audit)
    print(json.dumps(audit,indent=2))

if __name__=='__main__':main()
