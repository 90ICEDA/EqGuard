"""Evaluation only: strict existing checkpoints, no optimizer/backward/SAT."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
for k in list(os.environ):
 if k.startswith('P2B_'):del os.environ[k]
os.environ['P2B_MASK']='old'
import sys,json,hashlib,gc,datetime,importlib.util
from pathlib import Path
import numpy as np
import torch
from torch.nn import Linear,Sequential,BatchNorm1d,ReLU
from torch_geometric.nn import GINConv
import torch.nn.functional as fn
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;H=R/'_p0pilot/p2b_main_20261031'
sys.path.insert(0,str(R));from models.gin_net import GINDual
spec=importlib.util.spec_from_file_location('frozen_eval_loader',H/'train_ab.py');T=importlib.util.module_from_spec(spec);spec.loader.exec_module(T)
assert T.MASK_MODE=='old' and not T.EXTRA and T.EQ==0
class Model(GINDual):
 def __init__(self):
  super().__init__(39,64,2,num_layers=2,split=29,fusion='concat')
  self.mix=Linear(39,39)
  self.post=GINConv(Sequential(Linear(64,64),BatchNorm1d(64),ReLU(),Linear(64,64)))
 def forward(self,x,e):
  x=x+fn.relu(self.mix(x));a=self._run(self.enc_s,x[:,:self.split],e);b=self._run(self.enc_f,x[:,self.split:],e)
  h=self.fuse(torch.cat((a,b),1));h=fn.dropout(fn.relu(self.post(h,e)),p=.2,training=self.training)
  return self.classifier(h)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
 O.mkdir(exist_ok=True);report=[]
 for seed in [1,2]:
  old=H/'runs_ablate'/f'dual_mix_post_cat_s{seed}_e200';sel=json.loads((old/'SELECTED.json').read_text());historical=json.loads((H/f'ablate_report_s{seed}_e200.json').read_text())['dual_mix_post_cat']
  assert sel['path']==historical['selected']['path'] and sel['updates']==200
  checkpoint=R/sel['path'];out=O/f'seed{seed}';out.mkdir(exist_ok=True);model=Model().cuda()
  assert sum(p.numel() for p in model.parameters())==46620
  state=torch.load(checkpoint,map_location='cuda',weights_only=True);model.load_state_dict(state,strict=True);model.eval()
  assert not model.training
  before={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
  record=dict(seed=seed,checkpoint=str(checkpoint),checkpoint_sha=sha(checkpoint),selected=sel,threshold=float(historical['threshold']),parameters=46620,mask='old',architecture='dual_mix_post_cat39 split29 post1',training_updates=0,backward_calls=0,optimizer_steps=0,SAT_calls=0,torch=torch.__version__,python=sys.executable,outputs={})
  for domain,split in [('orig','train'),('trans','train'),('trans','val'),('trans','test')]:
   p=out/f'{domain}_{split}_scores.npy';stamp=out/f'{domain}_{split}_binding.json'
   if p.exists() and stamp.exists():
    b=json.loads(stamp.read_text());assert b['checkpoint_sha']==record['checkpoint_sha'] and b['score_sha']==sha(p);pred=np.load(p);reused=True
   else:
    assert not p.exists() and not stamp.exists(),'incomplete eval artifact retained; inspect before retry'
    d=T.load(domain,split,'A')
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):pred=torch.softmax(model(d['x'],d['edge']).float(),1)[:,1].cpu().numpy()
    assert np.isfinite(pred).all();np.save(p,pred);write(stamp,dict(checkpoint_sha=record['checkpoint_sha'],score_sha=sha(p),rows=len(pred),domain=domain,split=split,loader_sha=sha(H/'train_ab.py')))
    del d;gc.collect();torch.cuda.empty_cache();reused=False
   record['outputs'][domain+'_'+split]=dict(rows=len(pred),sha=sha(p),reused=reused)
   if domain=='trans' and split in ['val','test']:
    now,pv=T.metrics(pred,'trans',split,record['threshold']);record[split]=now
    expected=historical[split]['trusted']['ap'];assert abs(now['trusted']['ap']-expected)<1e-6,(now['trusted']['ap'],expected)
    deltas={key:now['trusted'][key]-historical[split]['trusted'][key] for key in ['ap','auc','r1','r5','control_fpr']}
    record.setdefault('historical_metric_deltas',{})[split]=deltas
    for key,delta in deltas.items():assert abs(delta)<1e-5,(key,now['trusted'][key],historical[split]['trusted'][key])
   print(seed,domain,split,len(pred),'reused',reused,flush=True)
  va=T.arrays('trans','val');p=np.load(out/'trans_val_scores.npy');th=float(np.nextafter(np.quantile(p[va['trusted']&(va['y']==0)],.95),np.inf));assert abs(th-record['threshold'])<1e-6
  assert all(torch.equal(before[k],v.detach().cpu()) for k,v in model.state_dict().items())
  record.update(state_unchanged=True,historical_metrics_reproduced=True,time=datetime.datetime.now().astimezone().isoformat());write(out/'evaluation.json',record);report.append(record)
  del model,state,before;gc.collect();torch.cuda.empty_cache()
 write(O/'evaluation_summary.json',dict(models=report,new_training=0,new_sat=0,forward_limit=8,production_modified=False))
if __name__=='__main__':main()
