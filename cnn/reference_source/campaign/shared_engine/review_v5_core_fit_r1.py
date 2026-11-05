"""Independent evidence audit of actual trained V5 routed core, never system fit."""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(ROOT))
import hashlib,json,re
from state import save,status
BUILD=Path.home()/'fpga_builds/g2_roi_v5_epoch08_output32_r2'
OUT=BUILD/'direct_core_route_r1'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def count(text,name):
    matches=re.findall(re.escape(name)+r'\.*\s*:\s*(\d+)',text)
    if len(matches)!=1:raise RuntimeError('Need unique actual route counter:'+name)
    return int(matches[0])


def main():
    report=HERE/'V5_R2_CORE_FIT_REVIEW.json'
    if report.exists():raise RuntimeError('Existing fit review preserved')
    route=json.loads((HERE/'V5_R2_CORE_ROUTE_R1.json').read_text());rtl=json.loads((HERE/'V5_R2_ACTUAL_RTL.json').read_text());quality=json.loads((ROOT/'v5_fixed_feedback_native_r1/COMPLETE.json').read_text())
    if route['status']!='complete_review_required' or not route['routed'] or not rtl['rtl_passed'] or not quality['within_three_percentage_point_loss']:raise RuntimeError('Actual trained route/RTL/quality gates incomplete')
    for name,digest in route['source_rtl_sha256'].items():
        if sha(OUT/'rtl'/name)!=digest or rtl['provenance']['rtl_sha256'][name]!=digest:raise RuntimeError('Routed source not identical to actual simulated trained RTL')
    text=(OUT/'route_status.rpt').read_text();routable=count(text,'# of routable nets');routed=count(text,'# of fully routed nets');errors=count(text,'# of nets with routing errors')
    checks=(OUT/'check_timing.rpt').read_text();summary={name:int(re.search(r'checking '+name+r' \((\d+)\)',checks).group(1)) for name in ['no_clock','constant_clock','unconstrained_internal_endpoints','multiple_clock','loops','partial_input_delay','partial_output_delay','latch_loops','no_input_delay','no_output_delay']}
    timing=json.loads((OUT/'timing_values.json').read_text());full=(OUT/'timing.rpt').read_text()
    if 'All user specified timing constraints are met.' not in full:raise RuntimeError('Actual report does not establish clock timing')
    lines=(OUT/'utilization.rpt').read_text().splitlines();top=next(l for l in lines if re.match(r'\| cnn_engine\s+\|',l));fields=[v.strip() for v in top.split('|')[1:-1]];n=list(map(int,fields[2:]));lut,logic,lutram,srl,ff,bram36,bram18,dsp=n
    resources={'LUT':lut,'FF':ff,'DSP':dsp,'RAMB36':bram36,'RAMB18':bram18,'BRAM18_equivalent':2*bram36+bram18};fractions={'LUT':lut/203800,'FF':ff/407600,'DSP':dsp/840,'BRAM18_equivalent':(2*bram36+bram18)/890}
    drc=(OUT/'drc.rpt').read_text();severities=re.findall(r'^\|\s*\S+\s*\|\s*(Warning|Error|Critical Warning|Info)\s*\|',drc,re.M)
    if not severities or any(s in ['Error','Critical Warning'] for s in severities):raise RuntimeError('Actual core DRC has errors/critical warnings or summary missing')
    passed=routed==routable and errors==0 and timing['setup_wns_ns']>=0 and timing['hold_whs_ns']>=0 and float(timing['clock_periods_ns'])==10 and timing['blackbox_count']==0 and all(summary[k]==0 for k in ['no_clock','constant_clock','unconstrained_internal_endpoints','multiple_clock','loops','partial_input_delay','partial_output_delay','latch_loops']) and all(f<=.6 for f in fractions.values())
    result={'core_fit_verified':bool(passed),'system_fit_verified':False,'board_inference_demonstrated':False,'trained_checkpoint_sha256':route['checkpoint_sha256'],'actual_postroute_resources':resources,'fractions_of_genesys2':fractions,'actual_timing':timing,'route':{'routable_nets':routable,'fully_routed_nets':routed,'routing_errors':errors},'timing_checks':summary,'warning_scope':'139DRCwarnings:configurationvoltage notspecified,OOCboundarynets nointernalloads,DSPpipeline suggestions. No errors/criticalwarnings. NOTbitstreamready.445input/530outputportsuntimedexternalboundaries, but0internalunconstrainedendpoints. Fullsystemconstraints/configbank/MIG/camera remain required.','evidence_sha256':{n:sha(OUT/n) for n in ['routed.dcp','route_status.rpt','timing.rpt','timing_values.json','utilization.rpt','drc.rpt','check_timing.rpt']},'scope':'Actual trained V5epoch8 full55op/331114parameterR7CNN core, same source as exactactualRTL proof.100MHz placement/routing and internal timing verified. NOTcompletecamera/frontend/controller/decoder/MIGsystem fit or physicalDDR/boardFPS/field proof.'};save(report,result);status('Actual trained CNN core fit verified',core_fit_verified=bool(passed),resources=resources,setup_wns_ns=timing['setup_wns_ns'],system_fit_verified=False)
    if not passed:raise RuntimeError('Actual routed evidence failed core fit audit')


if __name__=='__main__':main()
