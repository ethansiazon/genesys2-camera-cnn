"""Guarded full-CNN native numerical check of versioned R6; no HLS launch."""
from pathlib import Path
import json
import check_wide_cpp_r4 as runner
runner.BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_reuse_r6'
runner.REPORT=runner.BUILD/'HOST_NUMERICAL_CHECK.json'
if __name__=='__main__':
    program=json.loads((runner.BUILD/'program.json').read_text())
    # program.h fixes the operator bounds; no unsupported instruction may address
    # beyond the 16 input groups x nine kernel positions cached in each bank.
    operations=program.get('instructions',[])
    if not operations:raise RuntimeError('Inspect operator schema before using cache')
    for op in operations:
        if op.get('kind') in (1,'conv','conv2d'):
            if (op['ic']+7)//8*op['k']**2>144:raise RuntimeError('Weight cache capacity exceeded')
    runner.main()
