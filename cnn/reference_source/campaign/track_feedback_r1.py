"""Single-object causal association/search logic; no labels or model inside.

Engineering adaptation of high/low-confidence association, not ByteTrack itself.
All state, crops, matching and expiry depend only on PAST available predictions.
Coordinates are in the declared working-width640 image system, timestamps seconds.
"""
from dataclasses import dataclass
import numpy as np

@dataclass(frozen=True)
class Config:
    acquire_score:float=.25
    maintain_score:float=.06
    acquisition_hits:int=2
    maximum_missed_updates:int=2
    maximum_observation_age:float=.60
    maximum_without_high_score:float=1.0
    search_scale:float=4.0
    minimum_search_width:float=80.0
    maximum_search_width:float=256.0
    search_aspect:float=.75
    association_diagonal:float=1.5
    minimum_association_radius:float=8.0
    minimum_side_ratio:float=.25
    maximum_side_ratio:float=4.0

def compatible(boxes,reference,config=Config()):
    boxes=np.asarray(boxes,float).reshape(-1,4);ref=np.asarray(reference,float)
    if ref.shape!=(4,) or not np.isfinite(ref).all() or (ref[2:]<=0).any():return np.zeros(len(boxes),bool)
    ratios=boxes[:,2:]/ref[2:];distance=((boxes[:,:2]-ref[:2])**2).sum(1)
    radius=max(config.minimum_association_radius,config.association_diagonal*float(np.linalg.norm(ref[2:])))
    return np.isfinite(boxes).all(1)&(boxes[:,2:]>0).all(1)&(ratios>=config.minimum_side_ratio).all(1)&(ratios<=config.maximum_side_ratio).all(1)&(distance<=radius**2)

def best_candidate(boxes,scores,allowed,origin):
    boxes=np.asarray(boxes,float).reshape(-1,4);scores=np.asarray(scores,float).reshape(-1)
    if len(boxes)!=len(scores) or len(allowed)!=len(scores):raise ValueError('Candidate arrays differ')
    valid=np.asarray(allowed,bool)&np.isfinite(scores)&np.isfinite(boxes).all(1)&(boxes[:,2:]>0).all(1)
    if not valid.any():return None
    index=int(np.argmax(np.where(valid,scores,-np.inf)))
    return {'box':boxes[index].tolist(),'score':float(scores[index]),'origin':origin,'raw_index':index}

class Tracker:
    def __init__(self,config=Config()):
        self.config=config;self.box=None;self.velocity=np.zeros(2);self.observed_at=None;self.last_high=None;self.last_score=0.;self.misses=0;self.acquisition=None;self.hits=0;self.events=[];self.last_release_time=-1.

    def reset(self,why,now):
        if self.box is not None:self.events.append({'event':'released','reason':why,'at':float(now)})
        self.box=None;self.velocity[:]=0.;self.observed_at=None;self.last_high=None;self.last_score=0.;self.misses=0;self.acquisition=None;self.hits=0

    def expire(self,now):
        if self.box is not None:
            if now-self.observed_at>self.config.maximum_observation_age+1e-9:self.reset('observation_age',now)
            elif now-self.last_high>self.config.maximum_without_high_score+1e-9:self.reset('no_recent_high_score',now)

    def prediction(self,now):
        self.expire(now)
        if self.box is None:return None
        result=self.box.copy();result[:2]+=self.velocity*max(0.,now-self.observed_at);return result

    def search_rectangle(self,now,image_height):
        predicted=self.prediction(now)
        if predicted is None:return None
        width=float(np.clip(self.config.search_scale*max(predicted[2],predicted[3]/self.config.search_aspect),self.config.minimum_search_width,self.config.maximum_search_width));width=min(width,640.,image_height/self.config.search_aspect);height=width*self.config.search_aspect
        left=float(np.clip(predicted[0]-width/2,0,640-width));top=float(np.clip(predicted[1]-height/2,0,image_height-height))
        return [left,top,left+width,top+height]

    def consume(self,capture_time,available_time,candidates):
        if capture_time>available_time+1e-9 or available_time<self.last_release_time-1e-9:raise ValueError('Noncausal result availability')
        self.last_release_time=available_time;self.expire(available_time)
        config=self.config
        if self.box is not None:
            reference=self.box.copy();reference[:2]+=self.velocity*max(0.,capture_time-self.observed_at)
            valid=[c for c in candidates if c['score']>=config.maintain_score and compatible([c['box']],reference,config)[0]]
            if valid:
                chosen=max(valid,key=lambda c:c['score']);box=np.asarray(chosen['box'],float);dt=capture_time-self.observed_at
                if dt>0:
                    instant=(box[:2]-self.box[:2])/dt;self.velocity=.5*instant+.5*self.velocity
                self.box=box;self.observed_at=capture_time;self.last_score=chosen['score'];self.misses=0
                if chosen['score']>=config.acquire_score:self.last_high=capture_time
                return 'associated'
            self.misses+=1
            if self.misses>config.maximum_missed_updates:self.reset('miss_limit',available_time)
            return 'miss'
        strong=[c for c in candidates if c['origin']=='motion' and c['score']>=config.acquire_score]
        if not strong:self.acquisition=None;self.hits=0;return 'untracked'
        chosen=max(strong,key=lambda c:c['score']);box=np.asarray(chosen['box'],float)
        previous=self.acquisition
        if previous is not None and compatible([box],previous['box'],config)[0] and capture_time-previous['time']<=.41:self.hits+=1
        else:self.hits=1
        self.acquisition={'box':box,'time':capture_time,'score':chosen['score']}
        if self.hits>=config.acquisition_hits:
            self.box=box;self.observed_at=capture_time;self.last_high=capture_time;self.last_score=chosen['score'];self.misses=0;self.velocity=np.zeros(2)
            if previous is not None and capture_time>previous['time']:self.velocity=(box[:2]-previous['box'][:2])/(capture_time-previous['time'])
            self.events.append({'event':'acquired','capture_time':capture_time,'available_time':available_time});self.acquisition=None;self.hits=0;return 'acquired'
        return 'acquiring'

def verify():
    c=Config();t=Tracker(c);a=lambda x,s,origin='motion':{'box':[x,80.,12.,8.],'score':s,'origin':origin}
    assert t.consume(0,.15,[a(50,.8)])=='acquiring' and t.prediction(.15) is None
    assert t.consume(.2,.35,[a(52,.8)])=='acquired'
    assert np.allclose(t.prediction(.4)[:2],[54,80])
    # Lower confidence supports a real existing trajectory, not a new acquisition.
    assert t.consume(.4,.55,[a(54,.08,'search')])=='associated'
    assert t.prediction(.6) is not None
    u=Tracker(c);assert u.consume(0,.1,[a(50,.08)])=='untracked'
    # A high-scoring far distractor must not replace the candidate inside the gate.
    assert t.consume(.6,.75,[a(200,.99),a(56,.08,'search')])=='associated'
    assert t.box[0]==56
    # No infinite ghost: expiry is tied to capture age, including processing delay.
    assert t.prediction(1.21) is None
    q=Tracker(c);q.consume(0,0,[a(50,.8)]);q.consume(.2,.2,[a(52,.8)])
    frozen=q.prediction(.3).copy();q.consume(.4,.4,[a(54,.8)])
    assert np.allclose(frozen,[53,80,12,8])
    boxes=np.array([[10.,10,4,4],[51,80,12,8],[52,80,100,100]])
    chosen=best_candidate(boxes,[.99,.2,.9],compatible(boxes,[50,80,12,8]),'search')
    assert chosen['raw_index']==1
    # Score ties choose the first raw candidate deterministically.
    assert best_candidate(boxes[:2],[.2,.2],[True,True],'motion')['raw_index']==0
    try:q.consume(.6,.3,[])
    except ValueError:pass
    else:raise AssertionError('Backwards availability accepted')
    return {'passed':True,'checks':['Two-hit motion acquisition','No low-score acquisition','Low-score search association','Past-only velocity forecast','High-confidence far distractor rejection before ranking','Bounded output age including latency','Earlier snapshot unchanged by future result','Size-ratio gate and deterministic raw-index ties','Monotonic availability guard'],'scope':'Controller logic synthetic checks only; not CNN accuracy, fixed-point hardware or field tracking proof'}

if __name__=='__main__':
    import json
    print(json.dumps(verify(),indent=2))
