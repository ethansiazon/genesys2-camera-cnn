"""Prepare a measured-headroom experiment:32 output x8 input MAC lanes.

Same R6 model/precision/math, twice output-channel hardware, same old coefficient
format. Load each16-channel packed coefficient subgroup independently; mask
invalid extra output lanes, including the16-channel stem and21-channel heads.
No HLS job is launched by this preparation.
"""
from pathlib import Path
import hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from state import save
SOURCE=Path.home()/'fpga_builds/g2_roi_epoch11_reuse_r6'
BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_output32_r7'

def main():
    if BUILD.exists():raise RuntimeError('Existing output32 attempt preserved')
    src=(SOURCE/'cnn_engine.cpp').read_text();oldsha=hashlib.sha256((SOURCE/'cnn_engine.cpp').read_bytes()).hexdigest();proof=json.loads((ROOT/'shared_engine/WEIGHT_REUSE_R6_ACTUAL_RTL.json').read_text())
    if not proof['rtl_passed'] or oldsha!=json.loads((SOURCE/'PREPARED.json').read_text())['new_sha256']:raise RuntimeError('Exact R6 RTL prerequisite required')
    start=src.index('static void convolve(');end=src.index('\nstatic void vector_operation(',start);old=src[start:end];changed=old
    for before,after in [('weight[16][8][9]','weight[32][8][9]'),('accum[16][64]','accum[32][64]'),('cached_weights[16][144]','cached_weights[32][144]'),('mo+=16','mo+=32'),('ap_int<48> bias[16]','ap_int<48> bias[32]'),('for(int m=0;m<16;m++)','for(int m=0;m<32;m++)'),('for(int group=0;group<2;group++)','for(int group=0;group<4;group++)')]:
        if before not in changed:raise RuntimeError('Transformation anchor missing:'+before)
        changed=changed.replace(before,after)
    c0=changed.index('    CacheOutputGroupWeights:');c1=changed.index('                ap_int<48> bias[32];',c0)
    changed=changed[:c0]+'''    CacheOutputSubgroups:
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
'''+changed[c1:]
    before='Word word=cached_weights[m][ni*op.k*op.k+kk];'
    if changed.count(before)!=1:raise RuntimeError('Cached kernel read changed')
    changed=changed.replace(before,'Word word=(mo+m<op.oc)?cached_weights[m][ni*op.k*op.k+kk]:Word(0);')
    changed=changed.replace('OutputGroupsCached:\n    for(int mo=0;mo<op.oc;mo+=32) {\n        #pragma HLS LOOP_TRIPCOUNT min=1 max=8','OutputGroupsCached:\n    for(int mo=0;mo<op.oc;mo+=32) {\n        #pragma HLS LOOP_TRIPCOUNT min=1 max=4')
    result=src[:start]+changed+src[end:];program=json.loads((SOURCE/'program.json').read_text())
    for op in program['instructions']:
        if op['kind']==1 and ((op['ic']+7)//8*op['k']**2>144 or op['oc']>128 or op['a']==op['o']):raise RuntimeError('Unsupported operator bounds/alias')
    BUILD.mkdir()
    for name in ['cnn_engine.h','program.h','program.json','coefficients.bin','input_0.bin','input_1.bin','input_2.bin','expected.npy','test_engine.cpp','SOURCE_PROVENANCE.json','QUANTIZED_MODEL_METADATA.json']:shutil.copy2(SOURCE/name,BUILD/name)
    (BUILD/'cnn_engine.cpp').write_text(result)
    audit={'prepared':True,'source':str(SOURCE),'build':str(BUILD),'source_sha256':oldsha,'new_sha256':hashlib.sha256((BUILD/'cnn_engine.cpp').read_bytes()).hexdigest(),'mac_lanes':[32,8],'model_sha256':program['model_sha256'],'changes':['32ratherthan16outputchannels per convolution tile,256ratherthan128MACs','32independentpackedcoefficientcachebanks','Preserveexported16outputchannelformat throughseparate16-lanesubgroupbursts','Maskinvalidextraoutputlaneweightreads;bias/outputstoresalreadyguardactualoc'],'why':'R6actualHLSusesonly141of840DSPand162of890BRAM18K. Testingadditionalparallelismaddressesmeasuredlatencysensitivitywithoutchangingmodelmath. Resources/timing/cyclesmustbemeasured,notlinearlyassumed.','primary_research':['https://chenzhangsjtu.github.io/files/2015-FPGA.pdf','https://github.com/dhm2013724/yolov2_xilinx_fpga'],'scope':'PreparedCHANGEDhardware experiment ONLY, SAME actualfinalROI11 fullCNN/precision/expectedoutputs. Not measurednewfit/speedup,notV5weights orcamera-systemproof.'};save(BUILD/'PREPARED.json',audit);save(ROOT/'shared_engine/OUTPUT32_R7_PREPARED.json',audit);print(json.dumps(audit,indent=2))

if __name__=='__main__':main()
