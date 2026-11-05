"""Frozen-candidate VAL-only decoder study; no training/GT-controlled inference.
Compare raw objectness, typed score, and agreement with image-only motion peaks.
"""
import environment
import argparse,ctypes,hashlib,json,time,traceback
import cv2,numpy as np,torch,torch_directml
from model_p2_two_class import make
from data_roi256 import sized
from data import iou
from score_motion_application_baselines import metric
from state import ROOT,Memory,save,status,lock,guard

POLICIES=['raw','typed','motion_agreement','typed_motion_agreement']

def choose(pred,u,v,marginx,marginy):
    allowed=(pred[:,:,0]-u[:,None]).abs()<=pred[:,:,2]/2+marginx[:,None]
    allowed&=(pred[:,:,1]-v[:,None]).abs()<=pred[:,:,3]/2+marginy[:,None]
    raw=pred[:,:,4];typed=raw*pred[:,:,5]
    out={}
    for name,scores in zip(POLICIES,[raw,typed,raw*allowed,typed*allowed]):
        c,j=scores.max(1);out[name]=(c.numpy(),pred[torch.arange(len(pred)),j,:4].numpy())
    return out

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--epoch',type=int,required=True);args=parser.parse_args();out=ROOT/f'roi_epoch{args.epoch:02d}_decoder_val_r1'
    if out.exists():raise RuntimeError('Existing decoder study preserved')
    torch.set_num_threads(3);cv2.setNumThreads(1);checkpoint=ROOT/f'trial04_roi256/epoch_{args.epoch:02d}.pt';snap=torch.load(checkpoint,map_location='cpu',weights_only=False);seed=torch.load(ROOT/snap['config']['seed_checkpoint'],map_location='cpu',weights_only=False);net,_=make(anchors=seed['config']['anchors']);net.load_state_dict(snap['ema']);device=torch_directml.device(0);net.to(device).eval();del snap,seed
    manifest=ROOT/'motion_validation_prepared/manifest.json';d=json.loads(manifest.read_text());records=[];flat=[]
    for seq in d['sequences']:
        for r in seq['records']:
            row={'source':seq['source'],'sequence':seq['sequence'],'frame':r['frame'],'truth_native':r['truth_native'],'negative_kind':'other_flying_object' if seq['source']=='DroneDetectionThesis' and not seq['sequence'].startswith('V_DRONE_') else 'scene_empty','confidence':0.,'selected_iou':0.,'selected_box_native':[0.,0.,0.,0.]};records.append(row)
            for patch in r['crops']:flat.append((len(records)-1,patch,r['native_size'][0]))
    if len(records)!=5748 or len(flat)!=9471:raise RuntimeError('Original native VAL membership changed')
    selected={name:[dict(r) for r in records] for name in POLICIES};out.mkdir();save(out/'FROZEN_CONFIG.json',{'checkpoint':str(checkpoint),'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),'native_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'policies':POLICIES,'motion_gate':'Before max, require image-only motion peak inside each predicted rectangle expanded8working640pixels. Exact same predeclared gate as epoch3small diagnostic, no GT input.','class_score':'Rawobj vs obj*class0; rareotheraircraftexcludedONLYapplicationselection, strictallframes retained.','scope':'Original VAL policy calibration, no new training/newdatasets/13/20policythresholdtuning. No temporal/hardware/field claim.'});start=time.time()
    with torch.no_grad():
        for begin in range(0,len(flat),24):
            guard();batch=flat[begin:begin+24];inputs=[];transforms=[];us=[];vs=[];mx=[];my=[]
            for _,patch,native_w in batch:
                image=cv2.imread(patch['image_path'])
                if image is None:raise RuntimeError('Missing original frozen ROI crop')
                canvas,_,tr=sized(image,np.empty((0,4),np.float32));inputs.append(torch.from_numpy(np.ascontiguousarray(canvas[:,:,::-1])).permute(2,0,1).float()/255);transforms.append(tr);sx,sy,px,py=tr;l,t,_,_=patch['native_rectangle'];x,y,_=patch['proposal_640'];scale=640/native_w;us.append((x/scale-l)*sx+px);vs.append((y/scale-t)*sy+py);mx.append(8*sx/scale);my.append(8*sy/scale)
            p=net(torch.stack(inputs).to(device))[0].cpu();policies=choose(p,torch.tensor(us),torch.tensor(vs),torch.tensor(mx),torch.tensor(my))
            for name,(cs,bs) in policies.items():
                for (index,patch,_),c,b,tr in zip(batch,cs,bs,transforms):
                    sx,sy,px,py=tr;l,t,_,_=patch['native_rectangle'];native=np.array([(b[0]-px)/sx+l,(b[1]-py)/sy+t,b[2]/sx,b[3]/sy]);row=selected[name][index]
                    if c>row['confidence']:row.update(confidence=float(c),selected_box_native=native.tolist(),selected_iou=max((float(iou(native,np.array(gt))) for gt in row['truth_native']),default=0.))
            if begin%2400==0:status('Checking image-only decoder alternatives on original native VAL',patch=begin,total=len(flat))
    results={}
    for name,rows in selected.items():
        eligible=[r for r in rows if r['truth_native'] or r['negative_kind']!='other_flying_object'];scan=[metric(eligible,t) for t in np.arange(.01,.996,.01)];best=max((r for r in scan if r['scene_empty_trigger'] is not None and r['scene_empty_trigger']<=.05),key=lambda r:r['balanced_f1']);strict=metric(rows,best['threshold']);strict['all_negative_trigger']=strict.pop('scene_empty_trigger');strict['all_negative_frames']=strict.pop('scene_empty_frames');results[name]={'selection':best,'strict_all_original_frames':strict};save(out/(name+'_records.json'),rows);save(out/(name+'_scan.json'),scan)
    save(out/'COMPLETE.json',{'epoch':args.epoch,'results':results,'seconds':round(time.time()-start,1),'scope':'Complete same5748nativeVALframes and9471crops, four label-free decoding policies. Calibration only; requires subsequent frozen temporal/external/development tests, actual hardwaredecoder cost and unseenconfirmation.'});print(json.dumps(results,indent=2))

if __name__=='__main__':
    with lock():main()
