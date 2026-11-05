"""Prepared deployment-ROI data path. Does not change the running global trial.

Object-guided crops are TRAIN augmentation only. Runtime/VAL proposal geometry
must remain image-only. Partial targets cannot silently become empty negatives.
"""
import environment
import collections, random
import cv2, numpy as np, torch

W,H=256,192

def read_native(row):
    boxes=np.array([o['box'] for o in row['objects']],np.float32).reshape(-1,4)
    classes=np.array([o['class'] for o in row['objects']],np.float32)
    if row['objects_unit']=='native_source':image=cv2.imread(row['origin_source'])
    elif row['kind']=='origin_full':
        image=cv2.imread(row['origin_source'])
        if image is None:raise RuntimeError('Missing original registered source')
        h,w=image.shape[:2]
        if abs(w/h-4/3)>.01:image=cv2.imread(row['image_path'])
        elif len(boxes):boxes*=np.array([w/320,h/240,w/320,h/240],np.float32)
    else:image=cv2.imread(row['image_path'])
    if image is None:raise RuntimeError('Missing registered image')
    return image,boxes,classes

def crop_rectangle(image,boxes,rectangle):
    l,t,r,b=rectangle
    if not (0<=l<r<=image.shape[1] and 0<=t<b<=image.shape[0]):raise ValueError('Invalid image crop')
    if not len(boxes):return image[t:b,l:r],boxes.copy(),np.zeros(0,dtype=bool)
    low=boxes[:,:2]-boxes[:,2:]/2;high=boxes[:,:2]+boxes[:,2:]/2
    lo=np.maximum(low,[l,t]);hi=np.minimum(high,[r,b]);extent=np.maximum(0,hi-lo)
    fractions=extent.prod(1)/np.maximum(1e-12,boxes[:,2:].prod(1))
    if np.any((fractions>0)&(fractions<.98)):return None
    keep=fractions>=.98;out=np.c_[(lo[keep]+hi[keep])/2-[l,t],extent[keep]].astype(np.float32)
    return image[t:b,l:r],out,keep

def augment_crop(image,boxes,classes):
    h,w=image.shape[:2];maximum=min(w,h*4/3)
    if len(boxes):
        chosen=boxes[random.randrange(len(boxes))];cx,cy,bw,bh=chosen
        if bw<=0 or bh<=0:raise RuntimeError('Invalid TRAIN object')
        cw=min(maximum,max(W*bw/random.uniform(24,80),bw*1.5,bh*2.,16.));ch=cw*.75
        if cw<bw or ch<bh:return image,boxes,classes
        for _ in range(4):
            x=cx+random.uniform(-.35,.35)*(cw-bw);y=cy+random.uniform(-.35,.35)*(ch-bh)
            left=int(round(np.clip(x-cw/2,0,w-cw)));top=int(round(np.clip(y-ch/2,0,h-ch)))
            rect=(left,top,min(w,left+round(cw)),min(h,top+round(ch)))
            result=crop_rectangle(image,boxes,rect)
            if result is not None and len(result[1]):
                patch,new,keep=result;return patch,new,classes[keep]
        return image,boxes,classes
    cw=max(8.,maximum*random.uniform(.125,.65));ch=cw*.75
    left=random.randint(0,max(0,w-round(cw)));top=random.randint(0,max(0,h-round(ch)))
    return image[top:top+round(ch),left:left+round(cw)],boxes,classes

def sized(image,boxes,width=W,height=H):
    h,w=image.shape[:2];scale=min(width/w,height/h);nw,nh=round(w*scale),round(h*scale);px,py=(width-nw)//2,(height-nh)//2
    out=np.full((height,width,3),114,np.uint8);out[py:py+nh,px:px+nw]=cv2.resize(image,(nw,nh),interpolation=cv2.INTER_AREA if scale<1 else cv2.INTER_LINEAR)
    transformed=boxes*np.array([nw/w,nh/h,nw/w,nh/h],np.float32)+np.array([px,py,0,0],np.float32)
    return out,transformed,(nw/w,nh/h,px,py)

class Data(torch.utils.data.Dataset):
    def __init__(self,rows,augment=False):self.rows=rows;self.augment=augment
    def __len__(self):return len(self.rows)
    def __getitem__(self,index):
        row=self.rows[index];image,boxes,classes=read_native(row)
        if self.augment:
            if row['split']!='train':raise RuntimeError('TRAIN augmentation cannot receive VAL/test')
            if random.random()<.8:image,boxes,classes=augment_crop(image,boxes,classes)
        image,boxes,_=sized(image,boxes)
        if self.augment:
            if random.random()<.5:
                image=np.ascontiguousarray(image[:,::-1])
                if len(boxes):boxes[:,0]=W-boxes[:,0]
            if random.random()<.7:
                hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV).astype(np.float32);hsv[:,:,1]*=random.uniform(.75,1.25);hsv[:,:,2]*=random.uniform(.65,1.3);hsv[:,:,1:]=np.clip(hsv[:,:,1:],0,255);image=cv2.cvtColor(hsv.astype(np.uint8),cv2.COLOR_HSV2BGR)
            if random.random()<.1:image=cv2.GaussianBlur(image,(3,3),0)
        if not np.isfinite(boxes).all() or (boxes[:,2:]<=0).any():raise RuntimeError('Invalid transformed positive geometry')
        return torch.from_numpy(np.ascontiguousarray(image[:,:,::-1])).permute(2,0,1).float()/255,torch.from_numpy(np.c_[classes,boxes].astype(np.float32)),index

def collate(batch):
    images,objects,ids=zip(*batch);h,w=images[0].shape[1:];targets=[];actual=[]
    for i,items in enumerate(objects):
        drones=items[items[:,0]==0];actual.append(drones[0,1:] if len(drones) else torch.zeros(4))
        for item in items:targets.append(torch.cat((torch.tensor([float(i)]),item[:1],item[1:]/torch.tensor([w,h,w,h]))))
    return torch.stack(images),torch.stack(targets) if targets else torch.empty(0,6),torch.stack(actual),list(ids)

def sampling(rows):
    gm={'drone':.60,'empty':.25,'hard_negative':.15};vm={'full':.15,'roi':.25,'motion_fixed':.45,'motion_adaptive':.15}
    groups=collections.defaultdict(lambda:collections.defaultdict(lambda:collections.defaultdict(lambda:collections.defaultdict(list))))
    for i,r in enumerate(rows):groups[r['group']][r['source']][r['sequence']][r['view']].append(i)
    weights=np.zeros(len(rows))
    for g,sources in groups.items():
        for _,sequences in sources.items():
            for _,views in sequences.items():
                total=sum(vm[v] for v in views)
                for view,ids in views.items():weights[ids]=gm[g]/len(sources)/len(sequences)*vm[view]/total/len(ids)
    return torch.from_numpy(weights/weights.sum())
