"""Integer-only decoder reference, with ROI-to-working-image geometry.

Coordinates are Q16 in the 640-wide working image used by the frozen tracker.
Raw logits rank candidates; sigmoid probabilities are separately reported.
No target labels enter this module.
"""
import numpy as np

Q=65536
TABLE=np.rint(Q/(1+np.exp(-(np.arange(6145)/256-12)))).astype(np.int64)


def sigmoid(raw):
    raw=np.asarray(raw,np.int64);result=TABLE[((raw+196608+32)>>6).clip(0,6144)]
    return np.where(raw<=-196608,0,np.where(raw>=196608,Q,result))


def round_even16(value):
    value=np.asarray(value,np.int64);base=value>>16;remainder=value-(base<<16)
    return base+((remainder>32768)|((remainder==32768)&((base&1)!=0)))


def transform(value,multiplier,offset=0):
    return (round_even16(np.asarray(value,np.int64)*int(multiplier))+int(offset)).clip(-(1<<31),(1<<31)-1)


def config(rectangle,tr,native_width,proposal=None,reference=None):
    sx,sy,px,py=tr;l,t,_,_=rectangle;scale=640/native_width;kx,ky=scale/sx,scale/sy
    result={'sx':round(kx*Q),'sy':round(ky*Q),'ox':round((l*scale-px*kx)*Q),'oy':round((t*scale-py*ky)*Q),'u':0,'v':0,'mx':8*Q,'my':8*Q,'use_motion':int(proposal is not None),'rx':0,'ry':0,'rw':0,'rh':0,'use_association':int(reference is not None)}
    if proposal is not None:result.update(u=round(proposal[0]*Q),v=round(proposal[1]*Q))
    if reference is not None:result.update(zip(('rx','ry','rw','rh'),map(lambda x:round(float(x)*Q),reference)))
    if any(not -(1<<31)<=v<(1<<31) for v in result.values()) or result['sx']<=0 or result['sy']<=0:raise ValueError('Decoder control value outside signed32 range')
    return result


def decode_all(heads,anchors_q16,strides,cfg):
    """Input raw A24F14 integer heads in CHW, output Q16boxes/rawlogits."""
    boxes=[];logits=[]
    for level,raw in enumerate(heads):
        raw=np.asarray(raw,np.int64);c,h,w=raw.shape
        if c!=21:raise ValueError('Expected actual two-class/3-anchor raw head')
        fields=raw.reshape(3,7,h,w);yy,xx=np.mgrid[:h,:w];p=sigmoid(fields[:,:4]);stride=int(strides[level])
        x=(2*p[:,0]-32768+xx*Q)*stride;y=(2*p[:,1]-32768+yy*Q)*stride
        bw=((2*p[:,2])**2*np.asarray(anchors_q16[level])[:,0,None,None]+(1<<31))>>32
        bh=((2*p[:,3])**2*np.asarray(anchors_q16[level])[:,1,None,None]+(1<<31))>>32
        box=np.stack((transform(x,cfg['sx'],cfg['ox']),transform(y,cfg['sy'],cfg['oy']),transform(bw,cfg['sx']),transform(bh,cfg['sy'])),-1)
        boxes.append(box.reshape(-1,4));logits.append(fields[:,4].reshape(-1))
    return np.concatenate(boxes),np.concatenate(logits)


def allowed(boxes,cfg):
    boxes=np.asarray(boxes,np.int64);valid=(boxes[:,2:]>0).all(1)
    if cfg['use_motion']:
        valid&=(np.abs(boxes[:,0]-cfg['u'])<=boxes[:,2]//2+cfg['mx'])&(np.abs(boxes[:,1]-cfg['v'])<=boxes[:,3]//2+cfg['my'])
    if cfg['use_association']:
        rw,rh=int(cfg['rw']),int(cfg['rh'])
        if rw<=0 or rh<=0:return np.zeros(len(boxes),bool)
        valid&=(boxes[:,2]*4>=rw)&(boxes[:,3]*4>=rh)&(boxes[:,2]<=rw*4)&(boxes[:,3]<=rh*4)
        dx=boxes[:,0]-cfg['rx'];dy=boxes[:,1]-cfg['ry'];radius4=max(4*(8*Q)**2,9*(rw*rw+rh*rh))
        # Normal 640-wide image arithmetic fits int64 exactly. Extreme host
        # tests use Python arbitrary precision instead of overflowing silently.
        if max(int(np.abs(dx).max(initial=0)),int(np.abs(dy).max(initial=0)))>1_000_000_000 or radius4>np.iinfo(np.int64).max:
            distance4=4*(dx.astype(object)**2+dy.astype(object)**2)
        else:distance4=4*(dx*dx+dy*dy)
        valid&=np.asarray(distance4<=radius4,bool)
    return valid


def choose(heads,anchors_q16,strides,cfg):
    boxes,raw=decode_all(heads,anchors_q16,strides,cfg);valid=allowed(boxes,cfg)
    if not valid.any():return {'box_q16':[0]*4,'confidence_q16':0,'raw_objectness':-8388608,'index':0,'valid':0}
    index=int(np.argmax(np.where(valid,raw,-8388609)))
    return {'box_q16':boxes[index].tolist(),'confidence_q16':int(sigmoid(raw[index])),'raw_objectness':int(raw[index]),'index':index,'valid':1}
