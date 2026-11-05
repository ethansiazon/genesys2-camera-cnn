"""Versioned original allocator for256ROI/256bit feature words; no FPGA compiler."""
from pathlib import Path
import json,subprocess,sys
HERE=Path(__file__).resolve().parent
SOURCE=Path.home()/'fpga_builds/g2_shared_engine_20261017_wide_r4_roi256'
BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_wide_r4_roi256_live'

def main():
    if BUILD.exists():raise RuntimeError('Existing live wide build preserved')
    # Correct descriptive metadata only from first export's old template wording.
    path=SOURCE/'program.json';raw=path.read_bytes();d=json.loads(raw)
    if d['feature_ddr_bytes']!=d['feature_ddr_words']*32:raise RuntimeError('Wide physical feature bytes mismatch')
    (SOURCE/'PROGRAM_METADATA_BEFORE_WORD_LABEL_CORRECTION.json').write_bytes(raw)
    d.update(layout='NCHW8:256bitfeaturewords,8signextended32bitlanes carryingA24F14;128bitcoefficientwords,8signedW16lanes;B24F14 storedsigned32',feature_word_bits=256,coefficient_word_bits=128)
    path.write_text(json.dumps(d,indent=2))
    code=(HERE/'plan_live_memory.py').read_text().replace("SOURCE=Path.home()/'fpga_builds/g2_shared_engine_20261017_r1'",f'SOURCE=Path({str(SOURCE)!r})').replace("BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_live_r2'",f'BUILD=Path({str(BUILD)!r})')
    code=code.replace('sizes={0:288*384}','sizes={0:192*256}').replace('high*16','high*32')
    code=code.replace("'input_2.bin']","'input_2.bin','quantized_fx.pt','QUANTIZED_MODEL_METADATA.json','expected.npy','VECTORS.json','SOURCE_PROVENANCE.json']")
    start=code.index("    original=(HERE/'run_shared_preflight.py').read_text()");end=code.index('    print(json.dumps(',start);code=code[:start]+code[end:]
    target=SOURCE/'plan_live_wide.py';target.write_text(code);subprocess.run([sys.executable,str(target)],check=True)

if __name__=='__main__':main()
