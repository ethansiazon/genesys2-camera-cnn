"""Fresh full17193-frame native replay: actual fixed core AND integer decoder.

No labels in acquisition/search/ROI/decoder/association; labels score only after
predictions. Existing frozen R3 controller and assumed latency, no retuning.
"""
import environment
import hashlib,json,time
from pathlib import Path
import cv2,numpy as np,torch
from state import ROOT,save,status,guard,lock
from model_p2_two_class import make
from evaluate_final_roi_quantized_cpu import Fixed
from track_feedback_r1 import Config
from score_motion_application_baselines import metric
from observations_integer_r2 import observations

BUILD=Path.home()/'fpga_builds/g2_roi_v5_epoch08_output32_r2'
DECODER=Path.home()/'fpga_builds/g2_v5_decoder_work_r2'
OUT=ROOT/'v5_integer_decoder_native_r2'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class IntegerNet:
    def __init__(self,net,anchors_q16,strides):
        self.reference=Fixed(net);self.anchors_q16=anchors_q16;self.strides_integer=strides
        self.clips=0;self.calls=0;self.sequence=''

    def __call__(self,images):
        self.reference.clipped=0;heads=self.reference.run(images.double());self.clips+=self.reference.clipped;self.calls+=len(images)
        if self.calls//100!=(self.calls-len(images))//100:status('Checking actual integer box/centre decoder on native videos',sequence=self.sequence,cnn_calls=self.calls,clipped_values=self.clips)
        return heads


def main():
    guard();torch.set_num_threads(2);cv2.setNumThreads(1)
    if (OUT/'COMPLETE.json').exists():raise RuntimeError('Existing integer decoder native study preserved')
    host=json.loads((DECODER/'HOST_CHECK.json').read_text())
    if not host['passed']:raise RuntimeError('Actual C++ integer decoder host gate required')
    for name,digest in host['source_sha256'].items():
        if sha(DECODER/name)!=digest:raise RuntimeError('Host-proven decoder source changed')
    prior=ROOT/'v5_fixed_feedback_native_r1';baseline=json.loads((prior/'COMPLETE.json').read_text());frozen_parent=json.loads((prior/'FROZEN_CONFIG.json').read_text())
    meta=json.loads((BUILD/'QUANTIZED_MODEL_METADATA.json').read_text());checkpoint=Path(meta['checkpoint'])
    if sha(checkpoint)!=frozen_parent['checkpoint_sha256']:raise RuntimeError('Wrong actual trained V5 checkpoint')
    source=(prior/'frozen_sequential_cpu.py').read_text();OUT.mkdir(exist_ok=True);derived=OUT/'frozen_sequential_cpu.py'
    if derived.exists() and derived.read_text()!=source:raise RuntimeError('Original sequential replay source changed')
    if not derived.exists():derived.write_text(source)
    namespace={'__name__':'integer_decoder_native','__file__':str(derived)};exec(compile(source,str(derived),'exec'),namespace);namespace['observations']=observations
    manifest_path=ROOT/'motion_validation_prepared/manifest.json';manifest=json.loads(manifest_path.read_text());config=Config(**frozen_parent['controller'])
    if len(manifest['sequences'])!=46 or sum(len(s['native_truth']) for s in manifest['sequences'])!=17193:raise RuntimeError('Native original membership changed')
    decoder_meta=json.loads((DECODER/'PREPARED.json').read_text());aq=np.array(decoder_meta['anchor_q16'],np.int64)
    frozen={'checkpoint_sha256':sha(checkpoint),'quantized_model_sha256':sha(BUILD/'quantized_fx.pt'),'native_manifest_sha256':sha(manifest_path),'float_decoder_baseline_sha256':sha(prior/'COMPLETE.json'),'decoder_host_gate_sha256':sha(DECODER/'HOST_CHECK.json'),'source_sha256':{p.name:sha(p) for p in [Path(__file__),ROOT/'observations_integer_r2.py',ROOT/'decoder_work_r2.py',ROOT/'track_feedback_r1.py',ROOT/'data_roi256.py',derived]},'controller':frozen_parent['controller'],'latency':.09,'updated_hz':10,'max_calls_per_update':2,'anchors_q16':aq.tolist(),'scope':'Actual trainedV5fixedcore plus integerLUTsigmoid/boxsize/Q16coordinateconversion/motion+associationgatesbeforeRAWlogitranking. SamefrozenR3controller. Causal ROI feedback recomputed from fresh nativepixels. CPU imagepreprocessing and tracker velocity/timing stillFLOAT; no hardware/system/boardFPS/field acceptance.'}
    frozen_path=OUT/'FROZEN_CONFIG.json'
    if frozen_path.exists():
        if json.loads(frozen_path.read_text())!=frozen:raise RuntimeError('Cannot resume changed integer study')
    else:save(frozen_path,frozen)
    net=IntegerNet(torch.load(BUILD/'quantized_fx.pt',map_location='cpu',weights_only=False).double().eval(),aq,[4,8]);allrows=[];sequences=[];oldclips=0;start=time.time()
    with torch.no_grad():
        for seq in manifest['sequences']:
            name=seq['sequence'];net.sequence=name;done=OUT/(name+'_DONE.json')
            if done.exists():
                saved=json.loads(done.read_text());paths={k:OUT/v for k,v in saved['files'].items()}
                if any(sha(p)!=saved['sha256'][k] for k,p in paths.items()):raise RuntimeError('Completed sequence payload changed')
                rows=json.loads(paths['records'].read_text());result=saved['result'];oldclips+=saved['clipped_values']
            else:
                guard();before=net.clips;rows,result=namespace['evaluate_sequence'](seq,net,torch.device('cpu'),.09,config,OUT)
                paths={k:OUT/(name+'_'+k+'.json') for k in ['records','updates','events']};save(done,{'result':result,'files':{k:p.name for k,p in paths.items()},'sha256':{k:sha(p) for k,p in paths.items()},'clipped_values':net.clips-before})
            if len(rows)!=len(seq['native_truth']):raise RuntimeError('Incomplete native sequence')
            allrows.extend(rows);sequences.append(result);save(OUT/'progress.json',{'completed_recordings':len(sequences),'total_recordings':46,'sequence':name,'cnn_calls_this_process':net.calls,'seconds':round(time.time()-start,1)})
            status('Integer decoder native recording complete',sequence=name,completed_recordings=len(sequences),total_recordings=46)
    eligible=[r for r in allrows if r['truth_native'] or r['negative_kind']!='other_flying_object'];quality=metric(eligible,.5);change=quality['balanced_f1']-baseline['application']['balanced_f1']
    save(OUT/'COMPLETE.json',{'complete':True,'native_frames':len(allrows),'application':quality,'same_core_float_decoder_baseline':baseline['application'],'balanced_f1_change':change,'within_three_percentage_point_loss':bool(change>=-.03),'author_negative_gate_passed':bool(quality['scene_empty_trigger']<=.05),'clipped_values':net.clips+oldclips,'strict_all_frames':metric(allrows,.5),'sequences':sequences,'seconds_this_process':round(time.time()-start,1),'scope':frozen['scope']})
    status('Trained integer decoder native quality complete',balanced_f1=quality['balanced_f1'],change=change,author_negative_trigger=quality['scene_empty_trigger'],clipped_values=net.clips+oldclips,hardware_proven=False)


if __name__=='__main__':
    with lock():main()
