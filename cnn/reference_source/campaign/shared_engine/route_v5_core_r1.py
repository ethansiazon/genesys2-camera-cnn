"""Prepared direct single-process Vivado route for actual V5 R7 circuit.

Launch only after serial quality/actualRTL completes. No HLS parent or board I/O.
Every stage saves a recoverable checkpoint; no automatic identical failure retry.
"""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT))
import hashlib,json,shutil,traceback
from state import lock,save,status
import run_shared_preflight as runner
BUILD=Path.home()/'fpga_builds/g2_roi_v5_epoch08_output32_r2'
OUT=BUILD/'direct_core_route_r1'
REPORT=HERE/'V5_R2_CORE_ROUTE_R1.json'


def main():
    if OUT.exists() or REPORT.exists():raise RuntimeError('Previous route attempt preserved; review before any changed retry')
    rtl=json.loads((HERE/'V5_R2_ACTUAL_RTL.json').read_text());quality=json.loads((ROOT/'v5_fixed_feedback_native_r1/COMPLETE.json').read_text())
    if not rtl['rtl_passed'] or not quality['within_three_percentage_point_loss'] or quality['clipped_values']:raise RuntimeError('Actual trained RTL and fresh quality gates required')
    if runner.free()<4:raise RuntimeError('Need4GiB free to begin one guarded direct Vivado')
    source=BUILD/'shared_engine_prj/solution1/syn/verilog';OUT.mkdir();copied=OUT/'rtl';copied.mkdir();hashes={}
    proven=rtl['provenance']['rtl_sha256']
    for path in source.iterdir():
        if path.suffix not in ('.v','.dat'):continue
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=proven[path.name]:raise RuntimeError('Generated RTL changed after numerical proof')
        shutil.copy2(path,copied/path.name);hashes[path.name]=digest
    record={'status':'running','routed':False,'core_fit_verified':False,'system_fit_verified':False,'source_rtl_sha256':hashes,'checkpoint_sha256':json.loads((BUILD/'PREPARED.json').read_text())['checkpoint_sha256'],'strategy':'One direct Vivado process, general.maxThreads1, out-of-context synthesized actual generated full V5core; no parentVitis/BDmemory overhead. Preserve1.5GiB memoryguard. Recoverable synth/opt/place/route checkpoints.','scope':'Actual trained V5 core only. ExternalAXI/control timing/realDDR/MIG/camera/frontend/controller/decoder/system and board inference not included.'};save(REPORT,record)
    try:
        tcl='''set_param general.maxThreads 1
read_verilog [glob rtl/*.v]
synth_design -top cnn_engine -part xc7k325tffg900-2 -mode out_of_context
create_clock -name core_clock -period 10 [get_ports ap_clk]
write_checkpoint -force synthesized.dcp
report_utilization -file utilization_synth.rpt
opt_design
write_checkpoint -force optimized.dcp
place_design
write_checkpoint -force placed.dcp
phys_opt_design
route_design
write_checkpoint -force routed.dcp
report_route_status -file route_status.rpt
report_timing_summary -delay_type min_max -report_unconstrained -file timing.rpt
report_utilization -hierarchical -file utilization.rpt
report_drc -file drc.rpt
check_timing -verbose -file check_timing.rpt
set setup_path [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_path [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup_path] != 1 || [llength $hold_path] != 1} {error {Missing actual constrained setup/hold paths}}
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set periods [get_property PERIOD [get_clocks]]
set blackboxes [llength [get_cells -hier -quiet -filter {IS_BLACKBOX == 1}]]
set fd [open timing_values.json w]
puts $fd [format {{"setup_wns_ns": %.8f,"hold_whs_ns": %.8f,"clock_periods_ns": "%s","blackbox_count":%d}} $wns $whs $periods $blackboxes]
close $fd
exit
'''
        (OUT/'route.tcl').write_text(tcl)
        # ROM .dat names in generated RTL are relative, preserve both source-dir
        # and working-dir lookup without altering generated modules.
        for path in copied.glob('*.dat'):shutil.copy2(path,OUT/path.name)
        runner.HERE=OUT;runner.run('direct_v5_core_route_r1',[r'C:\AMDDesignTools\2026.1\Vivado\bin\vivado.bat','-mode','batch','-source','route.tcl','-log','vivado.log','-journal','vivado.jou'],5400)
        values=json.loads((OUT/'timing_values.json').read_text());record.update(status='complete_review_required',routed=(OUT/'routed.dcp').exists(),timing=values,reports={n:str(OUT/n) for n in ['route_status.rpt','timing.rpt','utilization.rpt','drc.rpt','check_timing.rpt']},next='Supervisor independently review fullyrouted/error/clock/no-unconstrainedINTERNAL endpoints/setup/hold/blackbox/resource evidence. No external-system fit claim from OOC alone.');save(REPORT,record)
        status('Actual V5 routed core reports ready for review',timing=values,system_fit_proven=False)
    except BaseException as exc:
        record.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc(),saved_checkpoints=[str(p) for p in OUT.glob('*.dcp')]);save(REPORT,record);status('V5 route needs review; checkpoints preserved',error=str(exc));raise


if __name__=='__main__':
    with lock():main()
