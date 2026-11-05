"""AMD-supported HLS export_design -flow impl: real OOC Vivado place/route.
No physical board pins, programming or claim about full camera/MIG system.
"""
import hashlib,json,sys,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
from state import lock,save,status
import run_shared_preflight as runner
BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_wide_r2_live';REPORT=HERE/'FINAL_ROI11_CORE_IMPLEMENTATION.json'

def main():
    if REPORT.exists():raise RuntimeError('Existing actual implementation preserved; no identical retry')
    proof=json.loads((HERE/'FINAL_ROI11_ACTUAL_RTL.json').read_text())
    if not proof['rtl_passed']:raise RuntimeError('Actual FINAL full CNN RTL proof required')
    rtl=BUILD/'shared_engine_prj/solution1/syn/verilog'
    for name,sha in proof['provenance']['rtl_sha256'].items():
        if hashlib.sha256((rtl/name).read_bytes()).hexdigest()!=sha:raise RuntimeError('Verified final generated RTL changed')
    record={'status':'running','tool_completed':False,'core_fit_verified':False,'system_fit_verified':False,'physical_board_inference':False,'primary_reference':'https://docs.amd.com/r/en-US/ug1399-vitis-hls/export_design','scope':'Actual Vivado synthesis/place-and-route of verified FINALROI11core via AMD HLS supported export_design -flow impl. OOC coreONLY; excludesphysicalcamera/MIG/interconnect/frontend/decoder/systemconstraints. No boardprogramming.'};save(REPORT,record)
    try:
        tcl='open_project shared_engine_prj\nopen_solution solution1\nexport_design -rtl verilog -format ip_catalog -flow impl -ipname genesys2_roi11_cnn\nexit\n';(BUILD/'actual_core_impl.tcl').write_text(tcl);runner.HERE=BUILD;runner.run('actual_final_roi11_export_impl',[r'C:\AMDDesignTools\2026.1\Vitis\bin\vitis-run.bat','--tcl','actual_core_impl.tcl','--mode','hls'],3600)
        for name,sha in proof['provenance']['rtl_sha256'].items():
            if hashlib.sha256((rtl/name).read_bytes()).hexdigest()!=sha:raise RuntimeError('Export changed previously verified RTL; inspectbeforeclaim')
        impl=BUILD/'shared_engine_prj/solution1/impl';reports=[str(p) for p in impl.rglob('*') if p.suffix in ['.rpt','.xml','.json']];checkpoints=[str(p) for p in impl.rglob('*.dcp')]
        if not reports:raise RuntimeError('Implementation tool exited without actual reports')
        record.update(status='complete_review_required',tool_completed=True,reports=reports,checkpoints=checkpoints,verified_rtl_unchanged=True,note='Inspect ACTUAL post-route timing/utilization/route completion and unconstrained paths before core_fit_verified; tool exit alone not proof. Full system and board remain unproven.');save(REPORT,record);status('Actual FINAL trained core implementation reports saved',actual_reports=len(reports),core_and_system_fit_claim_pending_review=True)
    except BaseException as exc:record.update(status='needs_attention',error=str(exc),traceback=traceback.format_exc());save(REPORT,record);status('Actual core implementation requires inspection',error=str(exc));raise

if __name__=='__main__':
    with lock():main()
