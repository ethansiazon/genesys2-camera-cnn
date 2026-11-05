"""Fresh sequential native VAL inference for causal search feedback, not cache replay.

Labels are attached ONLY after the current prediction. Same original46 recordings
and17193 native frames. Retained crops come from previously AVAILABLE detections.
Processing delay changes available state BEFORE each future crop, requiring a
separate full inference replay per delay. Never pretend old top1 caches suffice.
"""
import environment
import argparse,collections,dataclasses,hashlib,json,math,time
from pathlib import Path
import cv2,numpy as np,torch
from model_p2_two_class import make
from data_roi256 import sized
from track_feedback_r1 import Config,Tracker,compatible,best_candidate,verify
from calibrate_roi_temporal import overlap
from score_motion_application_baselines import metric
from state import ROOT,PROJECT,save,status,guard,lock

def fingerprint(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def observations(net,device,image,record,tracker,now):
    h,w=image.shape[:2];scale=640/w;reference=tracker.prediction(now);search=tracker.search_rectangle(now,h*scale);plans=[]
    if search is not None:
        l,t,r,b=search;plans.append({'rectangle':[round(l/scale),round(t/scale),min(w,round(r/scale)),min(h,round(b/scale))],'origin':'search'})
    maximum_motion=1 if search is not None else 2
    for crop in record['crops'][:maximum_motion]:plans.append({'rectangle':crop['native_rectangle'],'origin':'motion','proposal':crop['proposal_640']})
    if len(plans)>2:raise RuntimeError('Exceeded declared two-CNN-call budget')
    if not plans:return [],plans
    inputs=[];transforms=[]
    for plan in plans:
        l,t,r,b=map(int,plan['rectangle'])
        if not 0<=l<r<=w or not 0<=t<b<=h:raise RuntimeError('Invalid predicted/image-only native ROI')
        canvas,_,tr=sized(image[t:b,l:r],np.empty((0,4),np.float32));inputs.append(torch.from_numpy(np.ascontiguousarray(canvas[:,:,::-1])).permute(2,0,1).float()/255);transforms.append(tr)
    pred=net(torch.stack(inputs).to(device))[0].cpu().numpy()
    if not np.isfinite(pred).all():raise RuntimeError('Nonfinite decoded network output')
    candidates=[]
    for row,plan,tr in zip(pred,plans,transforms):
        sx,sy,px,py=tr;l,t,_,_=plan['rectangle'];boxes=row[:,:4].astype(float).copy();boxes[:,0]=((boxes[:,0]-px)/sx+l)*scale;boxes[:,1]=((boxes[:,1]-py)/sy+t)*scale;boxes[:,2]=boxes[:,2]/sx*scale;boxes[:,3]=boxes[:,3]/sy*scale
        allowed=np.ones(len(boxes),bool)
        if plan['origin']=='motion':
            x,y,_=plan['proposal'];allowed&=(np.abs(boxes[:,0]-x)<=boxes[:,2]/2+8)&(np.abs(boxes[:,1]-y)<=boxes[:,3]/2+8)
        if reference is not None:allowed&=compatible(boxes,reference,tracker.config)
        chosen=best_candidate(boxes,row[:,4],allowed,plan['origin'])
        if chosen is not None:candidates.append(chosen)
    return candidates,plans

def scheduled(seq):
    fps=seq.get('source_fps') or seq.get('assumed_fps')
    if fps is None or fps<=0:raise RuntimeError('Source clock required')
    due=0.;chosen={}
    for row in seq['records']:
        if row['frame']+1e-8>=due:chosen[row['frame']]=row;due+=fps/10.
    return float(fps),chosen

def evaluate_sequence(seq,net,device,latency,config,out):
    name=seq['sequence'];fps,chosen=scheduled(seq);tracker=Tracker(config);pending=collections.deque();records=[];updates=[];calls=0;start=time.time();capture=None
    if seq['source']=='DUT_Anti_UAV':
        paths=sorted((PROJECT/'training_datasets/dut_anti_uav'/name).glob('*.jpg'))
        if len(paths)!=len(seq['native_truth']):raise RuntimeError('Native source membership changed')
    else:
        capture=cv2.VideoCapture(seq['video'])
        if not capture.isOpened():raise RuntimeError('Native source video unavailable')
    def release(now):
        while pending and pending[0]['available_time']<=now+1e-9:
            result=pending.popleft();result['association_result']=tracker.consume(result['capture_time'],now,result['candidates']);result['actual_available_native_time']=now;updates.append(result)
    try:
        for index in range(len(seq['native_truth'])):
            now=index/fps;release(now)
            if capture is not None and not capture.grab():raise RuntimeError('Native source ended early')
            if index in chosen:
                guard();image=cv2.imread(str(paths[index])) if capture is None else capture.retrieve()[1]
                if image is None:raise RuntimeError('Native frame could not be decoded')
                if image.shape[1]!=chosen[index]['native_size'][0] or image.shape[0]!=chosen[index]['native_size'][1]:raise RuntimeError('Native image geometry changed')
                candidates,plans=observations(net,device,image,chosen[index],tracker,now);calls+=len(plans)
                pending.append({'capture_frame':index,'capture_time':now,'available_time':now+latency,'candidates':candidates,'rois':plans});release(now)
            prediction=tracker.prediction(now);active=prediction is not None;scale=640/seq['records'][0]['native_size'][0];native=(prediction/scale).tolist() if active else [0.,0.,0.,0.]
            # Label access is after every state/crop/CNN/association/output decision.
            truth=seq['native_truth'][index]
            records.append({'source':seq['source'],'sequence':name,'frame':index,'truth_native':truth,'negative_kind':'other_flying_object' if seq['source']=='DroneDetectionThesis' and not name.startswith('V_DRONE_') else 'scene_empty','confidence':float(active),'tracker_active':active,'neural_confidence':float(tracker.last_score) if active else 0.,'selected_box_native':native,'selected_iou':overlap(np.asarray(native),truth) if active else 0.,'measurement_age_seconds':float(now-tracker.observed_at) if active else None})
            if index%600==0:status('Checking causal search feedback on original native VAL',sequence=name,frame=index,total=len(seq['native_truth']),assumed_delay_seconds=latency)
    finally:
        if capture is not None:capture.release()
    save(out/(name+'_records.json'),records);save(out/(name+'_updates.json'),updates);save(out/(name+'_events.json'),tracker.events)
    return records,{'source':seq['source'],'sequence':name,'frames':len(records),'cnn_updates':len(chosen),'cnn_calls':calls,'maximum_cnn_calls_per_update':max((len(u['rois']) for u in updates),default=0),'acquisitions':sum(e['event']=='acquired' for e in tracker.events),'seconds_offline':round(time.time()-start,1)}
