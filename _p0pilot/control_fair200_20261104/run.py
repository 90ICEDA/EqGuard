"""Six paired, resumable GPU runs; unchanged strong model and loss. No SAT."""
import os
for k in list(os.environ):
 if k.startswith('P2B_'):del os.environ[k]
os.environ['P2B_MASK']='old'
os.environ['GNN_GRAD_CKPT']='0'
import sys,json,time,gc,hashlib,datetime,traceback
from pathlib import Path
import numpy as np
import torch
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;H=R/'_p0pilot/p2b_main_20261031'
sys.path.insert(0,str(R/'_p0pilot/control_best200_20261104'))
from evaluate import Model,T
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,p)
def save(p,x):
 tmp=p.with_suffix('.tmp');torch.save(x,tmp);os.replace(tmp,p)
def predict(model,domain,split):
 d=T.load(domain,split,'A');model.eval()
 with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):p=torch.softmax(model(d['x'],d['edge']).float(),1)[:,1].cpu().numpy()
 assert np.isfinite(p).all();del d;gc.collect();torch.cuda.empty_cache();return p
def train(seed,arm,manifest):
 out=O/f'seed{seed}'/arm;out.mkdir(parents=True,exist_ok=True)
 if (out/'EVALUATED.json').exists():
  print('REUSE COMPLETE',seed,arm,flush=True);return json.loads((out/'EVALUATED.json').read_text())
 binding=dict(manifest_sha=sha(O/'manifest.json'),runner_sha=sha(Path(__file__)),model_source_sha=sha(R/'_p0pilot/control_best200_20261104/evaluate.py'),loader_sha=sha(H/'train_ab.py'),loss_source_sha=sha(R/'train_test2.2.py'),seed=seed,arm=arm)
 if (out/'binding.json').exists():assert json.loads((out/'binding.json').read_text())==binding
 else:write(out/'binding.json',binding)
 T.seed(seed);model=Model().cuda();assert sum(x.numel() for x in model.parameters())==46620
 init=O/f'init_s{seed}.pt'
 if init.exists():model.load_state_dict(torch.load(init,map_location='cuda',weights_only=True))
 else:
  common=H/f'common_init_s{seed}.pt';assert common.exists()
  ref=torch.load(common,map_location='cuda',weights_only=True);cur=model.state_dict();cur.update({k:v for k,v in ref.items() if k in cur and cur[k].shape==v.shape});model.load_state_dict(cur)
  save(init,{k:v.cpu() for k,v in model.state_dict().items()})
 write(out/'config.json',dict(**binding,init_sha=sha(init),architecture='dual_mix_post_cat 39v2 split29 hidden64 2+2+post1',parameters=46620,updates=200,lr=.0002,weight_decay=.001,loss='unchanged ASL +1.4 softmiss squared',AMP='bf16',SAT=False,EQ=False,normalization='original frozen round32',graph='original round32 v2 directed',selection='old trusted injection-view val AP every5',counts=manifest['counts'],cuda=torch.cuda.get_device_name(),python=sys.executable))
 opt=torch.optim.Adam(model.parameters(),lr=.0002,weight_decay=.001);start=0;best=dict(score=-1.,epoch=-1);records=[]
 if (out/'resume.pt').exists():
  z=torch.load(out/'resume.pt',map_location='cuda',weights_only=False);model.load_state_dict(z['model']);opt.load_state_dict(z['optimizer']);start=z['completed'];best=z['best'];records=z['records'];print('RESUME',seed,arm,start,flush=True)
 domains={};slots={}
 for dm in ['orig','trans']:
  d=T.load(dm,'train','A');base=np.load(O/(dm+'_base_mask.npy'));indices=np.flatnonzero(base)
  d['base_indices']=torch.tensor(indices,device='cuda');domains[dm]=d;slots[dm]=torch.tensor(np.load(O/f'{dm}_{arm}_slots.npy'),device='cuda')
  assert int((d['y'][d['base_indices']]==1).sum())==manifest['counts'][dm]['base_positive']
 try:
  for epoch in range(start,200):
   begin=time.perf_counter();T.seed(seed+epoch);model.train();opt.zero_grad(set_to_none=True);losses=[]
   for dm,d in domains.items():
    ids=torch.cat((d['base_indices'],slots[dm][epoch]))
    with torch.autocast('cuda',dtype=torch.bfloat16):logits=model(d['x'],d['edge'])
    loss=T.domain_loss(logits,d['y'],ids);assert torch.isfinite(loss)
    loss.backward();losses.append(float(loss.detach()));del logits,loss,ids
   norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.);assert torch.isfinite(norm);opt.step()
   rec=dict(update=epoch+1,orig_loss=losses[0],trans_loss=losses[1],train_seconds=time.perf_counter()-begin,grad_norm=float(norm))
   if (epoch+1)%5==0:
    p=predict(model,'trans','val');metrics,_=T.metrics(p,'trans','val',.5);score=metrics['trusted']['ap'];rec['val_ap']=score
    if score>best['score']:
     best=dict(score=score,epoch=epoch+1);save(out/'best.pt',model.state_dict());np.save(out/'selected_val_scores.npy',p)
    records.append(rec);save(out/'resume.pt',dict(model=model.state_dict(),optimizer=opt.state_dict(),completed=epoch+1,best=best,records=records));write(out/'progress.json',dict(seed=seed,arm=arm,completed=epoch+1,best=best,last=rec,time=datetime.datetime.now().astimezone().isoformat()));write(out/'history.json',records)
    print(seed,arm,epoch+1,'valAP',round(score,5),'train_s',round(rec['train_seconds'],2),flush=True)
   else:records.append(rec)
  write(out/'SELECTED.json',dict(**best,updates=200,checkpoint_sha=sha(out/'best.pt'),init_sha=sha(init)))
 finally:
  del domains,slots,opt;gc.collect();torch.cuda.empty_cache()
 model.load_state_dict(torch.load(out/'best.pt',map_location='cuda',weights_only=True));p=np.load(out/'selected_val_scores.npy');a=T.arrays('trans','val');neg=p[a['trusted']&(a['y']==0)];threshold=float(np.nextafter(np.quantile(neg,.95),np.inf))
 # Frozen secondary operation points chosen exclusively using validation positives.
 positive=p[a['trusted']&(a['y']==1)];thresholds={'historical_fpr5':threshold,'val_recall80':float(np.quantile(positive,.2,method='lower')),'val_recall90':float(np.quantile(positive,.1,method='lower'))}
 result=dict(seed=seed,arm=arm,selected=best,thresholds=thresholds,init_sha=sha(init),checkpoint_sha=sha(out/'best.pt'),prediction_sha={})
 for dm,sp in [('orig','train'),('trans','train'),('trans','val'),('trans','test')]:
  pred=p if dm=='trans' and sp=='val' else predict(model,dm,sp);path=out/f'{dm}_{sp}_scores.npy';np.save(path,pred);result['prediction_sha'][dm+'_'+sp]=sha(path)
  if dm=='trans' and sp in ['val','test']:
   result[sp]={name:T.metrics(pred,dm,sp,th)[0] for name,th in thresholds.items()}
 write(out/'EVALUATED.json',result);del model;gc.collect();torch.cuda.empty_cache();return result
def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
 manifest=json.loads((O/'manifest.json').read_text(encoding='utf-8'))
 for p,h in manifest['inputs'].items():assert sha(R/p)==h,p
 for p,h in manifest['files'].items():assert sha(O/p)==h,p
 report=[]
 for seed in [42,1,2]:
  for arm in ['H','C']:report.append(train(seed,arm,manifest))
 write(O/'TRAINING_COMPLETE.json',dict(runs=report,updates=1200,SAT=0,time=datetime.datetime.now().astimezone().isoformat()))
if __name__=='__main__':
 try:main()
 except BaseException:
  (O/('failure_'+str(int(time.time()))+'.log')).write_text(traceback.format_exc(),encoding='utf-8');raise
