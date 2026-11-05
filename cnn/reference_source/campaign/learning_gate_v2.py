"""Check actual model backward parity and TRAIN-only memorization before a long job."""
import environment
import copy,json,random,time,traceback
import numpy as np,torch,torch_directml
from torch.utils.data import DataLoader
from model import make
from data_v2 import Data,collate,prepare,metrics,SEED
from state import ROOT,save,status,guard,lock
from utils.loss import ComputeLoss

def cpu_loss(net):
    loss=ComputeLoss(copy.deepcopy(net).cpu());loss.balance=[4.,1.];return loss

def forward_loss(net,loss,images,targets,device):
    raw=net(images.to(device));return loss([x.cpu() for x in raw],targets)

@torch.no_grad()
def predict(net,images,device):
    pred=net(images.to(device))[0].cpu();conf=pred[:,:,4]*pred[:,:,5];c,index=conf.max(1)
    b=pred[torch.arange(len(pred)),index,:4];return c.numpy(),b.numpy()

def main():
    if (ROOT/'LEARNING_GATE_V2_PASSED.json').exists():return
    torch.set_num_threads(4);torch.manual_seed(SEED);random.seed(SEED);np.random.seed(SEED)
    device=torch_directml.device(0);net,facts=make();net.eval();net.model[-1].train();gpu=copy.deepcopy(net).to(device);loss=cpu_loss(net)
    cases=[]
    for present in [True,False]:
        net.zero_grad(set_to_none=True);gpu.zero_grad(set_to_none=True);x=torch.rand(2,3,96,128)
        target=torch.tensor([[0,0,.4,.6,.12,.09],[1,0,.7,.3,.04,.05]]) if present else torch.empty(0,6)
        ca,_=forward_loss(net,loss,x,target,'cpu');ga,_=forward_loss(gpu,loss,x,target,device);ca.backward();ga.backward()
        errors=[];reference=[]
        for (name,a),(other,b) in zip(net.named_parameters(),gpu.named_parameters()):
            if a.grad is not None and b.grad is not None:errors.append(float((a.grad-b.grad.cpu()).abs().max()));reference.append(float(a.grad.abs().max()))
        absolute=max(errors);relative=absolute/max(1e-8,max(reference));cases.append({'positive_case':present,'cpu_loss':float(ca.detach()),'gpu_loss_cpu_calculated':float(ga.detach()),'max_weight_gradient_absolute_error':absolute,'error_relative_to_max_reference_gradient':relative})
        if relative>2e-3 or abs(float(ca.detach()-ga.detach()))>1e-3:raise RuntimeError('Real detector CPU/GPU backward parity failed')
    del net,gpu
    data=prepare();rows=[];seen=set()
    for r in data['train']:
        key=(r['source'],r['group'],r['view'])
        if key not in seen:rows.append(r);seen.add(key)
    rows=rows[:32];loader=DataLoader(Data(rows),batch_size=8,num_workers=0,collate_fn=collate);batches=list(loader)
    torch.manual_seed(SEED);net,facts=make();loss=cpu_loss(net);net=net.to(device);optimizer=torch.optim.AdamW(net.parameters(),lr=.001,weight_decay=.0001)
    history=[];start=time.time()
    for step in range(180):
        net.train();batch=batches[step%len(batches)];optimizer.zero_grad(set_to_none=True)
        total,parts=forward_loss(net,loss,batch[0],batch[1],device);total=total/len(batch[0]);total.backward();torch.nn.utils.clip_grad_norm_(net.parameters(),10);optimizer.step();history.append(float(total.detach()))
        if step%30==0:guard();status('Testing TRAIN-only learning',step=step,steps=180,loss=history[-1])
    net.eval();cs=[];bs=[];actual=[]
    for batch in batches:
        c,b=predict(net,batch[0],device);cs.extend(c);bs.extend(b);actual.extend(batch[2].numpy())
    values=[metrics(cs,bs,actual,rows,t) for t in np.arange(.01,.9,.02)];best=max(values,key=lambda x:x['f1'])
    result={'passed':np.mean(history[-20:])<.7*np.mean(history[:20]) and best['f1']>.5,'backward_parity':cases,'train_probe_views':len(rows),'first20_mean_loss':float(np.mean(history[:20])),'last20_mean_loss':float(np.mean(history[-20:])),'train_probe_best_f1':best['f1'],'seconds':time.time()-start,'model':facts,'scope':'Audited-source-data tiny TRAIN-only memorization, not validation accuracy. Probe weights discarded. Official YOLOv5 CIoU/objectness loss runs on CPU; network/backward run on DirectML with tested gradient agreement.'}
    save(ROOT/'learning_gate_v2_result.json',result)
    if not result['passed']:raise RuntimeError('Tiny TRAIN learning gate failed; inspect before production training')
    save(ROOT/'LEARNING_GATE_V2_PASSED.json',result);status('New detector backward and learning gates passed',probe_f1=best['f1'],parameters=facts['parameters'])
if __name__=='__main__':
    try:
        with lock():main()
    except Exception as e:save(ROOT/'LEARNING_GATE_V2_ERROR.json',{'error':str(e),'traceback':traceback.format_exc()});raise
