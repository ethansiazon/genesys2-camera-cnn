"""Portable adapter around the retained fixed CNN and unchanged R9 logic."""
import environment
import hashlib,json
from pathlib import Path
import numpy as np,torch,psutil
from fixed_reference import Fixed
ROOT=Path(__file__).resolve().parents[1]
def guard():
    if psutil.virtual_memory().available<1.5*2**30:
        raise RuntimeError('Stopped below 1.5 GiB free RAM; close this run and preserve outputs')
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
class IntegerNet:
    def __init__(self,net,anchors_q16,strides):
        self.reference=Fixed(net);self.anchors_q16=anchors_q16;self.strides_integer=strides
        self.clips=0;self.calls=0
    def __call__(self,images):
        self.reference.clipped=0
        heads=self.reference.run(images.double())
        self.clips+=self.reference.clipped;self.calls+=len(images)
        return heads
def load():
    guard();torch.set_num_threads(2)
    preferred=read(ROOT/'config/PREFERRED_INFERENCE_R9.json')
    for file,key in [('epoch_08.pt','checkpoint_sha256'),('quantized_fx.pt','quantized_model_sha256')]:
        if sha(ROOT/'weights'/file)!=preferred[key]:raise RuntimeError('Checkpoint changed: '+file)
    # Only load the trusted files shipped with this package; .pt uses pickle.
    net=torch.load(ROOT/'weights/quantized_fx.pt',map_location='cpu',weights_only=False).double().eval()
    anchors=np.asarray(read(ROOT/'config/DECODER_PREPARED.json')['anchor_q16'],np.int64)
    return IntegerNet(net,anchors,[4,8]),preferred
