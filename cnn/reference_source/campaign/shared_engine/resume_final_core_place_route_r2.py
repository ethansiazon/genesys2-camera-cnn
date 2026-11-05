"""Changed RAM strategy: resume saved opt DCP in ONE single-thread Vivado.
Preserves actual synthesis and failed parent HLS-export attempt; no resynthesis.
"""
import hashlib,json,sys,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
from state import lock,save,status
import run_shared_preflight as runner
BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_wide_r2_live';OUT=BUILD/'direct_place_route_r2';REPORT=HERE/'FINAL_ROI11_CORE_ROUTE_R2.json'

def main():
    if OUT.exists() or REPORT.exists():raise RuntimeError('Existing changed implementation attempt preserved')
    previous=json.loads((HERE/'FINAL_ROI11_CORE_IMPLEMENTATION.json').read_text())
    if previous.get('error')!='Own compiler stopped at1.5GiB RAM reserve':raise RuntimeError('Specific original memory evidence required before changed strategy')
    checkpoint=BUILD/'shared_engine_prj/solution1/impl/verilog/project.runs/impl_1/bd_0_wrapper_opt.dcp'
    if not checkpoint.exists():raise RuntimeError('No saved optimized design to resume')
    OUT.mkdir();record={'status':'running','routed':False,'core_fit_verified':False,'system_fit_verified':False,'checkpoint':str(checkpoint),'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),'change_from_failed_attempt':'Reuse COMPLETE optimizedDCP, no resynthesis. Single directVivado process vs parentVitis+VivadoBDimplementation run; general.maxThreads1. Samepart/circuit/10nsconstraints, RAMguardunchanged.','scope':'Out-of-contextcore only, no camera/MIG/frontend/decoder/boardprogramming; inspect postroutepaths/constraints before fit/speed claim.'};save(REPORT,record)
    try:
        code=r'''set_param general.maxThreads 1
open_checkpoint {CHECKPOINT}
report_clocks -file clocks_before.rpt
place_design
write_checkpoint -force placed.dcp
phys_opt_design
route_design
write_checkpoint -force routed.dcp
report_route_status -file route_status.rpt
report_timing_summary -delay_type min_max -report_unconstrained -file timing.rpt
report_utilization -hierarchical -file utilization.rpt
report_drc -file drc.rpt
set setup_path [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_path [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup_path] != 1 || [llength $hold_path] != 1} {error {No actual constrained setup/hold timing paths}}
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set periods [get_property PERIOD [get_clocks]]
set blackboxes [llength [get_cells -hier -quiet -filter {IS_BLACKBOX == 1}]]
set fd [open timing_values.json w]
puts $fd [format {{"setup_wns_ns": %.8f,"hold_whs_ns": %.8f,"clock_periods_ns": "%s","blackbox_count":%d}} $wns $whs $periods $blackboxes]
close $fd
exit
'''.replace('CHECKPOINT',checkpoint.as_posix());(OUT/'resume.tcl').write_text(code);runner.HERE=OUT;runner.run('direct_final_core_route_r2',[r'C:\AMDDesignTools\2026.1\Vivado\bin\vivado.bat','-mode','batch','-source','resume.tcl','-log','vivado.log','-journal','vivado.jou'],3600)
        values=json.loads((OUT/'timing_values.json').read_text());record.update(status='complete_review_required',routed=(OUT/'routed.dcp').exists(),timing=values,reports={name:str(OUT/name) for name in ['route_status.rpt','timing.rpt','utilization.rpt','drc.rpt']},scope='Actual resumedoneprocess OOCcore placement/routing. Review unroutednets/actual100MHzsetup+hold/constraints/resources. Fullcamera/MIG/interfaces/decoder/DDRthroughput andphysicalboard remainunproven.');save(REPORT,record);status('Direct actual core placement/routing reports saved',timing=values,system_fit_proven=False)
    except BaseException as exc:record.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,record);status('Changed direct-route strategy requires inspection',error=str(exc));raise

if __name__=='__main__':
    with lock():main()
