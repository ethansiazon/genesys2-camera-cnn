"""Prepared finer-head option; not automatically selected or trained.

YOLOv5v7 GPL3 author P2 top-down design: vendor/models/hub/yolov5-p2.yaml.
Engineering adaptation keeps narrow learned P4 context backbone/neck, adds P2
fusion, predicts P2/P3 rather than P3/P4. Active model.py remains unchanged.
"""
import environment
import copy
import torch
from torch import nn
from models.yolo import Model
from model import CONFIG,ANCHORS

def make(anchors=None,seed_checkpoint=None):
    cfg=copy.deepcopy(CONFIG);cfg['nc']=2
    if anchors is not None:cfg['anchors']=anchors
    cfg['head']=cfg['head'][:-1]+[
        [-1,1,'Conv',[128,1,1]],
        [-1,1,'nn.Upsample',[None,2,'nearest']],
        [[2,12],1,'Concat',[1]],
        [-1,3,'C3',[128,False]],
        [[14,10],1,'Detect',[2,cfg['anchors']]]]
    net=Model(cfg,ch=3,nc=2);net.names=['drone','other_flying'];net.nc=2
    net.hyp={'box':.075,'obj':.54,'cls':.01875,'cls_pw':1.,'obj_pw':1.,'fl_gamma':0.,'label_smoothing':0.,'anchor_t':4.}
    transferred=[]
    if seed_checkpoint is not None:
        snapshot=torch.load(seed_checkpoint,map_location='cpu',weights_only=False);parent=snapshot['ema'];state=net.state_dict()
        for key,value in parent.items():
            layer=int(key.split('.')[1])
            if layer<=10 and key in state and state[key].shape==value.shape:state[key]=value;transferred.append(key)
        net.load_state_dict(state)
    return net,{'parameters':sum(p.numel() for p in net.parameters()),'compatible_trained_tensors_transferred':len(transferred),
                'seed_checkpoint':str(seed_checkpoint) if seed_checkpoint else None,'prediction_strides':net.stride.tolist(),
                'family':'YOLOv5v7 narrow P4 context backbone with P2/P3 outputs,ReLU','source_commit':'915bbf294bb74c859f0b41f1c23bc395014ea679',
                'classes':['drone','other_flying'],'scope':'Prepared two-class architecture option. New heads are untrained, compatible parent features alone do not establish accuracy or hardware feasibility.'}

class HardwareGraph(nn.Module):
    def __init__(self,net):
        super().__init__();self.layers=nn.ModuleList(list(net.model[:-1]));self.head2=net.model[-1].m[0];self.head3=net.model[-1].m[1]
    def forward(self,x):
        saved=[]
        for m in self.layers:
            if m.f!=-1:x=saved[m.f] if isinstance(m.f,int) else [x if j==-1 else saved[j] for j in m.f]
            x=m(x);saved.append(x)
        return self.head2(saved[14]),self.head3(saved[10])
