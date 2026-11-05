"""Predeclared motion-agreement + full native causal cadence selection for V5.
No labels in proposals, CNNranking, update clock, confirmation or forecasting.
"""
import json,time
import cv2,numpy as np,torch
from data_roi256 import sized
from evaluate_roi_decoder_policies import choose
from calibrate_roi_temporal import prepare,apply
from score_motion_application_baselines import metric
from data import iou
from state import ROOT,save,status,guard

@torch.no_grad()
def evaluate(net,device,label,trial,config):
    net.eval();manifest=json.loads((ROOT/config['native_validation']).read_text());rows=[];flat=[];start_time=time.time()
    for seq in manifest['sequences']:
        for r in seq['records']:
            rows.append({'source':seq['source'],'sequence':seq['sequence'],'frame':r['frame'],'truth_native':r['truth_native'],'negative_kind':'other_flying_object' if seq['source']=='DroneDetectionThesis' and not seq['sequence'].startswith('V_DRONE_') else 'scene_empty','confidence':0.,'selected_iou':0.,'selected_box_native':[0.,0.,0.,0.]})
            for patch in r['crops']:flat.append((len(rows)-1,patch,r['native_size'][0]))
    if len(rows)!=5748 or len(flat)!=9471:raise RuntimeError('Original native VAL membership changed')
    rawrows=[dict(r) for r in rows]
    for begin in range(0,len(flat),24):
        guard();batch=flat[begin:begin+24];inputs=[];transforms=[];us=[];vs=[];mx=[];my=[]
        for _,patch,native_w in batch:
            image=cv2.imread(patch['image_path'])
            if image is None:raise RuntimeError('Missing original frozen nativeVALcrop')
            canvas,_,tr=sized(image,np.empty((0,4),np.float32));inputs.append(torch.from_numpy(np.ascontiguousarray(canvas[:,:,::-1])).permute(2,0,1).float()/255);transforms.append(tr);sx,sy,px,py=tr;l,t,_,_=patch['native_rectangle'];x,y,_=patch['proposal_640'];scale=640/native_w;us.append((x/scale-l)*sx+px);vs.append((y/scale-t)*sy+py);mx.append(8*sx/scale);my.append(8*sy/scale)
        pred=net(torch.stack(inputs).to(device))[0].cpu();policies=choose(pred,torch.tensor(us),torch.tensor(vs),torch.tensor(mx),torch.tensor(my))
        for policy,destination in [('raw',rawrows),('motion_agreement',rows)]:
            cs,bs=policies[policy]
            for (index,patch,_),c,b,tr in zip(batch,cs,bs,transforms):
                sx,sy,px,py=tr;l,t,_,_=patch['native_rectangle'];native=np.array([(b[0]-px)/sx+l,(b[1]-py)/sy+t,b[2]/sx,b[3]/sy]);row=destination[index]
                if c>row['confidence']:row.update(confidence=float(c),selected_box_native=native.tolist(),selected_iou=max((float(iou(native,np.array(gt))) for gt in row['truth_native']),default=0.))
        if begin%2400==0:status('V5 checks ALL original native validation crops',evaluation=label,patch=begin,total=len(flat))
    save(trial/(label+'_records.json'),rows);save(trial/(label+'_raw_records.json'),rawrows);series,full=prepare(rows,manifest);eligible=[r for r in full if r['truth_native'] or r['negative_kind']!='other_flying_object'];scan=[]
    for confirmations in [1,2,3]:
        for threshold in np.arange(.05,.801,.01):
            apply(series,full,float(threshold),confirmations,True);score=metric(eligible,float(threshold));score['confirmations']=confirmations;scan.append(score)
        guard()
    valid=[r for r in scan if r['scene_empty_trigger'] is not None and r['scene_empty_trigger']<=.05];selected=max(valid,key=lambda r:r['balanced_f1']);apply(series,full,selected['threshold'],selected['confirmations'],True);strict=metric(full,selected['threshold']);strict['all_negative_trigger']=strict.pop('scene_empty_trigger');strict['all_negative_frames']=strict.pop('scene_empty_frames');raweligible=[r for r in rawrows if r['truth_native'] or r['negative_kind']!='other_flying_object'];rawscan=[metric(raweligible,t) for t in np.arange(.01,.996,.01)];rawpoint=max((r for r in rawscan if r['scene_empty_trigger'] is not None and r['scene_empty_trigger']<=.05),key=lambda r:r['balanced_f1'])
    result={'selection':selected,'raw_sampled_diagnostic':rawpoint,'strict_all_original_frames':strict,'native_frames':len(full),'application_frames':len(eligible),'original_sampled_frames':len(rows),'cnn_patch_calls':len(flat),'seconds':round(time.time()-start_time,1),'policy':'motion_agreement','scope':'Predeclared original native17193GT-frame conditional5Hz clock/confirm1..3/past-onlyvelocity VAL calibration. No GTcrops/state/ranking, no13/20 or external data in selection. RareotheraircraftexcludedONLYapplication, strictallframesretained. Actualprocessinglatencycurrentlyzero; no boardFPS/hover/systemclaim. Native5748rawsampleddiagnostic preserved separately; protocolnotidentical tooldsampledmodelselection.'};save(trial/(label+'_temporal_scan.json'),scan);save(trial/(label+'_temporal_selected_records.json'),full);save(trial/(label+'.json'),result);return result
