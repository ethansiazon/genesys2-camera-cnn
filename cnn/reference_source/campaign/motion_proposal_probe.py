"""CPU-only acquisition diagnostic, NOT CNN accuracy or an FPGA implementation.

Inspired by Hobden et al. 2022 background differencing; translation compensation
uses OpenCV phaseCorrelate. Parameters fixed before scoring; GT enters score only.
No training/model changes. Full-size proposal crops need explicit memory budgeting.
"""
import json,time
from pathlib import Path
import cv2,numpy as np
from dense_video_audit import truth

ROOT=Path(__file__).resolve().parent
PARAMS={'working_width':640,'frame_step':3,'max_proposals':4,'nms_radius':32,
        'minimum_residual':8.,'mad_multiplier':6.,'crop_sizes':[[80,60],[128,96]],
        'phase_response_minimum':.12,'maximum_translation_pixels':40.}

class Motion:
    def __init__(self):self.previous=None;self.window=None
    def propose(self,image):
        h,w=image.shape[:2];scale=640/w
        gray=cv2.cvtColor(cv2.resize(image,(640,round(h*scale))),cv2.COLOR_BGR2GRAY).astype(np.float32)
        gray=cv2.GaussianBlur(gray,(3,3),0)
        if self.previous is None:
            self.previous=gray;self.window=cv2.createHanningWindow((gray.shape[1],gray.shape[0]),cv2.CV_32F)
            return [],{'shift':[0.,0.],'phase_response':0.,'warmup':True}
        previous=self.previous;self.previous=gray
        # phaseCorrelate can modify inputs while windowing: explicit copies.
        shift,response=cv2.phaseCorrelate(previous.copy(),gray.copy(),self.window)
        dx,dy=shift
        if not np.isfinite([dx,dy,response]).all() or response<.12 or max(abs(dx),abs(dy))>40:dx=dy=0.
        matrix=np.float32([[1,0,dx],[0,1,dy]])
        aligned=cv2.warpAffine(previous,matrix,(gray.shape[1],gray.shape[0]),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
        valid=cv2.warpAffine(np.ones_like(gray,np.uint8),matrix,(gray.shape[1],gray.shape[0]),flags=cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT)
        valid=cv2.erode(valid,np.ones((7,7),np.uint8));valid[:4]=0;valid[-4:]=0;valid[:,:4]=0;valid[:,-4:]=0
        residual=np.abs(gray-aligned);values=residual[valid>0]
        med=float(np.median(values));mad=float(np.median(np.abs(values-med)))
        threshold=max(8.,med+6.*1.4826*mad)
        # Summed local change preserves compact targets; suppression limits redundancy.
        residual=np.maximum(0.,residual-threshold)*valid
        score=cv2.boxFilter(residual,-1,(5,5),normalize=False)
        proposals=[]
        for _ in range(4):
            _,maximum,_,point=cv2.minMaxLoc(score)
            if maximum<=0:break
            x,y=point;proposals.append([float(x),float(y),float(maximum)])
            cv2.circle(score,(x,y),32,0.,-1)
        return proposals,{'shift':[float(dx),float(dy)],'phase_response':float(response),'residual_threshold':threshold,'warmup':False}

def score(proposals,box,scale,shape):
    # Labels are used ONLY here, after proposals are produced.
    b=np.asarray(box)*scale;out={}
    for cw,ch in PARAMS['crop_sizes']:
        for k in [1,2,4]:
            covered=False
            for x,y,_ in proposals[:k]:
                left=np.clip(x-cw/2,0,shape[1]-cw);top=np.clip(y-ch/2,0,shape[0]-ch)
                covered|=bool(b[0]-b[2]/2>=left and b[0]+b[2]/2<=left+cw and b[1]-b[3]/2>=top and b[1]+b[3]/2<=top+ch)
            out[f'{cw}x{ch}_top{k}_whole_target_coverage']=covered
    return out

def verify():
    rng=np.random.default_rng(20261017);image=rng.integers(10,245,(240,320,3),dtype=np.uint8)
    m=Motion();m.propose(image)
    moved=cv2.warpAffine(image,np.float32([[1,0,4],[0,1,-3]]),(320,240),borderMode=cv2.BORDER_REFLECT)
    _,facts=m.propose(moved)
    if np.linalg.norm(np.asarray(facts['shift'])-[8,-6])>.75:raise RuntimeError('Translation direction/scale failed')
    if not score([[100,100,1]],[100,100,20,10],1,(480,640))['80x60_top1_whole_target_coverage']:raise RuntimeError('Coverage coordinate test failed')
    if score([[100,100,1]],[300,300,20,10],1,(480,640))['80x60_top1_whole_target_coverage']:raise RuntimeError('False coverage')
    return facts

def main():
    cv2.setNumThreads(1);verified=verify();results={};started=time.time()
    # Fixed independent VAL recordings first; watched 13/20 are development only.
    for seq in ['video05','video10','video14','video13','video20']:
        frames=sorted((ROOT.parent/'training_datasets/dut_anti_uav'/seq).glob('*.jpg'));gt=truth(seq)
        if len(gt)!=len(frames):raise RuntimeError('GT alignment '+seq)
        m=Motion();records=[];totals={};positive=0;proposed=0;counts=[];shifts=[]
        for i in range(0,len(frames),3):
            image=cv2.imread(str(frames[i]));h,w=image.shape[:2];candidates,facts=m.propose(image)
            counts.append(len(candidates));shifts.append(facts['shift']);proposed+=bool(candidates)
            evaluated=bool(gt[i][2]>0 and not facts['warmup'])
            hits=score(candidates,gt[i],640/w,(round(h*640/w),640)) if evaluated else {}
            if evaluated:
                positive+=1
                for key,value in hits.items():totals[key]=totals.get(key,0)+int(value)
            records.append({'frame':i,'proposals_640':candidates,'facts':facts,'positive_for_scoring':evaluated,'coverage':hits})
        results[seq]={'sampled_frames':len(records),'evaluated_positive_frames':positive,'mean_proposals':float(np.mean(counts)),
                      'fraction_frames_with_motion_proposals':proposed/len(records),
                      'whole_target_proposal_coverage':{k:v/max(1,positive) for k,v in totals.items()},
                      'median_abs_translation_640':np.median(np.abs(shifts),axis=0).tolist()}
        (ROOT/(seq+'_motion_proposals.json')).write_text(json.dumps(records))
        print(seq,json.dumps(results[seq]),flush=True)
    report={'parameters_frozen_before_scoring':PARAMS,'translation_test':verified,'results':results,'seconds':time.time()-started,
            'sources':['https://www.frontiersin.org/journals/space-technologies/articles/10.3389/frspt.2022.878010/full','https://docs.opencv.org/4.x/d7/df3/group__imgproc__motion.html'],
            'scope':'Exploratory motion-proposal coverage ONLY, not detection accuracy, no CNN involved. Labels never produce proposals. No thresholds tuned per clip. Missing/hovering targets, wind, panning and multiple candidates remain risks. Full system needs CNN confirmation and negative-video validation; no FPGA fit/throughput proof.'}
    (ROOT/'motion_proposal_probe.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()
