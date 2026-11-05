"""Same input/sampling contract, with verified author labels and all multi-drone targets."""
import environment
import json,random
import cv2,numpy as np,torch
from state import ROOT
from data import W,H,SEED,letterbox,tensor,metrics,iou,sampling

def prepare():
    path=ROOT/'data_manifest_v2.json'
    if not path.exists():raise RuntimeError('Complete author-table reconstruction first')
    return json.loads(path.read_text())

class Data(torch.utils.data.Dataset):
    def __init__(self,rows,augment=False):self.rows=rows;self.augment=augment
    def __len__(self):return len(self.rows)
    def __getitem__(self,i):
        r=self.rows[i];arr=r.get('boxes',[r['box']] if r['box'][2]>0 else []);boxes=np.asarray(arr,np.float32).reshape(-1,4)
        if r['kind']=='origin_full':
            image=cv2.imread(r['origin_source'])
            if image is None:raise RuntimeError('Missing original source image')
            h,w=image.shape[:2]
            if abs(w/h-4/3)>.01:
                image=cv2.imread(r['image_path'])
            else:boxes=boxes*np.array([w/320,h/240,w/320,h/240],np.float32)
        else:image=cv2.imread(r['image_path'])
        if image is None:raise RuntimeError('Unreadable registered image')
        image,_,tr=letterbox(image)
        if len(boxes):boxes=boxes*np.array([tr[0],tr[1],tr[0],tr[1]],np.float32)+np.array([tr[2],tr[3],0,0],np.float32)
        if self.augment:
            if random.random()<.5:
                image=np.ascontiguousarray(image[:,::-1])
                if len(boxes):boxes[:,0]=W-boxes[:,0]
            if random.random()<.7:
                hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV).astype(np.float32);hsv[:,:,1]*=random.uniform(.75,1.25);hsv[:,:,2]*=random.uniform(.65,1.3);hsv[:,:,1:]=np.clip(hsv[:,:,1:],0,255);image=cv2.cvtColor(hsv.astype(np.uint8),cv2.COLOR_HSV2BGR)
            if random.random()<.1:image=cv2.GaussianBlur(image,(3,3),0)
        if not np.isfinite(boxes).all() or (boxes[:,2:]<0).any():raise RuntimeError('Invalid audited boxes')
        return tensor(image),torch.from_numpy(np.ascontiguousarray(boxes)),i

def collate(batch):
    images,boxlists,ids=zip(*batch);targets=[];actual=[]
    for i,boxes in enumerate(boxlists):
        actual.append(boxes[0] if len(boxes) else torch.zeros(4))
        for b in boxes:
            if min(b[2:])>0:targets.append(torch.cat((torch.tensor([float(i),0]),b/torch.tensor([W,H,W,H]))))
    return torch.stack(images),torch.stack(targets) if targets else torch.empty(0,6),torch.stack(actual),list(ids)
