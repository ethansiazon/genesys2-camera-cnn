"""Guarded light native numerical check of R7; no FPGA compiler or GPU."""
from pathlib import Path
import check_wide_cpp_r4 as runner
runner.BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_output32_r7'
runner.REPORT=runner.BUILD/'HOST_NUMERICAL_CHECK.json'
if __name__=='__main__':runner.main()
