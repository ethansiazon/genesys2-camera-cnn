"""Prepare TRAIN-only native-resolution motion proposals for a possible next trial.

No running training files are changed. No VAL/test frames are used to train.
Motion proposes independently; author labels annotate/reject ambiguous crops only.
"""
import collections,ctypes,hashlib,json,os,time
from pathlib import Path
import cv2,numpy as np
from dense_video_audit import truth
from motion_proposal_probe import Motion,PARAMS,verify

ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
OUT=ROOT/'motion_training_prepared';CACHE=OUT/'cache'

def save(path,obj):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2));os.replace(tmp,path)

class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),('total',ctypes.c_ulonglong),('available',ctypes.c_ulonglong),('page',ctypes.c_ulonglong),('available_page',ctypes.c_ulonglong),('virtual',ctypes.c_ulonglong),('available_virtual',ctypes.c_ulonglong),('extended',ctypes.c_ulonglong)]

def guard():
    m=Memory();m.length=ctypes.sizeof(m);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    if m.available<2*2**30:raise RuntimeError('Data preparation stopped below2GiB free; running trainer untouched')

def geometry(proposal,image_shape,boxes):
    h,w=image_shape[:2];scale=640/w;x,y,_=proposal
    left=int(round(np.clip(x-40,0,640-80)/scale));top=int(round(np.clip(y-30,0,h*scale-60)/scale))
    right=min(w,int(round(left+80/scale)));bottom=min(h,int(round(top+60/scale)))
    transformed=[]
    for cx,cy,bw,bh in boxes:
        lo=np.maximum([cx-bw/2,cy-bh/2],[left,top]);hi=np.minimum([cx+bw/2,cy+bh/2],[right,bottom]);extent=np.maximum(0,hi-lo)
        fraction=float(np.prod(extent)/max(1e-12,bw*bh))
        if 0<fraction<.98:return None # visible partial target: don't silently label background
        if fraction>=.98:
            transformed.append([float((lo[0]+hi[0])/2-left),float((lo[1]+hi[1])/2-top),float(extent[0]),float(extent[1])])
    transformed.sort(key=lambda b:b[2]*b[3],reverse=True)
    return (left,top,right,bottom),transformed

def geometry_checks():
    good=geometry([100,100,1],(480,640,3),[[100,100,20,10]])
    if good[0]!=(60,70,140,130) or good[1]!=[[40.,30.,20.,10.]]:raise RuntimeError('Crop transform failed')
    if geometry([100,100,1],(480,640,3),[[140,100,20,10]]) is not None:raise RuntimeError('Partial target was not excluded')
    if geometry([100,100,1],(480,640,3),[[300,300,20,10]])[1]:raise RuntimeError('Outside target included')
    if len(geometry([100,100,1],(480,640,3),[[90,100,10,10],[110,100,8,8]])[1])!=2:raise RuntimeError('Multi-target lost')
    return verify()

def paired_frames(job,indices):
    wanted=set(indices)|{i-3 for i in indices}
    if job['source']=='DUT_Anti_UAV':
        paths=sorted((PROJECT/'training_datasets/dut_anti_uav'/job['sequence']).glob('*.jpg'))
        for i in sorted(wanted):
            image=cv2.imread(str(paths[i]))
            if image is None:raise RuntimeError('Unreadable TRAIN native image')
            yield i,image
    else:
        cap=cv2.VideoCapture(job['video']);n=0
        try:
            while n<=max(wanted):
                if not cap.grab():raise RuntimeError('Native TRAIN video ended early')
                if n in wanted:
                    ok,image=cap.retrieve()
                    if not ok:raise RuntimeError('Native TRAIN video retrieve failed')
                    yield n,image
                n+=1
        finally:cap.release()

def main():
    cv2.setNumThreads(1);OUT.mkdir(exist_ok=True);CACHE.mkdir(exist_ok=True)
    manifest=OUT/'manifest.json'
    if manifest.exists():raise RuntimeError('Prepared motion data already exists; inspect, do not overwrite')
    tests=geometry_checks();raw=(ROOT/'data_manifest_v2.json').read_bytes();d=json.loads(raw);tables=json.loads((ROOT/'halmstad_author_tables.json').read_text());jobs=[]
    for source in ['DUT_Anti_UAV','DroneDetectionThesis']:
        train={r['sequence'] for r in d['train'] if r['source']==source};val={r['sequence'] for r in d['val'] if r['source']==source}
        if train&val:raise RuntimeError('Native TRAIN/VAL sequence overlap')
        if source=='DUT_Anti_UAV' and train&{'video13','video20'}:raise RuntimeError('Watched development clips in TRAIN')
        for seq in sorted(train):
            if source=='DUT_Anti_UAV':
                labels=truth(seq);job={'source':source,'sequence':seq,'frames':len(labels),'boxes':[[b.tolist()] if b[2]>0 else [] for b in labels]}
            else:
                t=tables[seq];labels=[]
                for row in t['labels']:labels.append([[x+bw/2,y+bh/2,bw,bh] for x,y,bw,bh in row['DRONE']])
                job={'source':source,'sequence':seq,'frames':t['frame_count'],'boxes':labels,'video':t['video'],'mat_sha256':t['mat_sha256']}
            jobs.append(job)
    plan={'base_manifest_sha256':hashlib.sha256(raw).hexdigest(),'motion_parameters':PARAMS,'primary_crop_working_pixels':[80,60],
          'maximum_proposals':2,'pairs_per_train_sequence':16,'lag_frames':3,'geometry_and_translation_tests':tests,
          'sequences':[{'source':j['source'],'sequence':j['sequence'],'frames':j['frames']} for j in jobs],
          'scope':'Prepared training-only proposals, not used in active trial02. Labels annotate crops but do not propose them. Ambiguous partial-drone crops excluded. Existing source groups/splits retained. No validation, test or watched13/20 imagery included.'}
    save(OUT/'PLAN.json',plan);rows=[];counts=collections.Counter();started=time.time()
    for number,job in enumerate(jobs,1):
        guard();seq=job['sequence'];indices=sorted(set(np.linspace(3,job['frames']-1,min(16,job['frames']-3),dtype=int).tolist()));stored={};selected=set(indices)
        for i,image in paired_frames(job,indices):
            # Only lagged frames needed in memory; all others are discarded.
            stored[i]=image
            if i in selected:
                motion=Motion();motion.propose(stored[i-3]);proposals,facts=motion.propose(image)
                for rank,proposal in enumerate(proposals[:2]):
                    g=geometry(proposal,image.shape,job['boxes'][i])
                    if g is None:counts['ambiguous_partial_excluded']+=1;continue
                    (left,top,right,bottom),boxes=g;file=CACHE/f'{job["source"]}_{seq}_{i:06d}_{rank}.jpg'
                    if not cv2.imwrite(str(file),image[top:bottom,left:right],[cv2.IMWRITE_JPEG_QUALITY,96]):raise RuntimeError('Crop write failed')
                    hard=not boxes and job['source']=='DroneDetectionThesis' and not seq.startswith('V_DRONE_')
                    group='drone' if boxes else 'hard_negative' if hard else 'empty';counts[group]+=1
                    rows.append({'split':'train','source':job['source'],'sequence':seq,'frame_index':i,'view':'roi','kind':'native_motion_roi','group':group,
                                 'category':'DRONE' if boxes else 'MOTION_HARD_NEGATIVE' if hard else 'EMPTY_MOTION',
                                 'image_path':str(file),'box':boxes[0] if boxes else [0.,0.,0.,0.],'boxes':boxes,
                                 'origin_native_rectangle':[left,top,right,bottom],'proposal_rank':rank,'proposal_640':proposal,
                                 'annotation':'Exact author-native TRAIN boxes; label-free phase-compensated frame-difference proposals; all fully-contained targets.'})
                # Retain only earlier frames still needed by a later selected pair.
            future={j-3 for j in indices if j>i}
            stored={k:v for k,v in stored.items() if k in future}
        save(OUT/'progress.json',{'sequence':seq,'completed_sequences':number,'total_sequences':len(jobs),'entries':len(rows),'counts':dict(counts),'seconds':round(time.time()-started,1)})
        if number%20==0:print(f'TRAIN motion crops {number}/{len(jobs)} sequences; {len(rows)} entries; {dict(counts)}',flush=True)
    result={'train':rows,'counts':dict(counts),'sequence_count':len(jobs),'seconds':time.time()-started,'plan':plan}
    save(manifest,result);print(json.dumps({k:v for k,v in result.items() if k not in ['train','plan']}),flush=True)

if __name__=='__main__':main()
