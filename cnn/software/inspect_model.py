"""Load both retained checkpoints and run a lightweight head-shape/numeric check."""
import environment
import argparse,json
from pathlib import Path
import numpy as np,torch
from runtime import ROOT,load,read
from model_p2_two_class import make,HardwareGraph
def main():
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);a=p.parse_args()
    out=Path(a.report)
    if out.exists():raise RuntimeError('Use a new report path')
    fixed,preferred=load()
    snapshot=torch.load(ROOT/'weights/epoch_08.pt',map_location='cpu',weights_only=False)
    aq=np.asarray(read(ROOT/'config/DECODER_PREPARED.json')['anchor_q16'],np.float64)
    anchors=(aq/65536).reshape(2,6).tolist()
    net,_=make(anchors=anchors);net.load_state_dict(snapshot['ema'],strict=True);net.eval()
    params=sum(p.numel() for p in net.parameters())
    if params!=331114:raise RuntimeError('Unexpected architecture')
    torch.manual_seed(7);sample=torch.rand(1,3,192,256)
    with torch.no_grad():
        original=HardwareGraph(net)(sample);heads=fixed(sample)
    shapes=[list(x.shape) for x in heads]
    if shapes!=[[1,21,48,64],[1,21,24,32]]:raise RuntimeError('Head shape mismatch')
    if not all(torch.isfinite(x).all() for x in heads):raise RuntimeError('Nonfinite output')
    report={'passed':True,'parameters':params,'completed_epoch':8,'next_epoch_recovery_counter':snapshot['epoch'],'input_bchw':[1,3,192,256],
        'head_shapes_bchw':shapes,'ema_strict_load':True,'clipped_values':fixed.clips,
        'random_probe_float_vs_fixed_max_abs':[float((x.double()-y).abs().max()) for x,y in zip(original,heads)],
        'checkpoint_sha256':preferred['checkpoint_sha256'],'quantized_model_sha256':preferred['quantized_model_sha256'],
        'torch':torch.__version__,'scope':'Loading/shape/random-input smoke check, not an accuracy evaluation.'}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2))
    (out.parent/'retained_architecture.yaml').write_text(__import__('yaml').safe_dump(net.yaml,sort_keys=False))
    (out.parent/'retained_layers.txt').write_text(str(net))
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
