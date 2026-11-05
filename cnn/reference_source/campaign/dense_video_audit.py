"""Score saved predictions against COMPLETE author annotations, without inference or tuning."""
import json,re
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'genesys2_roi_redesign_v2'
def iou(a,b):
    lo=np.maximum(a[:2]-a[2:]/2,b[:2]-b[2:]/2);hi=np.minimum(a[:2]+a[2:]/2,b[:2]+b[2:]/2)
    overlap=np.maximum(0,hi-lo).prod();return float(overlap/max(1e-8,np.prod(a[2:])+np.prod(b[2:])-overlap))
def truth(seq):
    lines=(ROOT/'official_annotations'/f'{seq}_gt.txt').read_text().splitlines();result=[]
    for line in lines:
        a=np.array([float(x) for x in re.split(r'[,\s]+',line.strip()) if x][:4])
        if len(a)!=4:raise RuntimeError('Bad official annotation')
        result.append(np.r_[a[:2]+a[2:]/2,a[2:]] if min(a[2:])>0 else np.zeros(4))
    return result
def main():
    out={}
    for seq in ['video13','video20']:
        actual=truth(seq);runs={};agreement=[]
        frames=sorted((ROOT.parent/'training_datasets/dut_anti_uav'/seq).glob('*.jpg'))
        if len(frames)!=len(actual):raise RuntimeError('Image/annotation count mismatch')
        for path in sorted((OLD/'videos').glob(f'{seq}_*_predictions.json')):
            pred=json.loads(path.read_text());good=[];center=[];active=[];neg=[]
            if len(pred)!=len(actual):raise RuntimeError('Prediction length mismatch')
            for r,b in zip(pred,actual):
                a=np.array(r['box_native']);visible=b[2]>0;det=a[2]>0
                if visible:
                    good.append(det and iou(a,b)>=.5);active.append(det)
                    if det:center.append(float(np.linalg.norm(a[:2]-b[:2])))
                else:neg.append(det)
                if r['label_available'] and 'seed_global' in path.name and visible and r['actual_native'][2]>0:agreement.append(iou(np.array(r['actual_native']),b))
            runs[path.name.replace('_predictions.json','')]={'frames':len(pred),'positive_frames':len(good),'negative_frames':len(neg),'correct_box_recall_complete_gt':float(np.mean(good)) if good else None,'positive_prediction_coverage':float(np.mean(active)) if active else None,'negative_trigger_rate':float(np.mean(neg)) if neg else None,'median_center_error_on_triggered_positive_native_pixels':float(np.median(center)) if center else None}
        out[seq]={'annotation_frame_count':len(actual),'prior_sparse_label_agreement_iou_median':float(np.median(agreement)) if agreement else None,'prior_sparse_label_agreement_iou_min':float(np.min(agreement)) if agreement else None,'runs':runs}
    (ROOT/'complete_video_baselines.json').write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
