"""Evidence-led COPY: separate vector DDR reads/writes causing R2 II17/15.946ns.
No FPGA compiler or GPU launched here. Preserve current active RTL and training.
"""
import hashlib,json,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
SOURCE=Path.home()/'fpga_builds/g2_shared_engine_20261017_live_r2'
BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_vector_r3'

BODY=r'''static void vector_operation(Word* memory,Op op) {
    #pragma HLS INLINE off
    Word first[64],second[64],even[128],odd[128];
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
                    Word p00=even[x*2],p01=even[x*2+1],p10=odd[x*2],p11=odd[x*2+1],word=0;
                    for(int n=0;n<8;n++) {
                        #pragma HLS UNROLL
                        const int channel=c*8+n,source=channel/4;Word pixel;
                        if(channel%4==0)pixel=p00;else if(channel%4==1)pixel=p01;else if(channel%4==2)pixel=p10;else pixel=p11;
                        ap_int<16> value=source<op.ic?lane(pixel,source):ap_int<16>(0);
                        word.range(n*16+15,n*16)=value.range(15,0);
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
            Word word;
            if(op.kind==4)word=first[x/2];
            else if(op.kind==3)word=first[x];
            else {
                Word a=first[x],b=op.kind==2?second[x]:Word(0);word=0;
                for(int n=0;n<8;n++) {
                    #pragma HLS UNROLL
                    ap_int<48> value=lane(a,n);
                    if(op.kind==2)value+=lane(b,n);
                    if(op.kind==5 && value<0)value=0;
                    ap_int<16> q=saturate(value);word.range(n*16+15,n*16)=q.range(15,0);
                }
            }
            memory[destination+x]=word;
        }
    }
}'''

def main():
    if BUILD.exists():raise RuntimeError('Versioned optimization build preserved')
    BUILD.mkdir()
    for name in ['cnn_engine.h','program.h','program.json','test_engine.cpp','coefficients.bin','input_0.bin','input_1.bin','input_2.bin']:shutil.copy2(SOURCE/name,BUILD/name)
    text=(SOURCE/'cnn_engine.cpp').read_text();start=text.index('static void vector_operation(');end=text.index('\nvoid cnn_engine(',start)
    (BUILD/'cnn_engine.cpp').write_text(text[:start]+BODY+'\n'+text[end:])
    (BUILD/'OPTIMIZATION_PROVENANCE.json').write_text(json.dumps({'source':str(SOURCE),'scope':'COPY with vector load/write phases separated, exact SAME complete model coefficients/layout/liveness/program and convolution kernel. Host/fullRTL/resource/timing gates required before adoption.',
        'evidence':'R2 HLS200-887/1016: busread7.3ns +select1.346ns +buswrite7.3ns, II17 in vector_operation. Convolve meets7.3ns, so target evidenced vector bottleneck first.',
        'source_cpp_sha256':hashlib.sha256((SOURCE/'cnn_engine.cpp').read_bytes()).hexdigest(),'coefficient_bytes_unchanged':(BUILD/'coefficients.bin').read_bytes()==(SOURCE/'coefficients.bin').read_bytes(),
        'fpga_compiler_launched':False,'synthesis_passed':False,'rtl_passed':False},indent=2))
    print(BUILD)

if __name__=='__main__':main()
