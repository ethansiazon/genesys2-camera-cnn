"""Versioned development data, fixed original membership and native author annotations."""
import environment
import json,hashlib,random
from collections import Counter,defaultdict
from pathlib import Path
import cv2,numpy as np,torch
from dense_video_audit import truth
from state import ROOT,PROJECT,save,status
W,H=384,288
SEED=20261017

def iou(a,b):
    a=np.asarray(a);b=np.asarray(b);lo=np.maximum(a[...,:2]-a[...,2:]/2,b[...,:2]-b[...,2:]/2);hi=np.minimum(a[...,:2]+a[...,2:]/2,b[...,:2]+b[...,2:]/2)
    area=np.maximum(0,hi-lo).prod(-1);return area/np.maximum(1e-8,a[...,2:].prod(-1)+b[...,2:].prod(-1)-area)

def letterbox(image,box=None):
    h,w=image.shape[:2];s=min(W/w,H/h);nw,nh=round(w*s),round(h*s);px,py=(W-nw)//2,(H-nh)//2
    out=np.full((H,W,3),114,np.uint8);out[py:py+nh,px:px+nw]=cv2.resize(image,(nw,nh),interpolation=cv2.INTER_AREA if s<1 else cv2.INTER_LINEAR)
    tr=(nw/w,nh/h,px,py)
    b=None if box is None else np.array([box[0]*tr[0]+px,box[1]*tr[1]+py,box[2]*tr[0],box[3]*tr[1]],np.float32)
    return out,b,tr

def tensor(image):return torch.from_numpy(np.ascontiguousarray(image[:,:,::-1])).permute(2,0,1).float()/255

def prepare():
    path=ROOT/'data_manifest.json'
    if path.exists():return json.loads(path.read_text())
    old=json.loads((PROJECT/'genesys2_roi_redesign_v2/data/prepared.json').read_text());train=[];val=[];withheld=[]
    for split,rows in [('train',old['train']),('val',old['val_full'])]:
        for r in rows:
            r=dict(r)
            if split=='train' and r['source']=='DUT_Anti_UAV' and r['sequence'] in ['video13','video20']:
                withheld.append(r['image_path']);continue
            r['kind']='prepared_crop' if r['view']=='roi' else 'origin_full'
            (train if split=='train' else val).append(r)
    allowed=sorted({r['sequence'] for r in train if r['source']=='DUT_Anti_UAV'})
    oldkeys={(r['sequence'],int(r['frame_index'])) for r in train if r['source']=='DUT_Anti_UAV' and r['view']=='full'}
    added=0
    for seq in allowed:
        gt=truth(seq);frames=sorted((PROJECT/'training_datasets/dut_anti_uav'/seq).glob('*.jpg'))
        if len(gt)!=len(frames):raise RuntimeError('Author annotation alignment mismatch '+seq)
        for i in np.unique(np.linspace(0,len(frames)-1,min(240,len(frames)),dtype=int)):
            if (seq,int(i)) in oldkeys:continue
            b=gt[int(i)];present=b[2]>0
            train.append({'split':'train','group':'drone' if present else 'empty','source':'DUT_Anti_UAV','sequence':seq,'category':'DRONE' if present else 'EMPTY_ANTIUAV','frame_index':int(i),'image_path':str(frames[int(i)]),'box':b.tolist(),'view':'full','kind':'official_full','annotation':'official author frame-level tracking GT'})
            added+=1
    for split,rows in [('train',train),('val',val)]:
        if any(r['split']!=split for r in rows):raise RuntimeError('Split changed')
    ts={(r['source'],r['sequence']) for r in train if r['source']=='DUT_Anti_UAV'};vs={(r['source'],r['sequence']) for r in val if r['source']=='DUT_Anti_UAV'}
    if ts&vs:raise RuntimeError('DUT sequence leakage')
    result={'train':train,'val':val};save(path,result)
    summary={'train_entries':len(train),'val_entries':len(val),'added_official_native_train_frames':added,'withheld_training_views_from_development_videos':len(withheld),'DUT_train_sequences':allowed,'DUT_val_sequences':sorted(x[1] for x in vs),'source_counts':dict(Counter(r['source'] for r in train)),'scope':'Original splits retained, video13/video20 excluded from new training. Original models may have historical exposure to video13. Watched clips remain development, not independent test. No test/holdout training.'}
    save(ROOT/'data_summary.json',summary);status('New detector data registered',**summary);return result

class Data(torch.utils.data.Dataset):
    def __init__(self,rows,augment=False):self.rows=rows;self.augment=augment
    def __len__(self):return len(self.rows)
    def __getitem__(self,i):
        r=self.rows[i];b=np.array(r['box'],np.float32)
        if r['kind']=='origin_full':
            image=cv2.imread(r['origin_source'])
            if image is None:raise RuntimeError('Missing original source cache')
            h,w=image.shape[:2]
            # Audited full-box coordinates were in320x240; source caches are4:3.
            if abs(w/h-4/3)>.01:
                image=cv2.imread(r['image_path']);b=np.array(r['box'],np.float32)
            else:b*=np.array([w/320,h/240,w/320,h/240],np.float32)
        else:
            image=cv2.imread(r['image_path'])
        if image is None:raise RuntimeError('Unreadable registered image')
        image,b,tr=letterbox(image,b)
        if self.augment:
            if random.random()<.5:image=np.ascontiguousarray(image[:,::-1]);b[0]=W-b[0] if b[2]>0 else 0
            if random.random()<.7:
                hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV).astype(np.float32);hsv[:,:,1]*=random.uniform(.75,1.25);hsv[:,:,2]*=random.uniform(.65,1.3);hsv[:,:,1:]=np.clip(hsv[:,:,1:],0,255);image=cv2.cvtColor(hsv.astype(np.uint8),cv2.COLOR_HSV2BGR)
            if random.random()<.1:image=cv2.GaussianBlur(image,(3,3),0)
        if not np.isfinite(b).all() or min(b[2:])<0:raise RuntimeError('Invalid registered box')
        return tensor(image),torch.from_numpy(b),i

def collate(batch):
    ims,boxes,ids=zip(*batch);boxes=torch.stack(boxes);targets=[]
    for i,b in enumerate(boxes):
        if min(b[2:])>0:targets.append(torch.cat((torch.tensor([float(i),0]),b/torch.tensor([W,H,W,H]))))
    target=torch.stack(targets) if targets else torch.empty(0,6)
    return torch.stack(ims),target,boxes,list(ids)

def sampling(rows):
    groupmix={'drone':.65,'empty':.30,'hard_negative':.05};groups=defaultdict(lambda:defaultdict(lambda:defaultdict(lambda:defaultdict(list))))
    for i,r in enumerate(rows):groups[r['group']][r['source']][r['sequence']][r['view']].append(i)
    weights=np.zeros(len(rows))
    for group,sources in groups.items():
        for source,seqs in sources.items():
            for seq,views in seqs.items():
                for view,ids in views.items():
                    vm=(.65 if view=='full' else .35) if len(views)>1 else 1.
                    weights[ids]=groupmix[group]/len(sources)/len(seqs)*vm/len(ids)
    return torch.from_numpy(weights/weights.sum())

def metrics(conf,boxes,truths,rows,t):
    conf=np.asarray(conf);boxes=np.asarray(boxes);actual=np.asarray(truths);positive=actual[:,2]>0;trigger=conf>=t;correct=trigger&positive&(iou(boxes,actual)>=.5)
    tp=int(correct.sum());fp=int((trigger&~correct).sum());fn=int((positive&~correct).sum());p=tp/max(1,tp+fp);r=tp/max(1,tp+fn)
    keys=[(bool(y),row['source']) for y,row in zip(positive,rows)];counts=Counter(keys);n=Counter(k[0] for k in counts)
    weight=np.array([.5/(n[k[0]]*counts[k]) for k in keys]);a=weight[correct].sum();b=weight[trigger&~correct].sum();c=weight[positive&~correct].sum()
    wp=a/max(1e-12,a+b);wr=a/max(1e-12,a+c)
    return {'threshold':float(t),'f1':2*p*r/max(1e-12,p+r),'balanced_f1':float(2*wp*wr/max(1e-12,wp+wr)),'precision':p,'recall':r,'negative_trigger':float(trigger[~positive].mean()) if (~positive).any() else None,'tp':tp,'fp_or_bad_box':fp,'fn':fn,'sources':{s:{'positive_recall':float(correct[positive&np.array([x['source']==s for x in rows])].mean()) if (positive&np.array([x['source']==s for x in rows])).any() else None} for s in sorted({x['source'] for x in rows})}}
