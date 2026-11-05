"""Rescore saved original native VAL predictions; no inference/fitting/new data."""
import collections,hashlib,json
from pathlib import Path
import numpy as np
from state import ROOT,save

def metric(records,t):
    p=np.array([bool(r['truth_native']) for r in records]);c=np.array([r['confidence'] for r in records]);hit=np.array([r['selected_iou']>=.5 for r in records]);trigger=c>=t;correct=trigger&p&hit
    tp=int(correct.sum());fp=int((trigger&~correct).sum());fn=int((p&~correct).sum());precision=tp/max(1,tp+fp);recall=tp/max(1,tp+fn)
    keys=[(bool(y),r['source']) for y,r in zip(p,records)];counts=collections.Counter(keys);sources=collections.Counter(k[0] for k in counts);weights=np.array([.5/(sources[k[0]]*counts[k]) for k in keys]);a=weights[correct].sum();b=weights[trigger&~correct].sum();cc=weights[p&~correct].sum();wp=a/max(1e-12,a+b);wr=a/max(1e-12,a+cc)
    return {'threshold':float(t),'balanced_f1':float(2*wp*wr/max(1e-12,wp+wr)),'f1':2*precision*recall/max(1e-12,precision+recall),'precision':precision,'recall':recall,'scene_empty_trigger':float(trigger[~p].mean()) if (~p).any() else None,'tp':tp,'fp_or_bad_box':fp,'fn':fn,'scene_empty_frames':int((~p).sum()),'positive_frames':int(p.sum())}

def main():
    output=ROOT/'MOTION_APPLICATION_BASELINES.json'
    if output.exists():raise RuntimeError('Existing baseline evidence preserved')
    results={}
    for label in ['trial02_motion_val_primary','trial02_motion_adaptive_val']:
        path=ROOT/label/'records.json';raw=path.read_bytes();records=json.loads(raw);eligible=[r for r in records if r['truth_native'] or r['negative_kind']!='other_flying_object']
        scan=[metric(eligible,t) for t in np.arange(.01,.996,.01)];valid=[r for r in scan if r['scene_empty_trigger'] is not None and r['scene_empty_trigger']<=.05]
        if not valid:raise RuntimeError('No calibrated scene-empty operating point')
        selected=max(valid,key=lambda r:r['balanced_f1']);pos=[r for r in eligible if r['truth_native']]
        results[label]={'selected':selected,'retained_frames':len(eligible),'excluded_other_flying_frames':len(records)-len(eligible),'raw_geometry':float(np.mean([r['selected_iou']>=.5 for r in pos])),'saved_records_sha256':hashlib.sha256(raw).hexdigest()}
    save(output,{'results':results,'scope':'Existing saved native VAL predictions, application rules explicitly tolerate rare aircraft/birds. Excludes only original other-flying negative frames, no labels/splits/predictions modified. Original full strict reports preserved. New scores are not gains versus old scores under different rejection rules; use these matched baselines for subsequent ROI candidates. No13/20 or new DAVIS data included.'})
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
