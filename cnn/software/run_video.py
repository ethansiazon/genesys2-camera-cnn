"""CPU replay with retained weights/R9. No training, downloads or board access."""
import environment
import argparse,collections,json,math,time
from pathlib import Path
import cv2,numpy as np,torch
from runtime import load,guard,sha
from observations_integer_r2 import observations
from track_feedback_r1 import Config,Tracker
from motion_proposal_probe import Motion
from prepare_motion_train import geometry

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True);p.add_argument('--output',required=True,help='New .mp4 path')
    p.add_argument('--max-frames',type=int,default=0,help='0 = all frames, otherwise a short smoke test')
    a=p.parse_args();src=Path(a.input).resolve();dest=Path(a.output).resolve()
    records=dest.with_suffix('.jsonl');summary=dest.with_suffix('.summary.json')
    if not src.is_file():raise FileNotFoundError(src)
    if any(x.exists() for x in [dest,records,summary]):raise RuntimeError('Use new output names; existing results preserved')
    if dest.suffix.lower()!='.mp4':raise ValueError('Use .mp4 output')
    dest.parent.mkdir(parents=True,exist_ok=True)
    net,preferred=load();cv2.setNumThreads(1)
    cap=cv2.VideoCapture(str(src));writer=None
    if not cap.isOpened():raise RuntimeError('Cannot read video')
    fps=float(cap.get(cv2.CAP_PROP_FPS));expected=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));h=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not math.isfinite(fps) or fps<=0:raise RuntimeError('Valid native FPS metadata required')
    if min(w,h)<=0 or h*640/w<60:raise RuntimeError('Unsupported empty/extreme-aspect video')
    config=Config(**preferred['controller']);tracker=Tracker(config);motion=Motion()
    pending=collections.deque();due=0.;index=0;outputs=0;begin=time.time();error=None;complete=False
    def release(now):
        while pending and pending[0][0]<=now+1e-9:
            _,captured,candidates=pending.popleft();tracker.consume(captured,now,candidates)
    try:
        writer=cv2.VideoWriter(str(dest),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
        if not writer.isOpened():raise RuntimeError('Video encoder could not open output')
        with records.open('w',encoding='utf-8') as log,torch.no_grad():
            while not a.max_frames or index<a.max_frames:
                ok,image=cap.read()
                if not ok:break
                if image.shape[:2]!=(h,w):raise RuntimeError('Frame dimensions changed')
                now=index/fps;release(now)
                if index+1e-8>=due:
                    guard();proposals,_=motion.propose(image);crops=[]
                    for proposal in proposals[:2]:
                        rectangle,_=geometry(proposal,image.shape,[])
                        crops.append({'native_rectangle':rectangle,'proposal_640':proposal})
                    candidates,plans=observations(net,torch.device('cpu'),image,{'crops':crops},tracker,now)
                    if len(plans)>2:raise RuntimeError('Exceeded frozen crop budget')
                    pending.append((now+.09,now,candidates));due+=fps/10.;release(now)
                prediction=tracker.prediction(now);active=prediction is not None
                box=(prediction/(640/w)).tolist() if active else [0.,0.,0.,0.]
                row={'frame':index,'source_time_seconds':now,'tracker_active':active,
                     'neural_confidence':float(tracker.last_score) if active else 0.,
                     'box_native':box,'centre_native':box[:2] if active else None,
                     'measurement_age_seconds':now-tracker.observed_at if active else None}
                log.write(json.dumps(row)+'\n');outputs+=int(active)
                if active:
                    x,y,bw,bh=box
                    cv2.rectangle(image,(round(x-bw/2),round(y-bh/2)),(round(x+bw/2),round(y+bh/2)),(235,30,235),2)
                    cv2.drawMarker(image,(round(x),round(y)),(235,30,235),cv2.MARKER_CROSS,12,2)
                cv2.putText(image,'V5/R9 CPU replay | '+('TRACK' if active else 'SEARCH'),(8,20),cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1,cv2.LINE_AA)
                writer.write(image);index+=1
                if index%50==0:print(f'{index}/{expected} frames; {net.calls} CNN crops',flush=True)
        if expected>0 and index!=min(expected,a.max_frames or expected):raise RuntimeError('Input ended before expected frame count')
        if net.clips:raise RuntimeError('Fixed activation clipping occurred; inspect before accepting results')
        complete=True
    except BaseException as exc:
        error=str(exc);raise
    finally:
        cap.release()
        if writer is not None:writer.release()
        summary.write_text(json.dumps({'complete':complete,'error':error,'input':str(src),'input_sha256':sha(src),
            'frames':index,'native_fps':fps,'native_size':[w,h],'prediction_frames':outputs,
            'cnn_calls':net.calls,'clipped_values':net.clips,'offline_seconds':round(time.time()-begin,2),
            'controller':preferred['controller'],'checkpoint_sha256':preferred['checkpoint_sha256'],
            'scope':'CPU fixed-point replay, same R9 proposal/association policy. Native source clock, up to 10 updates/s with assumed 90ms availability. Not FPGA speed or accuracy; no ground truth used.'},indent=2),encoding='utf-8')
    print('Saved:',dest,'and per-frame JSONL/summary. Output frequency is not accuracy.')
if __name__=='__main__':main()
