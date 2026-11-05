"""One memory-access change from numerically passed R4; no FPGA compiler.
R3 synthesis inferred bursts for weights/vectors, none for conditional input load.
Hoist padding and make each valid feature row an unconditional contiguous read.
"""
from pathlib import Path
import difflib,hashlib,json,shutil
HERE=Path(__file__).resolve().parent
SOURCE=Path.home()/'fpga_builds/g2_shared_engine_20261017_wide_r4_roi256_live'
BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_wide_r5_burst_roi256'

def main():
    if BUILD.exists():raise RuntimeError('Existing changed build preserved')
    if not json.loads((SOURCE/'HOST_NUMERICAL_CHECK.json').read_text())['passed']:raise RuntimeError('Wide R4 full numeric gate required')
    original=(SOURCE/'cnn_engine.cpp').read_text();begin=original.index('                LoadRows:');end=original.index('                    for(int kk=',begin)
    load='''                ClearInputRows:
                    for(int y=0;y<ir;y++)for(int x=0;x<ic;x++) {
                        #pragma HLS PIPELINE II=1
                        for(int n=0;n<8;n++) {
                            #pragma HLS UNROLL
                            input[n][y][x]=0;
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
'''
    changed=original[:begin]+load+original[end:];BUILD.mkdir()
    for name in ['cnn_engine.h','test_engine.cpp','program.h','program.json','coefficients.bin','input_0.bin','input_1.bin','input_2.bin','expected.npy','VECTORS.json','QUANTIZED_MODEL_METADATA.json','quantized_fx.pt','LIVENESS_AUDIT.json']:shutil.copy2(SOURCE/name,BUILD/name)
    (BUILD/'cnn_engine.cpp').write_text(changed);(BUILD/'SOURCE_CHANGE.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='R4 conditional padding read',tofile='R5 zero then contiguous valid spans')))
    (BUILD/'SOURCE_PROVENANCE.json').write_text(json.dumps({'parent_build':str(SOURCE),'parent_cpp_sha256':hashlib.sha256(original.encode()).hexdigest(),'new_cpp_sha256':hashlib.sha256(changed.encode()).hexdigest(),'scope':'Prepared input padding/burst-access COPY only. Same full55op program, arithmetic, coefficients, liveness,128MACs and A24F14/W16. Parent HLS log has no burst inference on LoadRows_LoadCols; NEW actual HLS burst inference/resources/RTL/cycles still unproven. No false-dependence pragmas or claimed speedup.'},indent=2));print(BUILD)

if __name__=='__main__':main()
