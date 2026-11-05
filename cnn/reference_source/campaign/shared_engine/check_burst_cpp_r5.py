"""Same independent full-network host comparison for changed R5 memory access."""
from pathlib import Path
import check_wide_cpp_r4 as runner
runner.BUILD=Path.home()/'fpga_builds/g2_shared_engine_20261017_wide_r5_burst_roi256'
runner.REPORT=runner.BUILD/'HOST_NUMERICAL_CHECK.json'
if __name__=='__main__':runner.main()
