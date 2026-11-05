"""YOLOv5v7 family challenger, GPL-3.0. Original source and LICENSE in vendor/yolov5.

Engineering adaptation: retain compatible nano backbone layers0..6; use P3/P4 heads,
train with ReLU from the beginning. COCO initialization does not imply pretrained
drone accuracy or equivalence after the activation/topology adaptation.
"""
import environment
import torch
from torch import nn
from models.yolo import Model

ANCHORS=[[4,4,9,7,18,12],[30,22,60,40,120,90]]
CONFIG={'nc':1,'depth_multiple':.33,'width_multiple':.25,'activation':'nn.ReLU()',
 'anchors':ANCHORS,
 'backbone':[[-1,1,'Conv',[64,6,2,2]],[-1,1,'Conv',[128,3,2]],[-1,3,'C3',[128]],[-1,1,'Conv',[256,3,2]],[-1,6,'C3',[256]],[-1,1,'Conv',[512,3,2]],[-1,9,'C3',[512]]],
 'head':[[-1,1,'Conv',[256,1,1]],[-1,1,'nn.Upsample',[None,2,'nearest']],[[4,8],1,'Concat',[1]],[-1,3,'C3',[256,False]],[[10,6],1,'Detect',[1,ANCHORS]]]}

def make(anchors=None,pretrained=True):
    import copy
    cfg=copy.deepcopy(CONFIG)
    if anchors is not None:cfg['anchors']=anchors;cfg['head'][-1][3][1]=anchors
    net=Model(cfg,ch=3,nc=1)
    net.names=['drone'];net.nc=1
    net.hyp={'box':.05,'obj':1.,'cls':.5,'cls_pw':1.,'obj_pw':1.,'fl_gamma':0.,'label_smoothing':0.,'anchor_t':4.}
    transferred=[]
    if pretrained:
        payload=torch.load(environment.ROOT/'downloads/yolov5n_coco_v7.pt',map_location='cpu',weights_only=False)
        original=payload['model'].float().state_dict();state=net.state_dict()
        for k,value in original.items():
            layer=int(k.split('.')[1])
            if layer<=6 and k in state and state[k].shape==value.shape:state[k]=value;transferred.append(k)
        net.load_state_dict(state)
    return net,{'parameters':sum(x.numel() for x in net.parameters()),'transferred_tensor_count':len(transferred),'transferred_keys':transferred,'family':'YOLOv5v7 P3/P4 narrow backbone, ReLU training activation','source_commit':'915bbf294bb74c859f0b41f1c23bc395014ea679'}

class HardwareGraph(nn.Module):
    """Raw BCHW convolution heads; grid decode/NMS belong to explicit postprocessing."""
    def __init__(self,net):
        super().__init__()
        self.layers=nn.ModuleList(list(net.model[:-1]));self.head3=net.model[-1].m[0];self.head4=net.model[-1].m[1]
    def forward(self,x):
        saved=[]
        for m in self.layers:
            if m.f!=-1:x=saved[m.f] if isinstance(m.f,int) else [x if j==-1 else saved[j] for j in m.f]
            x=m(x);saved.append(x)
        return self.head3(saved[10]),self.head4(saved[6])
