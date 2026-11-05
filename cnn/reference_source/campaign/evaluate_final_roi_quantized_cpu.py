"""ALL original native VAL crops, exact fixed-point reference, frozen controller.
One CPU thread; yields a saved resumable cursor if RAM falls below2GiB.
No confidence/controller retuning after quantization.
"""
import environment
import copy,ctypes,hashlib,json,time
from pathlib import Path
import cv2,numpy as np,torch
from model_p2_two_class import make,HardwareGraph
from data_roi256 import sized
from evaluate_roi_decoder_policies import choose
from calibrate_roi_temporal import prepare,apply
from score_motion_application_baselines import metric
from data import iou
from state import ROOT,Memory,save

BUILD=Path.home()/'fpga_builds/g2_roi_epoch11_wide_r2_live'
OUT=ROOT/'roi_epoch11_final_quantized_native_val_r1'

def enough():
    m=Memory();m.length=ctypes.sizeof(m);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m));return m.available>=2*2**30

class Fixed(torch.fx.Interpreter):
    def __init__(self,model):super().__init__(model);self.clipped=0
    def run_node(self,node):
        y=super().run_node(node)
        if isinstance(y,torch.Tensor):
            self.clipped+=int(((y < -512)|(y >8388607/16384)).sum());return torch.round(y*16384).clamp(-8388608,8388607)/16384
        return y

def decode(heads,anchors,strides):
    result=[]
    for level,head in enumerate(heads):
        b,c,h,w=head.shape;y=head.view(b,3,7,h,w).permute(0,1,3,4,2).contiguous().sigmoid();yy,xx=torch.meshgrid(torch.arange(h,dtype=y.dtype),torch.arange(w,dtype=y.dtype),indexing='ij');grid=torch.stack((xx,yy),2).view(1,1,h,w,2);xy=(y[...,:2]*2-.5+grid)*strides[level];wh=(y[...,2:4]*2)**2*(anchors[level]*strides[level]).view(1,3,1,1,2);result.append(torch.cat((xy,wh,y[...,4:]),4).view(b,-1,7))
    return torch.cat(result,1)

def main():
    torch.set_num_threads(1);cv2.setNumThreads(1)
    if not enough():raise RuntimeError('CPU quality reserve unavailable; hardware untouched')
    if (OUT/'COMPLETE.json').exists():raise RuntimeError('Existing quantized quality result preserved')
    selection_path=ROOT/'ROI256_FROZEN_TEMPORAL_SELECTION_R1.json';selection=json.loads(selection_path.read_text());policy=selection['policy'];threshold=selection['selected']['threshold'];count=selection['selected']['confirmations'];meta=json.loads((BUILD/'QUANTIZED_MODEL_METADATA.json').read_text());checkpoint=Path(meta['checkpoint'])
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=meta['checkpoint_sha256'] or selection['epoch']!=11:raise RuntimeError('Final checkpoint/selection changed')
    net=torch.load(BUILD/'quantized_fx.pt',map_location='cpu',weights_only=False).double().eval();snap=torch.load(checkpoint,map_location='cpu',weights_only=False);seed=torch.load(ROOT/snap['config']['seed_checkpoint'],map_location='cpu',weights_only=False);original,_=make(anchors=seed['config']['anchors']);original.load_state_dict(snap['ema']);original.eval();anchors=original.model[-1].anchors.detach().double();strides=original.stride.double()
    # Compare our hardware-head decoding with actual original vendor decoding.
    with torch.no_grad():
        sample=torch.rand(1,3,192,256);actual=original(sample)[0];reference=decode(HardwareGraph(original)(sample),anchors.float(),strides.float());decoder_error=float((actual-reference).abs().max())
    if decoder_error>.001:raise RuntimeError('Raw-head decoder differs from original vendor decoder')
    del original,snap,seed,actual,reference,sample
    manifest_path=ROOT/'motion_validation_prepared/manifest.json';manifest=json.loads(manifest_path.read_text());rows=[];flat=[]
    for seq in manifest['sequences']:
        for r in seq['records']:
            rows.append({'source':seq['source'],'sequence':seq['sequence'],'frame':r['frame'],'truth_native':r['truth_native'],'negative_kind':'other_flying_object' if seq['source']=='DroneDetectionThesis' and not seq['sequence'].startswith('V_DRONE_') else 'scene_empty','confidence':0.,'selected_box_native':[0.,0.,0.,0.],'selected_iou':0.})
            for patch in r['crops']:flat.append((len(rows)-1,patch,r['native_size'][0]))
    config={'quantized_model_sha256':hashlib.sha256((BUILD/'quantized_fx.pt').read_bytes()).hexdigest(),'checkpoint_sha256':meta['checkpoint_sha256'],'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),'selection_sha256':hashlib.sha256(selection_path.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'decoder_max_abs_error_vs_vendor':decoder_error,'policy':policy,'threshold':threshold,'confirmations':count,'format':'A24F14/W16perlayer/B24F14/48bit exact sum; FXfloat64exactintegerbound reference with ties-even rounding/saturation EVERYtensor node. Sigmoid/boxdecode floating point here; its final hardware/LUT approximation NOT yet included.','scope':'All9471 original nativeVAL crops. Frozen threshold/controller, NO recalibration/GTstate. CPUonly, no boardFPS/RTL accuracy claim.'}
    # The decoder parity probe uses random data; exclude its last-bit value from
    # the resume fingerprint, while keeping the measured result in metadata.
    fingerprint={k:v for k,v in config.items() if k!='decoder_max_abs_error_vs_vendor'}
    OUT.mkdir(exist_ok=True);start=0;clipped=0
    if (OUT/'FROZEN_CONFIG.json').exists():
        previous=json.loads((OUT/'FROZEN_CONFIG.json').read_text());previous.pop('decoder_max_abs_error_vs_vendor',None)
        if previous!=fingerprint:raise RuntimeError('Cannot resume a changed quality study')
        if (OUT/'recovery.json').exists():
            recovery=json.loads((OUT/'recovery.json').read_text());rows=recovery['records'];start=recovery['completed_patches'];clipped=recovery['clipped_node_values']
    else:save(OUT/'FROZEN_CONFIG.json',config)
    beginning=time.time();interpreter=Fixed(net)
    def checkpoint(cursor):save(OUT/'recovery.json',{'completed_patches':cursor,'total_patches':len(flat),'records':rows,'clipped_node_values':clipped})
    with torch.no_grad():
        for begin in range(start,len(flat),4):
            if not enough():checkpoint(begin);save(OUT/'progress.json',{'status':'memory_reserve_yield','completed_patches':begin,'total_patches':len(flat)});print('Saved CPU quality cursor at2GiB reserve; hardware job untouched',flush=True);return
            batch=flat[begin:begin+4];inputs=[];transforms=[];us=[];vs=[];mx=[];my=[]
            for _,patch,native_w in batch:
                image=cv2.imread(patch['image_path'])
                if image is None:raise RuntimeError('Missing original native quality crop')
                canvas,_,tr=sized(image,np.empty((0,4),np.float32));inputs.append(torch.from_numpy(np.ascontiguousarray(canvas[:,:,::-1])).permute(2,0,1).double()/255);transforms.append(tr);sx,sy,px,py=tr;l,t,_,_=patch['native_rectangle'];x,y,_=patch['proposal_640'];scale=640/native_w;us.append((x/scale-l)*sx+px);vs.append((y/scale-t)*sy+py);mx.append(8*sx/scale);my.append(8*sy/scale)
            interpreter.clipped=0;heads=interpreter.run(torch.stack(inputs));clipped+=interpreter.clipped;pred=decode(heads,anchors,strides);cs,bs=choose(pred,torch.tensor(us),torch.tensor(vs),torch.tensor(mx),torch.tensor(my))[policy]
            for (index,patch,_),c,b,tr in zip(batch,cs,bs,transforms):
                sx,sy,px,py=tr;l,t,_,_=patch['native_rectangle'];native=np.array([(b[0]-px)/sx+l,(b[1]-py)/sy+t,b[2]/sx,b[3]/sy]);row=rows[index]
                if c>row['confidence']:row.update(confidence=float(c),selected_box_native=native.tolist(),selected_iou=max((float(iou(native,np.array(gt))) for gt in row['truth_native']),default=0.))
            if begin%128==0:
                cursor=begin+len(batch);checkpoint(cursor);save(OUT/'progress.json',{'status':'running','completed_patches':cursor,'total_patches':len(flat),'seconds_this_process':round(time.time()-beginning,1),'clipped_node_values':clipped});print(f'Exact fixed-point native quality {cursor}/{len(flat)}',flush=True)
    checkpoint(len(flat));save(OUT/'records.json',rows);series,full=prepare(rows,manifest);apply(series,full,threshold,count,True);eligible=[r for r in full if r['truth_native'] or r['negative_kind']!='other_flying_object'];quality=metric(eligible,threshold);baseline=selection['selected'];difference=quality['balanced_f1']-baseline['balanced_f1'];strict=metric(full,threshold);save(OUT/'COMPLETE.json',{'quantized_frozen_controller':quality,'floating_frozen_controller':baseline,'balanced_f1_change':difference,'within_three_percentage_point_loss':bool(difference>=-.03),'clipped_node_values_including_repeated_tensor_nodes':clipped,'native_frames':len(full),'all_original_native_strict':strict,'seconds_last_process':round(time.time()-beginning,1),'scope':'Whole original native validation, same frozenfloat selection/controller, exact fixed-point arithmetic reference. NO retuning. Softwaredecoder sigmoids/boxes floating-point; future HLSdecoder approximation, RTLtrainedframe and completecamera/MIG/routedfit still required. No unseen/field/board acceptance.'});print(json.dumps({'balanced_f1_change':difference,'fixed':quality,'clipped':clipped}),flush=True)

if __name__=='__main__':main()
