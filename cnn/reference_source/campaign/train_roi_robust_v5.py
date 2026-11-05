"""Bounded, recoverable ROI fine-tuning; selection on whole native VAL replay.
All original baselines, global model, source images and final holdouts preserved.
"""
import environment
import hashlib,json,math,random,sys,time,traceback
from pathlib import Path
import cv2,numpy as np,torch,torch_directml
from torch.utils.data import DataLoader,Subset
from model_p2_two_class import make
from data_roi_robust_v5 import Data,collate,sampling,sized,W,H
from roi_native_metrics_v5 import evaluate as evaluate_predeclared_native
from learning_gate_v2 import cpu_loss,forward_loss
from score_motion_application_baselines import metric
from data import metrics,iou
from state import ROOT,PROJECT,save,status,guard,lock
from utils.torch_utils import ModelEMA

TRIAL=ROOT/'trial05_roi_robust';SEED=20261019
CONFIG={'trial': '05_roi_native_softmix_contrast', 'input': [256, 192, 3], 'epochs': 8, 'draws_per_epoch': 6000, 'batch_size': 16, 'learning_rate': 0.0001, 'body_lr_scale': 0.25, 'weight_decay': 0.0001, 'seed': 20261019, 'minimum_epochs': 4, 'patience': 3, 'manifest': 'roi256_dataset/manifest_native_all_v3.json', 'native_validation': 'motion_validation_prepared/manifest.json', 'seed_checkpoint': 'trial03_p23_consistent_flying/epoch_05.pt', 'warmstart_checkpoint': 'trial04_roi256/epoch_11.pt', 'selection': 'PREDECLARED motion_agreement beforemax, original17193nativeGTframes atclock-only5Hz, causalconfirm1..3 andpast-onlyvelocity, max sourcebalancedF1 under5%trueempty triggers. Originalstrictallaircraft and rawsampleddiagnostic retained. No13/20inselection.', 'augmentation': 'OriginalTRAINgeometry/HSV/mirrorplus25%softMixUp(.6original+.4officialBeta32blendwithTRAINempty) OR25%contrast.65..90; no compoundedextra fading, targetwidth>=12/height>=8. Alloriginalframe/splitmembership retained, nativeDUT/UAVCBpixels.', 'early_stopping': 'Minimum4epochs,3without sourcebalancednativecausalF1improvement,8max.2epochs/process exactEMA/optimizer/RNG/orderrecovery.', 'caveats': 'Configurationtrial notisolatedcausalablation. FullnativeVAL only328trueemptyframes, rareaircraftexcludedONLYapplication. Actualprocessinglatencyzero, nohover/board/system claim. Learnedcoefficients/scales neednewfinalquantizedverification; oldROI11proofnotnewweightsproof.'}

def cpu(x):
    if isinstance(x,torch.Tensor):return x.detach().cpu().clone()
    if isinstance(x,dict):return {k:cpu(v) for k,v in x.items()}
    if isinstance(x,list):return [cpu(v) for v in x]
    if isinstance(x,tuple):return tuple(cpu(v) for v in x)
    return x

def checkpoint(path,data):
    temp=path.with_suffix('.tmp');torch.save(cpu(data),temp);temp.replace(path)

@torch.no_grad()
def predict(net,images,device):
    p=net(images.to(device))[0].cpu();c,j=p[:,:,4].max(1);return c.numpy(),p[torch.arange(len(p)),j,:4].numpy()

def read_patch(path):
    image=cv2.imread(path)
    if image is None:raise RuntimeError('Missing frozen native ROI validation patch')
    image,_,tr=sized(image,np.empty((0,4),np.float32));return torch.from_numpy(np.ascontiguousarray(image[:,:,::-1])).permute(2,0,1).float()/255,tr

def validation_plan():
    manifest=ROOT/CONFIG['native_validation'];d=json.loads(manifest.read_text());records=[];flat=[]
    for seq in d['sequences']:
        for r in seq['records']:
            row={'source':seq['source'],'sequence':seq['sequence'],'frame':r['frame'],'truth_native':r['truth_native'],'negative_kind':'other_flying_object' if seq['source']=='DroneDetectionThesis' and not seq['sequence'].startswith('V_DRONE_') else 'scene_empty','confidence':0.,'selected_iou':0.,'selected_box_native':[0.,0.,0.,0.]};records.append(row)
            for patch in r['crops']:flat.append((len(records)-1,patch))
    if len(records)!=5748 or len(flat)!=9471:raise RuntimeError('Native original replay membership changed')
    return records,flat

def evaluate_native(net,device,label):
    return evaluate_predeclared_native(net,device,label,TRIAL,CONFIG)

@torch.no_grad()
def static_diagnostic(net,rows,device):
    net.eval();cs=[];bs=[];actual=[];loader=DataLoader(Data(rows),batch_size=24,num_workers=0,collate_fn=collate)
    for n,b in enumerate(loader):
        c,box=predict(net,b[0],device);cs.extend(c);bs.extend(box);actual.extend(b[2].numpy())
        if n%100==0:guard();status('Retaining original full static validation diagnostic',batch=n,total=len(loader))
    cs=np.array(cs);bs=np.array(bs);actual=np.array(actual);eligible=np.array([r['group']!='hard_negative' for r in rows]);selected_rows=[r for r,yes in zip(rows,eligible) if yes]
    scan=[metrics(cs[eligible],bs[eligible],actual[eligible],selected_rows,t) for t in np.arange(.01,.996,.01)];valid=[r for r in scan if r['negative_trigger'] is not None and r['negative_trigger']<=.05];best=max(valid,key=lambda r:r['balanced_f1'])
    result={'original_rows':len(rows),'input':[W,H,3],'application_diagnostic':best,'strict_at_diagnostic_threshold':metrics(cs,bs,actual,rows,best['threshold']),'scope':'Original6319 static VAL rows at256input, not primary ROI model selection. Original Mendeley labels retained despite visual-quality concerns; this is not a clean architecture ablation against480globalmodel.'};save(TRIAL/'selected_static6319_diagnostic.json',result);return result

def main():
    for file in ['ROI_ROBUST_V5_DATA_AUDIT_R2.json','ROI_NATIVE_DUT_V2_PREPARED.json','ROI_NATIVE_UAVCB_V3_PREPARED.json','ROI_ROBUST_V5_GRADIENT_SMOKE.json']:
        if not json.loads((ROOT/file).read_text())['passed']:raise RuntimeError('Readiness gate failed:'+file)
    TRIAL.mkdir(exist_ok=True)
    if (TRIAL/'TRAINING_COMPLETE.json').exists():status('ROI trial complete; supervisor must advance');return
    guard();torch.set_num_threads(4);cv2.setNumThreads(1);torch.manual_seed(SEED);np.random.seed(SEED);random.seed(SEED)
    config=dict(CONFIG);config['manifest_sha256']=hashlib.sha256((ROOT/CONFIG['manifest']).read_bytes()).hexdigest();config['native_validation_sha256']=hashlib.sha256((ROOT/CONFIG['native_validation']).read_bytes()).hexdigest();config['code_sha256']=hashlib.sha256(b''.join((ROOT/f).read_bytes() for f in ['train_roi_robust_v5.py','data_roi_robust_v5.py','data_roi256.py','recalibrate_roi_bn_native.py','roi_native_metrics_v5.py','evaluate_roi_decoder_policies.py','calibrate_roi_temporal.py','model_p2_two_class.py','learning_gate_v2.py','score_motion_application_baselines.py'])).hexdigest();config_path=TRIAL/'config.json'
    if config_path.exists() and json.loads(config_path.read_text())!=config:raise RuntimeError('Frozen ROI trial source/config changed; use a new version')
    readiness=json.loads((ROOT/'ROI_ROBUST_V5_DATA_AUDIT_R2.json').read_text());curation=json.loads((ROOT/'ROI_NATIVE_UAVCB_V3_PREPARED.json').read_text())
    if readiness['manifest_sha256']!=config['manifest_sha256'] or curation['new_manifest_sha256']!=config['manifest_sha256']:raise RuntimeError('TRAIN readiness/curation manifest changed')
    save(config_path,config);data=json.loads((ROOT/config['manifest']).read_text());seed=torch.load(ROOT/config['seed_checkpoint'],map_location='cpu',weights_only=False);net,facts=make(anchors=seed['config']['anchors']);warm=torch.load(ROOT/config['warmstart_checkpoint'],map_location='cpu',weights_only=False);net.load_state_dict(warm['ema']);facts.update(seed_checkpoint=config['warmstart_checkpoint'],anchor_provenance_checkpoint=config['seed_checkpoint'],all_parameters_including_heads_loaded=True,input=[W,H,3],logical_macs_per_cnn_call=170606592,loss_hyperparameters=net.hyp,scope='Warmstarted ALL immutable ROIepoch11 learnedparameters/BN; originalglobalepoch5 suppliesanchorconfigONLY. Nativepixel/softmixcontrastfine-tune. No newheads/teacher or FPGA precision acceptance claim.')
    loss=cpu_loss(net);device=torch_directml.device(0);net=net.to(device);body=[];head=[]
    for name,p in net.named_parameters():(body if int(name.split('.')[1])<=10 else head).append(p)
    optimizer=torch.optim.AdamW([{'params':body,'lr_scale':config['body_lr_scale']},{'params':head,'lr_scale':1.}],lr=config['learning_rate'],weight_decay=config['weight_decay']);ema=ModelEMA(net);history=json.loads((TRIAL/'history.json').read_text()) if (TRIAL/'history.json').exists() else []
    best=max((r['validation']['selection']['balanced_f1'] for r in history),default=-1.);best_epoch=max(history,key=lambda r:r['validation']['selection']['balanced_f1'])['epoch'] if history else 0;epoch=1;position=0;indices=None;running=[];recovery=TRIAL/'recovery.pt'
    if recovery.exists():
        r=torch.load(recovery,map_location='cpu',weights_only=False);net.load_state_dict(r['model']);ema.ema.load_state_dict(r['ema']);ema.updates=r['ema_updates'];optimizer.load_state_dict(r['optimizer']);epoch=r['epoch'];position=r['position'];indices=r['indices'];running=r['running'];random.setstate(r['random']);np.random.set_state(r['numpy']);torch.set_rng_state(r['torch_rng']);status('Resuming saved ROI optimizer/order/RNG state',epoch=epoch,sample=position)
    def state(ep,pos,ids):return {'model':net.state_dict(),'ema':ema.ema.state_dict(),'ema_updates':ema.updates,'optimizer':optimizer.state_dict(),'epoch':ep,'position':pos,'indices':ids,'running':running,'random':random.getstate(),'numpy':np.random.get_state(),'torch_rng':torch.get_rng_state(),'config':config,'facts':facts}
    if not history and not recovery.exists():
        initial=evaluate_native(ema.ema,device,'initial_native_val')
        if abs(initial['selection']['balanced_f1']-.7354512307435184)>.002:raise RuntimeError('Immutable ROI11 native golden replay differs; inspect before any V5gradient training')
    weights=sampling(data['train']);dataset=Data(data['train'],augment=True)
    for ep in range(epoch,config['epochs']+1):
        if ep!=epoch:position=0;indices=None;running=[]
        if indices is None:indices=torch.multinomial(weights,config['draws_per_epoch'],replacement=True).tolist()
        loader=DataLoader(Subset(dataset,indices[position:]),batch_size=config['batch_size'],num_workers=0,collate_fn=collate);start=time.time();net.train();status('Training V5 native-detail robustness candidate',epoch=ep,total_epochs=config['epochs'],sample=position,total_samples=len(indices),device=torch_directml.device_name(0).rstrip('\x00'),parameters=facts['parameters'])
        for b in loader:
            step=(ep-1)*math.ceil(len(indices)/config['batch_size'])+position//config['batch_size'];progress=(ep-1+position/len(indices))/config['epochs'];lr=config['learning_rate']*(.15+.85*.5*(1+math.cos(math.pi*progress)))*min(1.,(step+1)/50)
            for group in optimizer.param_groups:group['lr']=lr*group['lr_scale']
            optimizer.zero_grad(set_to_none=True);total,_=forward_loss(net,loss,b[0],b[1],device);total=total/len(b[0])
            if not torch.isfinite(total):raise RuntimeError('Nonfinite ROI loss; recovery retained')
            total.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),10);optimizer.step();ema.update(net);position+=len(b[0]);running.append(float(total.detach()));batch=position//config['batch_size']
            if batch%50==0:guard();status('V5 robustness training progress',epoch=ep,samples=position,total_samples=len(indices),mean_recent_loss=float(np.mean(running[-50:])),learning_rate=lr)
            if batch%100==0:checkpoint(recovery,state(ep,position,indices))
        checkpoint(recovery,state(ep,position,indices));validation=evaluate_native(ema.ema,device,f'epoch_{ep:02d}_native_val');row={'epoch':ep,'seconds':time.time()-start,'mean_loss':float(np.mean(running)),'validation':validation};history=[r for r in history if r['epoch']!=ep]+[row];save(TRIAL/'history.json',history);checkpoint(TRIAL/f'epoch_{ep:02d}.pt',state(ep+1,0,None))
        if validation['selection']['balanced_f1']>best:best=validation['selection']['balanced_f1'];best_epoch=ep;checkpoint(TRIAL/'best.pt',state(ep+1,0,None))
        running=[];checkpoint(recovery,state(ep+1,0,None));status('V5 robustness epoch evaluated',epoch=ep,best_epoch=best_epoch,**validation['selection'])
        if ep>=config['minimum_epochs'] and ep-best_epoch>=config['patience']:status('ROI validation plateau; retaining best',best_epoch=best_epoch);break
        if ep-epoch+1>=2 and ep<config['epochs']:status('Releasing ROI GPU process at saved epoch boundary',next_epoch=ep+1);sys.exit(75)
    del net,optimizer,ema;snap=torch.load(TRIAL/'best.pt',map_location='cpu',weights_only=False);selected,_=make(anchors=seed['config']['anchors']);selected.load_state_dict(snap['ema']);selected=selected.to(device).eval();full=evaluate_native(selected,device,'selected_native_validation');static=static_diagnostic(selected,data['val'],device)
    result={'trained':True,'best_epoch':best_epoch,'epochs_completed':history[-1]['epoch'],'native_validation':full,'static_diagnostic':static,'checkpoint':str(TRIAL/'best.pt'),'software_gate_passed':False,'hardware_gate_passed':False,'full_development_videos_pending':True,'scope':'Bounded V5trainingended, NOT campaignacceptance. Supervisor must FREEZE selectedpolicy/threshold/confirmation, run complete13/20/external/hover checks, then verifyactualNEWcoeffquantized/hardware. Originalmodels/splits preserved.'};save(TRIAL/'TRAINING_COMPLETE.json',result);status('V5 bounded robustness training complete; evaluation pipeline must advance',best_epoch=best_epoch,balanced_f1=full['selection']['balanced_f1'])

if __name__=='__main__':
    try:
        with lock():main()
    except Exception as exc:save(TRIAL/'ERROR.json',{'error':str(exc),'traceback':traceback.format_exc()});status('ROI256 trial needs evidence-based inspection',error=str(exc));raise
