"""Read-only temporal replay of cached CNN outputs, ALL native author GT frames.
No GT enters update times, motion crops, CNN predictions or consistency state.
Validation selects thresholds/confirmation count; never an unseen-test claim.
"""
import argparse,collections,ctypes,hashlib,json,math,re,time
from pathlib import Path
import numpy as np
from score_motion_application_baselines import metric
from state import ROOT,Memory,save

def consistent(boxes):
    result=np.zeros(len(boxes),bool)
    for i in range(1,len(boxes)):
        a,b=boxes[i-1],boxes[i];lo=np.maximum(a[:2]-a[2:]/2,b[:2]-b[2:]/2);hi=np.minimum(a[:2]+a[2:]/2,b[:2]+b[2:]/2);overlap=np.maximum(0,hi-lo).prod();union=max(1e-12,a[2:].prod()+b[2:].prod()-overlap);distance=float(np.sum((a[:2]-b[:2])**2));size=max(float(np.sum(a[2:]**2)),float(np.sum(b[2:]**2)))
        result[i]=overlap/union>=.1 or distance<=2.25*size
    return result

def confirmation(scores,adjacent,threshold,count):
    accepted=scores>=threshold
    for j in range(1,count):accepted[j:]&=scores[:-j]>=threshold;accepted[:j]=False
    for j in range(count-1):
        if j:accepted[j:]&=adjacent[:-j];accepted[:j]=False
        else:accepted&=adjacent
    return accepted

def overlap(box,truth):
    best=0.
    for gt in truth:
        a=np.array(gt);lo=np.maximum(box[:2]-box[2:]/2,a[:2]-a[2:]/2);hi=np.minimum(box[:2]+box[2:]/2,a[:2]+a[2:]/2);area=np.maximum(0,hi-lo).prod();best=max(best,float(area/max(1e-12,box[2:].prod()+a[2:].prod()-area)))
    return best

def velocities(boxes,frames,scores,adjacent,threshold):
    out=np.zeros((len(boxes),2))
    for i in range(1,len(boxes)):
        if scores[i]>=threshold and scores[i-1]>=threshold and adjacent[i]:
            instant=(boxes[i,:2]-boxes[i-1,:2])/(frames[i]-frames[i-1]);previous_reliable=i>1 and scores[i-2]>=threshold and adjacent[i-1]
            out[i]=.5*instant+.5*out[i-1] if previous_reliable else instant
    return out

def verify():
    boxes=np.array([[0,0,10,10],[1,0,10,10],[2,0,10,10]],float);adj=consistent(boxes)
    if confirmation(np.array([.7,.01,.01]),adj,.1,2).any():raise RuntimeError('Single-frame distractor confirmation failed')
    if confirmation(np.array([.2,.2,.2]),adj,.1,2).tolist()!=[False,True,True]:raise RuntimeError('Two-frame confirmation timing failed')
    if confirmation(np.array([.2,.2,.2]),adj,.1,3).tolist()!=[False,False,True]:raise RuntimeError('Three-frame confirmation timing failed')
    boxes[1,0]=1000
    if confirmation(np.array([.2,.2,.2]),consistent(boxes),.1,2).any():raise RuntimeError('Inconsistent-box confirmation failed')
    boxes=np.array([[0,0,10,10],[6,0,10,10],[12,0,10,10]],float);frames=np.array([0,6,12]);scores=np.array([.2,.2,.2]);v=velocities(boxes,frames,scores,consistent(boxes),.1)
    if not np.allclose(boxes[1,:2]+v[1]*3,[9,0]):raise RuntimeError('Past-only constant-velocity forecast failed')
    future=boxes.copy();future[2,0]=1000
    if not np.array_equal(velocities(future,frames,scores,consistent(future),.1)[:2],v[:2]):raise RuntimeError('Future observation leaked into earlier forecast')

def prepare(records,manifest):
    lookup={(r['source'],r['sequence'],r['frame']):r for r in records};series=[];full=[]
    for seq in manifest['sequences']:
        fps=seq.get('source_fps') or seq.get('assumed_fps')
        if not fps or not math.isfinite(fps) or fps<=0:raise RuntimeError('Source frame rate missing')
        chosen=[];due=0.;calls=0
        for r in seq['records']:
            if r['frame']+1e-8>=due:
                chosen.append(lookup[(seq['source'],seq['sequence'],r['frame'])]);due+=fps/5.;calls+=len(r['crops'])
        frames=np.array([r['frame'] for r in chosen]);scores=np.array([r['confidence'] for r in chosen]);boxes=np.array([r['selected_box_native'] for r in chosen]);mapping=np.searchsorted(frames,np.arange(len(seq['native_truth'])),side='right')-1
        if (mapping<0).any() or not np.isfinite(scores).all() or not np.isfinite(boxes).all():raise RuntimeError('Invalid chronological CNN replay')
        start=len(full)
        for i,truth in enumerate(seq['native_truth']):
            box=boxes[mapping[i]];full.append({'source':seq['source'],'sequence':seq['sequence'],'frame':i,'truth_native':truth,'negative_kind':'other_flying_object' if seq['source']=='DroneDetectionThesis' and not seq['sequence'].startswith('V_DRONE_') else 'scene_empty','confidence':0.,'selected_box_native':box.tolist(),'selected_iou':overlap(box,truth),'measurement_age_frames':int(i-frames[mapping[i]])})
        count=max(1,max(map(len,seq['native_truth'])));truth_array=np.zeros((len(seq['native_truth']),count,4))
        for i,objects in enumerate(seq['native_truth']):
            if objects:truth_array[i,:len(objects)]=objects
        series.append({'source':seq['source'],'sequence':seq['sequence'],'fps':fps,'frames':frames,'scores':scores,'boxes':boxes,'mapping':mapping,'adjacent':consistent(boxes),'start':start,'end':len(full),'cnn_calls':calls,'truth_array':truth_array})
    return series,full

def apply(series,full,threshold,count,forecast=False):
    for s in series:
        accepted=confirmation(s['scores'],s['adjacent'],threshold,count);conf=(s['scores']*accepted)[s['mapping']]
        part=full[s['start']:s['end']]
        if forecast:
            velocity=velocities(s['boxes'],s['frames'],s['scores'],s['adjacent'],threshold);boxes=s['boxes'][s['mapping']].copy();age=np.arange(len(boxes))-s['frames'][s['mapping']];boxes[:,:2]+=velocity[s['mapping']]*age[:,None];truth=s['truth_array'];lo=np.maximum(boxes[:,None,:2]-boxes[:,None,2:]/2,truth[:,:,:2]-truth[:,:,2:]/2);hi=np.minimum(boxes[:,None,:2]+boxes[:,None,2:]/2,truth[:,:,:2]+truth[:,:,2:]/2);area=np.maximum(0,hi-lo).prod(2);union=np.maximum(1e-12,boxes[:,None,2:].prod(2)+truth[:,:,2:].prod(2)-area);ious=(area/union).max(1)
            for r,c,b,i in zip(part,conf,boxes,ious):r.update(confidence=float(c),selected_box_native=b.tolist(),selected_iou=float(i))
        else:
            for r,c in zip(part,conf):r['confidence']=float(c)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--records',type=Path,required=True);parser.add_argument('--name',required=True);parser.add_argument('--forecast',action='store_true');args=parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_]+',args.name):raise RuntimeError('Simple artifact name required')
    folder=ROOT/args.name
    if folder.exists():raise RuntimeError('Existing temporal study preserved')
    folder.mkdir();verify();path=args.records if args.records.is_absolute() else ROOT/args.records;raw=path.read_bytes();manifest_path=ROOT/'motion_validation_prepared/manifest.json';manifest=json.loads(manifest_path.read_text());series,full=prepare(json.loads(raw),manifest);eligible=[r for r in full if r['truth_native'] or r['negative_kind']!='other_flying_object'];scan=[];start=time.time()
    config={'records':str(path),'records_sha256':hashlib.sha256(raw).hexdigest(),'native_manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cnn_updates_target_per_source_second':5,'candidate_confirmations':[1,2,3],'confidence_grid':[.05,.80,.01],'consistency':'IoU>=.1 OR centre-distance<=1.5*maxboxdiagonal; no target-ID/GT seed','past_only_forecast':args.forecast,'forecast_method':'Last-two reliable observed centres; first velocity exact finite difference, subsequent .5new/.5previous; zero when scores/geometry fail. NO future interpolation or GT velocity. Processing latency currentlyzero; actual hardware latency must be replayed before realtime claim.','below_threshold_or_inconsistent':'No output at that update until reconfirmed; hold/past-only forecast only BETWEEN scheduled CNN updates','test_kind':'Original VAL calibration, not unseen-test','native_frames':len(full),'eligible_application_frames':len(eligible),'scope':'CNN inputs/boxes/scores cached from immutable model; update times from clocks ONLY. Every author-native GT frame scored including intervals between CNN updates. True scene-empty labels never control state or cropping. No physical FPS/board claim.'};save(folder/'config.json',config)
    for count in [1,2,3]:
        for threshold in np.arange(.05,.801,.01):
            m=Memory();m.length=ctypes.sizeof(m);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            if m.available<2*2**30:raise RuntimeError('CPU replay stopped below2GiB reserve; GPU job untouched')
            apply(series,full,float(threshold),count,args.forecast);score=metric(eligible,float(threshold));score['confirmations']=count;scan.append(score)
        save(folder/'progress.json',{'completed_confirmation_counts':count,'seconds':round(time.time()-start,1)});print('Temporal validation confirmation count',count,'complete',flush=True)
    valid=[r for r in scan if r['scene_empty_trigger'] is not None and r['scene_empty_trigger']<=.05]
    if not valid:raise RuntimeError('No true scene-empty operating point')
    best=max(valid,key=lambda r:r['balanced_f1']);apply(series,full,best['threshold'],best['confirmations'],args.forecast);strict=metric(full,best['threshold']);strict['all_negative_trigger']=strict.pop('scene_empty_trigger');strict['all_negative_frames']=strict.pop('scene_empty_frames')
    baselines={str(count):max([r for r in valid if r['confirmations']==count],key=lambda r:r['balanced_f1']) if any(r['confirmations']==count for r in valid) else None for count in [1,2,3]}
    clocks=[{'source':s['source'],'sequence':s['sequence'],'source_fps':s['fps'],'native_frames':s['end']-s['start'],'cnn_updates':len(s['frames']),'cnn_patch_calls':s['cnn_calls'],'max_measurement_age_native_frames':max(r['measurement_age_frames'] for r in full[s['start']:s['end']])} for s in series]
    save(folder/'scan.json',scan);save(folder/'selected_records.json',full);save(folder/'COMPLETE.json',{'selected':best,'best_per_confirmation':baselines,'strict_all_original_native_frames':strict,'clocks':clocks,'seconds':round(time.time()-start,1),'scope':'Complete17193nativeGT-frame validation replay with conditional5HzCNN cadence/confirmation and held boxes. No GT influences state/candidate selection. Parameters selected on VAL; NOT independent accuracy, field-camera proof or measured hardware throughput. Original per-frame reports unchanged.'});print(json.dumps({'selected':best,'best_per_confirmation':baselines,'native_frames':len(full),'application_frames':len(eligible)},indent=2))

if __name__=='__main__':main()
