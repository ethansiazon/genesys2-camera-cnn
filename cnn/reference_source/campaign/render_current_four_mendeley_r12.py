"""Requested original four test clips, retained fixed V5 + frozen R9 policy.

No labels, fitting, per-video tuning, resampled time, or actuator work. Native
video FPS supplies the clock; CNN updates at most10Hz,90ms ASSUMEDavailability.
"""
import environment
import collections,csv,hashlib,json,math,time,traceback
from pathlib import Path
import cv2,numpy as np,torch
from state import ROOT,PROJECT,save,status,guard,lock
from evaluate_v5_integer_decoder_r2 import IntegerNet
from observations_integer_r2 import observations
from track_feedback_r1 import Config,Tracker
from motion_proposal_probe import Motion
from prepare_motion_train import geometry

NAMES=['f1_1_EO_dji_mavic_2_range_close.mp4','9_dji2_range_medium.mp4','f2_8_EO_dji_mavic_2.mp4','f2_10_EO_dji_mavic_2.mp4']
SOURCE=PROJECT/'demo_videos/mendeley_selected'
OUT=PROJECT/'outputs/video_demos/v5_r9_other_test_videos'
BUILD=Path.home()/'fpga_builds/g2_roi_v5_epoch08_output32_r2'
DECODER=Path.home()/'fpga_builds/g2_v5_decoder_work_r2'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))

def drawing(image,row,name):
    h,w=image.shape[:2];s=min(1280/w,720/h);nw,nh=round(w*s),round(h*s);px=(1280-nw)//2;py=48+(720-nh)//2
    canvas=np.full((768,1280,3),30,np.uint8);canvas[py:py+nh,px:px+nw]=cv2.resize(image,(nw,nh))
    if row['tracker_active']:
        x,y,bw,bh=row['box_native'];cx,cy=px+round(x*s),py+round(y*s)
        cv2.rectangle(canvas,(px+round((x-bw/2)*s),py+round((y-bh/2)*s)),(px+round((x+bw/2)*s),py+round((y+bh/2)*s)),(235,30,235),2,cv2.LINE_AA)
        cv2.drawMarker(canvas,(cx,cy),(235,30,235),cv2.MARKER_CROSS,16,2)
    state='TRACK OUTPUT' if row['tracker_active'] else 'SEARCHING'
    cv2.putText(canvas,f"V5 + R9 | {name} | frame {row['frame']} | {state} | score {row['neural_confidence']:.2f}",(10,20),cv2.FONT_HERSHEY_SIMPLEX,.47,(245,245,245),1,cv2.LINE_AA)
    cv2.putText(canvas,'Magenta: predicted box + centre | No ground-truth labels | Fixed-point CPU replay; not board inference',(10,40),cv2.FONT_HERSHEY_SIMPLEX,.47,(235,235,235),1,cv2.LINE_AA)
    return canvas

def render(video,net,config,number):
    name=video.stem;complete=OUT/(name+'_COMPLETE.json')
    if complete.exists():
        result=read(complete)
        for key,digest in result['files_sha256'].items():assert sha(OUT/key)==digest
        assert sha(video)==result['input_sha256'];return result
    guard();capture=cv2.VideoCapture(str(video));assert capture.isOpened()
    fps=float(capture.get(cv2.CAP_PROP_FPS));expected=int(capture.get(cv2.CAP_PROP_FRAME_COUNT));w=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH));h=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not math.isfinite(fps) or fps<=0:raise RuntimeError('Actual input video FPS required')
    destination=OUT/(name+'_v5_r9_detected.mp4');writer=cv2.VideoWriter(str(destination),cv2.VideoWriter_fourcc(*'mp4v'),fps,(1280,768));assert writer.isOpened()
    tracker=Tracker(config);motion=Motion();pending=collections.deque();rows=[];updates=[];tiles=[];wanted={expected//8,3*expected//8,5*expected//8,7*expected//8};due=0.;index=0;calls=0;clipping_before=net.clips;begin=time.time();net.sequence=name
    def release(now):
        while pending and pending[0]['available_time']<=now+1e-9:
            result=pending.popleft();result['association_result']=tracker.consume(result['capture_time'],now,result['candidates']);result['actual_available_native_time']=now;updates.append(result)
    status('Rendering original test video with current model',video=number,total_videos=4,sequence=name,frame=0,total=expected,training=False)
    try:
        with torch.no_grad():
            while True:
                ok,image=capture.read()
                if not ok:break
                assert image.shape[:2]==(h,w)
                now=index/fps;release(now)
                if index+1e-8>=due:
                    guard();proposals,facts=motion.propose(image);crops=[]
                    for proposal in proposals[:2]:
                        rectangle,_=geometry(proposal,image.shape,[]);crops.append({'native_rectangle':rectangle,'proposal_640':proposal})
                    candidates,plans=observations(net,torch.device('cpu'),image,{'crops':crops},tracker,now)
                    assert len(plans)<=2;calls+=len(plans);pending.append({'capture_frame':index,'capture_time':now,'available_time':now+.09,'candidates':candidates,'rois':plans,'motion_facts':facts});due+=fps/10.;release(now)
                prediction=tracker.prediction(now);active=prediction is not None;box=(prediction/(640/w)).tolist() if active else [0.,0.,0.,0.]
                row={'frame':index,'source_time_seconds':now,'tracker_active':active,'neural_confidence':float(tracker.last_score) if active else 0.,'box_native':box,'centre_native':box[:2] if active else None,'measurement_age_seconds':now-tracker.observed_at if active else None};rows.append(row)
                canvas=drawing(image,row,name);writer.write(canvas)
                if index in wanted:tiles.append(cv2.resize(canvas,(640,384)))
                if index%150==0:status('Current model video progress',video=number,total_videos=4,sequence=name,frame=index,total=expected)
                index+=1
    finally:capture.release();writer.release()
    assert index==expected,'Incomplete native input read'
    net_clips=net.clips-clipping_before
    if net_clips:raise RuntimeError('Actual fixed activation clipping observed; preserve evidence for inspection')
    cap=cv2.VideoCapture(str(destination));assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT))==expected
    assert abs(cap.get(cv2.CAP_PROP_FPS)-fps)<.01
    for position in [0,expected//2,expected-1]:
        cap.set(cv2.CAP_PROP_POS_FRAMES,position);ok,pixels=cap.read();assert ok and pixels.shape[:2]==(768,1280)
    cap.release()
    if len(tiles)==4:assert cv2.imwrite(str(OUT/(name+'_preview.jpg')),np.vstack([np.hstack(tiles[:2]),np.hstack(tiles[2:])]))
    save(OUT/(name+'_records.json'),rows);save(OUT/(name+'_updates.json'),updates);save(OUT/(name+'_events.json'),tracker.events)
    with (OUT/(name+'_frames.csv')).open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=['frame','source_time_seconds','tracker_active','neural_confidence','box_native','centre_native','measurement_age_seconds']);writer.writeheader();writer.writerows(rows)
    files=[destination,OUT/(name+'_records.json'),OUT/(name+'_updates.json'),OUT/(name+'_events.json'),OUT/(name+'_frames.csv'),OUT/(name+'_preview.jpg')]
    result={'sequence':name,'input_path':str(video),'input_sha256':sha(video),'source_native_size':[w,h],'source_fps':fps,'frames':index,'source_duration_seconds':index/fps,'output_video':str(destination),'prediction_frames':sum(r['tracker_active'] for r in rows),'prediction_frame_fraction':sum(r['tracker_active'] for r in rows)/index,'acquisitions':sum(e['event']=='acquired' for e in tracker.events),'cnn_calls':calls,'clipped_values':net_clips,'seconds_offline':round(time.time()-begin,1),'verified_video_frames_and_start_middle_end_decodes':True,'files_sha256':{p.name:sha(p) for p in files},'scope':'Original unlabelled previouslywatched Mendeley video, all native frames, same fixedV5epoch8/R9 .15/.06/twohit/maxmiss1. Output fraction is NOT accuracy. Max10Hz/twoCNNperupdate/90msASSUMEDavailable; CPUmotion/resize/tracker andfixedreference. NativeFPSplayback, not physical FPGA/system speed.'}
    save(complete,result);status('Current model test video complete',video=number,total_videos=4,sequence=name,frames=index,prediction_frames=result['prediction_frames']);return result

def main():
    guard();torch.set_num_threads(2);cv2.setNumThreads(1);OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'COMPLETE.json').exists():raise RuntimeError('Existing current-model video results preserved')
    preferred=read(ROOT/'PREFERRED_INFERENCE_R9.json');frozen=read(ROOT/'v5_retained_acquisition_native_r9/FROZEN_CONFIG.json')
    assert sha(ROOT/'trial05_roi_robust/epoch_08.pt')==preferred['checkpoint_sha256']==frozen['checkpoint_sha256']
    assert sha(BUILD/'quantized_fx.pt')==preferred['quantized_model_sha256']==frozen['quantized_model_sha256']
    for name in ['observations_integer_r2.py','decoder_work_r2.py','track_feedback_r1.py','data_roi256.py']:assert sha(ROOT/name)==frozen['source_sha256'][name]
    inputs=[SOURCE/n for n in NAMES];assert all(p.exists() for p in inputs)
    config=Config(**preferred['controller']);anchors=np.asarray(read(DECODER/'PREPARED.json')['anchor_q16'],np.int64)
    record={'checkpoint_sha256':preferred['checkpoint_sha256'],'quantized_model_sha256':preferred['quantized_model_sha256'],'controller':config.__dict__,'input_sources_sha256':{p.name:sha(p) for p in inputs},'code_sha256':{n:sha(ROOT/n) for n in ['render_current_four_mendeley_r12.py','observations_integer_r2.py','decoder_work_r2.py','track_feedback_r1.py','motion_proposal_probe.py','prepare_motion_train.py','data_roi256.py']},'parameters':331114,'CNN_ROI_input':[256,192,3],'scope':'Requested visual demonstration on SAMEfouroriginalvideos as experimentC/4, except13/20. No training or tuning, labels unavailable. Inputnativeclock10Hzbudget/90msASSUMEDCPUreplay; not actualboard.'}
    if (OUT/'FROZEN_CONFIG.json').exists():assert read(OUT/'FROZEN_CONFIG.json')==record
    else:save(OUT/'FROZEN_CONFIG.json',record)
    net=IntegerNet(torch.load(BUILD/'quantized_fx.pt',map_location='cpu',weights_only=False).double().eval(),anchors,[4,8]);results=[]
    for number,video in enumerate(inputs,1):results.append(render(video,net,config,number))
    save(OUT/'COMPLETE.json',{'complete':True,'configuration':record,'videos':results,'training':False})
    lines=['# Current V5 + R9 on the four previous test videos','','These are the same original four DJI/Mendeley clips used with Experiments3/4. They were not reconstructed from previous annotated output. Every native source frame is preserved, with its native playback FPS and aspect ratio.','','Magenta box/cross = predicted object box and centre. SEARCHING = no active output. TRACK OUTPUT does not mean the prediction has been verified correct. There are no frame-by-frame ground-truth labels for these clips, so neither output frequency nor confidence is accuracy.','','The current preferred trained V5epoch8 and R9settings are unchanged. The recent failed fine-tunes are not used. This is exact fixed-point CNN/integerdecoder CPU replay with softwaremotion/cropping/tracking. 90msavailability is assumed; this is not physicalboard inference.','','| Video | Frames | Native FPS | Open annotated video |','|---|---:|---:|---|']
    for r in results:lines.append(f"| {r['sequence']} | {r['frames']} | {r['source_fps']:g} | [{r['sequence']}]({Path(r['output_video']).name}) |")
    lines+=['','Each clip also has an every-frame CSV/JSON, update/event logs, preview sheet, verified frame counts/start-middle-end decodes and SHA256 provenance. No performance-based filtering or clip selection was done.']
    (OUT/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Lightweight offline gallery; local videos remain linked for desktop players.
    items=[]
    for r in results:
        name=r['sequence'];items.append(f'<section><h2>{name}</h2><video controls preload="none" poster="{name}_preview.jpg" src="{Path(r["output_video"]).name}"></video><p><a href="{Path(r["output_video"]).name}">Open video</a> · {r["frames"]} frames · {r["source_fps"]:g} fps</p></section>')
    (OUT/'START_HERE.html').write_text('<!doctype html><meta charset="utf-8"><title>Current V5 + R9 test videos</title><style>body{font:17px system-ui;background:#15202b;color:#edf3f9;max-width:1100px;margin:32px auto;padding:16px}video{width:100%;max-height:620px;background:black}section{margin:36px 0}a{color:#80ceff}</style><h1>Current model: four previous test clips</h1><p>Magenta: predicted box and centre. No ground-truth labels; these are visual demonstrations, not accuracy measurements. Same retained V5 + R9, fixed-point CPU replay. Playback speed is native video speed, not FPGA speed.</p>'+''.join(items),encoding='utf-8')
    status('All four current-model videos saved',folder=str(OUT),training=False)

if __name__=='__main__':
    try:
        with lock():main()
    except BaseException as exc:
        save(OUT/'ERROR.json',{'error':str(exc),'traceback':traceback.format_exc(),'original_model_preserved':True});raise
