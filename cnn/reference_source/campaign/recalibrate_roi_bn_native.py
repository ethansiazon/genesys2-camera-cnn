"""TRAIN-only normalization diagnostic, NO gradient/parameter optimization.
New native DUT pixels, deployment crop geometry without HSV/blur distortion.
Official torch.optim.swa_utils.update_bn; immutable original retained.
"""
import environment
import collections,hashlib,json,random,time
import cv2,numpy as np,torch,torch_directml
from torch.optim.swa_utils import update_bn
from model_p2_two_class import make
from data_roi256 import read_native,augment_crop,sized
from state import ROOT,save,status,guard,lock
OUT=ROOT/'roi_bn_native_r1'

def sampling(rows):
    gm={'drone':.60,'empty':.25,'hard_negative':.15};groups=collections.defaultdict(lambda:collections.defaultdict(lambda:collections.defaultdict(lambda:collections.defaultdict(list))))
    for i,r in enumerate(rows):groups[r['group']][r['source']][r['sequence']][r['view']].append(i)
    weights=np.zeros(len(rows))
    for group,sources in groups.items():
        for source,sequences in sources.items():
            vm={'full':.40,'motion_fixed':.45,'motion_adaptive':.15} if source=='DUT_Anti_UAV' else {'full':.15,'roi':.25,'motion_fixed':.45,'motion_adaptive':.15}
            for _,views in sequences.items():
                denom=sum(vm[v] for v in views)
                for view,ids in views.items():weights[ids]=gm[group]/len(sources)/len(sequences)*vm[view]/denom/len(ids)
    return torch.tensor(weights/weights.sum(),dtype=torch.double)

class GeometryData(torch.utils.data.Dataset):
    def __init__(self,rows):self.rows=rows
    def __len__(self):return len(self.rows)
    def __getitem__(self,index):
        row=self.rows[index]
        if row['split']!='train':raise RuntimeError('BN calibration cannot see VAL/test')
        image,boxes,classes=read_native(row)
        if random.random()<.8:image,boxes,classes=augment_crop(image,boxes,classes)
        canvas,_,_=sized(image,boxes);return torch.from_numpy(np.ascontiguousarray(canvas[:,:,::-1])).permute(2,0,1).float()/255

def parameter_sha(net):
    h=hashlib.sha256()
    for name,p in net.named_parameters():h.update(name.encode());h.update(p.detach().cpu().numpy().tobytes())
    return h.hexdigest()

def main():
    if OUT.exists():raise RuntimeError('Existing normalization diagnostic preserved')
    report=json.loads((ROOT/'ROI_NATIVE_DUT_V2_PREPARED.json').read_text())
    if not report['passed']:raise RuntimeError('New TRAINnative/split audit required')
    manifest=ROOT/'roi256_dataset/manifest_native_dut_v2.json';raw=manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=report['new_manifest_sha256']:raise RuntimeError('TRAIN native manifest changed')
    rows=json.loads(raw)['train'];checkpoint=ROOT/'trial04_roi256/epoch_11.pt';snapshot=torch.load(checkpoint,map_location='cpu',weights_only=False);seed=torch.load(ROOT/snapshot['config']['seed_checkpoint'],map_location='cpu',weights_only=False);net,_=make(anchors=seed['config']['anchors']);net.load_state_dict(snapshot['ema']);net.eval();before=parameter_sha(net);torch.set_num_threads(3);cv2.setNumThreads(1);random.seed(20261018);np.random.seed(20261018);torch.manual_seed(20261018);ids=torch.multinomial(sampling(rows),2048,replacement=True,generator=torch.Generator().manual_seed(20261018)).tolist();chosen=[rows[i] for i in ids];loader=torch.utils.data.DataLoader(GeometryData(chosen),batch_size=32,shuffle=False,num_workers=0);OUT.mkdir();save(OUT/'FROZEN_TRAIN_PLAN.json',{'checkpoint':str(checkpoint),'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),'manifest_sha256':report['new_manifest_sha256'],'seed':20261018,'samples':2048,'batch_size':32,'sample_indices':ids,'source_counts':dict(collections.Counter(r['source'] for r in chosen)),'augmentation':'TRAIN object-guided 80% crop geometry only, no HSV/blur/mirror. This is normalization CALIBRATION, not runtime label-informed crops.','method':'Official torch.optim.swa_utils.update_bn cumulative TRAIN-only mean/variance, all learned parameters fixed, NO optimizer/backward.','scope':'Diagnostic configuration, no accuracy/FPGA claim. Same TRAINmembership, original6319VAL/holdouts untouched.'})
    device=torch_directml.device(0);net.to(device);start=time.time();seen=0
    def guarded():
        nonlocal seen
        for batch in loader:
            guard();seen+=len(batch)
            if seen%256==0:status('Recalibrating normalization using TRAIN native images only',samples=seen,total=2048)
            yield batch
    update_bn(guarded(),net,device=device);net.eval();after=parameter_sha(net)
    if before!=after:raise RuntimeError('Learned parameter changed during BN-only diagnostic')
    target=OUT/'checkpoint.pt';torch.save({'ema':net.cpu().state_dict(),'config':snapshot['config'],'facts':snapshot['facts'],'bn_calibration':{'method':'Official update_bn TRAIN2048geometryonly','manifest':str(manifest),'parameter_sha256_before_and_after':before,'seed':20261018}},target);save(OUT/'COMPLETE.json',{'checkpoint':str(target),'checkpoint_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'learned_parameters_identical':True,'seconds':round(time.time()-start,1),'scope':'TRAIN-only BN runningstatistics changed, NO weighttraining. Requires identical fullnativeVAL/13/20/external tests before adoption.'});status('TRAIN-only normalization diagnostic prepared',learned_parameters_unchanged=True,validation_pending=True)

if __name__=='__main__':
    with lock():main()
