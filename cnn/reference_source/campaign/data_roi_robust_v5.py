"""Versioned TRAIN-only robustness data; validation pixels/targets unchanged.
Uses official YOLOv5v7 MixUp against labelled TRAIN-empty backgrounds. This is
an engineering trial, not a claim of reproducing AugMix or published accuracy.
"""
import random,collections
import numpy as np,torch
from data_roi256 import Data as BaseData,collate,sized,W,H
from recalibrate_roi_bn_native import sampling
from utils.augmentations import mixup

class Data(BaseData):
    def __init__(self,rows,augment=False):
        super().__init__(rows,augment);self.last={};self.empty=collections.defaultdict(list)
        if augment:
            for i,row in enumerate(rows):
                if row['split']!='train':raise RuntimeError('Robust TRAIN loader cannot receive VAL/test')
                if row['group']=='empty' and not row['objects']:self.empty[row['source']].append(i)
            if not self.empty:raise RuntimeError('Verified TRAIN-empty donor bank required')
    def __getitem__(self,index):
        image,labels,identity=super().__getitem__(index);self.last={'mixup':False,'contrast':False,'donor':None,'contrast_factor':1.}
        if not self.augment:return image,labels,identity
        canvas=np.rint(image.permute(1,2,0).numpy()*255).clip(0,255).astype(np.uint8)
        # At least8px targetheight/12pxwidth before synthetic fading. Tiny already
        # barely-visible labels do not get this extra visibility reduction.
        visible_enough=not len(labels) or bool(((labels[:,3]>=12)&(labels[:,4]>=8)).all())
        if visible_enough and random.random()<.25:
            source=random.choice(sorted(self.empty));donor=random.choice(self.empty[source]);background,objects,_=BaseData([self.rows[donor]],augment=True)[0]
            if len(objects) or self.rows[donor]['split']!='train':raise RuntimeError('MixUp donor must be labelled TRAIN-empty')
            other=np.rint(background.permute(1,2,0).numpy()*255).clip(0,255).astype(np.uint8);before=labels.clone();original=canvas.copy();mixed,lab=mixup(canvas,labels.numpy(),other,np.empty((0,5),np.float32));canvas=np.rint(.6*original+.4*mixed).clip(0,255).astype(np.uint8);labels=torch.from_numpy(lab.astype(np.float32))
            if not torch.equal(labels,before):raise RuntimeError('Empty-donor MixUp changed object geometry/classes')
            self.last.update(mixup=True,donor=donor,donor_source=source,softened_official_mixup=.4)
        # Applied to positives AND negatives; contrast is not a class cue.
        if visible_enough and not self.last['mixup'] and random.random()<.25:
            factor=random.uniform(.65,.9);mean=canvas.mean((0,1),keepdims=True);canvas=np.rint((canvas.astype(np.float32)-mean)*factor+mean).clip(0,255).astype(np.uint8);self.last.update(contrast=True,contrast_factor=factor)
        return torch.from_numpy(np.ascontiguousarray(canvas)).permute(2,0,1).float()/255,labels,identity
