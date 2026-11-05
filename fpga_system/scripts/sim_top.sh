#!/bin/bash -f
# Task 4's full MIG-calibration-aware simulation: rebuild the project with
# PHASE2_SIM_BYPASS_CAL=1 (SIM_BYPASS_INIT_CAL=FAST + 256-word coefficient
# cut, both simulation-only), export the IP simulation sources via Vivado's
# own export_simulation (MIG/smartconnect/proc_sys_reset/jtag_axi all need
# their generated sim netlists -- hand-enumerating those is impractical),
# then run with a real run-all script.
#
# CRITICAL FIX (code review, 2026-10-28): export_simulation's own generated
# cmd.tcl defaults to `run 1000ns; quit` (a GUI quick-look default) -- that
# is NOT "run to completion". The first attempt at this sim looked like a
# silent pass (6 seconds, zero output) for exactly this reason. Always use
# run_all.tcl (committed here, not generated) instead.
#
# Committed (code review, 2026-10-28, I10): the first version of this phase
# only ran these commands by hand and never committed a runner.
set -euo pipefail
cd "$(dirname "$0")/.."

source /tools/Xilinx/Vivado/2023.2/settings64.sh

rm -rf vivado xsim.dir sim_export *.jou *.pb *.log
PHASE2_SIM_BYPASS_CAL=1 vivado -mode batch -source scripts/create_project.tcl -source bd/create_bd.tcl

cat > /tmp/sim_top_setup.tcl << 'EOF'
open_project vivado/genesys2_cv.xpr
add_files -fileset sim_1 -norecurse [list \
    [file join [pwd] sim tb_cnn_subsystem_top.v] \
    [file join [pwd] sim mig_sim_models ddr3_model.sv] \
    [file join [pwd] sim mig_sim_models ddr3_model_parameters.vh] \
    [file join [pwd] sim mig_sim_models wiredly.v] \
]
set_property top tb_cnn_subsystem_top [get_filesets sim_1]
set_property include_dirs [list [file join [pwd] sim mig_sim_models]] [get_filesets sim_1]
update_compile_order -fileset sim_1
export_simulation -simulator xsim -directory sim_export -force
EOF
PHASE2_SIM_BYPASS_CAL=1 vivado -mode batch -source /tmp/sim_top_setup.tcl

cat > sim_export/xsim/run_all.tcl << 'EOF'
run -all
quit
EOF
cd sim_export/xsim
chmod +x tb_cnn_subsystem_top.sh
./tb_cnn_subsystem_top.sh
xsim tb_cnn_subsystem_top -tclbatch run_all.tcl -log run_all.log
