#!/bin/bash -f
# Task 3's standalone coefficient BRAM -> DDR copy sim: compile, elaborate,
# run. No BD-generated IP involved here, so plain xvlog/xelab/xsim directly
# (no export_simulation needed) -- unlike sim_top.sh. Run from the project
# root (coeff_bram_stage.v's HEXFILE path is relative to the invocation
# directory).
#
# Committed (code review, 2026-10-28, I10): the first version of this phase
# only ran these commands by hand and never committed a runner, so neither
# this sim nor sim_top.sh could be re-run or re-verified from the repo
# alone.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf xsim.dir *.jou *.pb *.log
xvlog --sv sim/axi_ram.sv
xvlog rtl/coeff_bram_stage.v rtl/copy_fsm.v sim/tb_bram_to_ddr.v
xelab tb_bram_to_ddr -s bram_to_ddr_test
xsim bram_to_ddr_test -runall
