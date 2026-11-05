"""Integer decoder plugged into existing causal feedback, no model/data changes.

Past prediction, image-only motion proposals and retained search plan are the
same as frozen R3. All raw-head ranking/mapping/gates use host-proven integer
decoder arithmetic. Tracker timing/velocity and image preprocessing remain CPU.
"""
import cv2,numpy as np,torch
from data_roi256 import sized
from decoder_work_r2 import config,choose,Q


def observations(net,device,image,record,tracker,now):
    h,w=image.shape[:2];scale=640/w;reference=tracker.prediction(now);search=tracker.search_rectangle(now,h*scale);plans=[]
    if search is not None:
        l,t,r,b=search;plans.append({'rectangle':[round(l/scale),round(t/scale),min(w,round(r/scale)),min(h,round(b/scale))],'origin':'search'})
    maximum_motion=1 if search is not None else 2
    for crop in record['crops'][:maximum_motion]:plans.append({'rectangle':crop['native_rectangle'],'origin':'motion','proposal':crop['proposal_640']})
    if len(plans)>2:raise RuntimeError('Exceeded original two-CNN budget')
    if not plans:return [],plans
    inputs=[];transforms=[]
    for plan in plans:
        l,t,r,b=map(int,plan['rectangle'])
        if not 0<=l<r<=w or not 0<=t<b<=h:raise RuntimeError('Invalid image-only search/motion rectangle')
        canvas,_,tr=sized(image[t:b,l:r],np.empty((0,4),np.float32));inputs.append(torch.from_numpy(np.ascontiguousarray(canvas[:,:,::-1])).permute(2,0,1).float()/255);transforms.append(tr)
    heads=net(torch.stack(inputs).to(device));candidates=[]
    for index,(plan,tr) in enumerate(zip(plans,transforms)):
        cfg=config(plan['rectangle'],tr,w,plan.get('proposal') if plan['origin']=='motion' else None,reference)
        raw=[torch.round(head[index]*16384).to(torch.int32).numpy() for head in heads]
        best=choose(raw,net.anchors_q16,net.strides_integer,cfg)
        if best['valid']:
            candidates.append({'box':(np.asarray(best['box_q16'],float)/Q).tolist(),'score':best['confidence_q16']/Q,'origin':plan['origin'],'raw_index':best['index'],'raw_objectness':best['raw_objectness']})
    return candidates,plans
