"""Authorized five-group budget-bounded normal-label experiment,seed42,noSAT/EQ."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,gc,hashlib,importlib.util,json,shutil,sys,time,traceback
import numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;L=R/'_p0pilot/control_loader_po_20261105';V=R/'_p0pilot/control_v3_eligible_20261104';B=R/'_p0pilot/control_budget_bounded_20261105'
sys.path.insert(0,str(L));from supervision_loader import FiveGroupLoader,read,sha
s=importlib.util.spec_from_file_location('frozen_v3_engine_for_five',V/'frozen_engine_v3.py');E=importlib.util.module_from_spec(s);s.loader.exec_module(E);torch=E.torch;T=E.T;Model=E.Model;ARMS=['G0','GB','GM','GBM','GAll']
def write(n,v):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,p)
def save(p,v):
 tmp=p.with_suffix(p.suffix+'.tmp');torch.save(v,tmp);os.replace(tmp,p)
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def prepare(loader):
 protected=dict(loader.checked_files)
 for p in [V/'frozen_engine_v3.py',V/'init_s42.pt',L/'supervision_loader.py',L/'PO_EVALUATION_CONTRACT.json',L/'LOADING_VERIFIED.json',R/'_p0pilot/control_best200_20261104/evaluate.py',R/'_p0pilot/p2b_main_20261031/train_ab.py',R/'train_test2.2.py',R/'models/gin_net.py',Path(__file__)]:protected[str(p.relative_to(R))]=sha(p)
 for p in L.iterdir():
  if p.is_file() and p.suffix in ['.json','.csv','.npz']:protected[str(p.relative_to(R))]=sha(p)
 contract=dict(authorization='user authorized integrate new loader andrun fivegroups seed42 200updates;supersedes historical noqueue flags here without editing parent contracts',parent_sha=sha(B/'EXPERIMENT_CONTRACT.json'),loader_sha=sha(L/'supervision_loader.py'),arms=ARMS,seed=42,updates_each=200,variant='main_fanout05',feature='39v3',architecture='frozen dual_mix_post_cat split29 hidden64 2+2+post1 46620params',initial_sha=sha(V/'init_s42.pt'),optimizer='Adam lr.0002 wd.001 clip1 BF16;orig then transbackward oneupdate',loss='unchanged T.domain_loss ASL+1.4softmiss^2;only frozen stepindices consumed,never oldmask',selection='mean oldtrusted __inj transvalAP every5;strictbestearliest on ties;unchanged',thresholds='same transval quantilerules .2/.1 positive lower andnextafter95%negative;no testselection',evaluation='all6splits,bothdomains;sourceequal normalregion/wholeviewalarm;AP/trigger/payloadrecall;frozen POstrata,support NA;testexploratory',protected_files=protected,SAT=0,EQ=0,positive_protection=False)
 if (O/'EXECUTION_CONTRACT.json').exists():assert read(O/'EXECUTION_CONTRACT.json')==contract
 else:write('EXECUTION_CONTRACT.json',contract)
 for p,h in protected.items():assert sha(R/p)==h,p
 if not (O/'init_s42.pt').exists():shutil.copy2(V/'init_s42.pt',O/'init_s42.pt')
 assert sha(O/'init_s42.pt')==contract['initial_sha'];T.CONTRACT=loader.feature_contract;T.NORM=loader.normalization
 # Patch only this imported runtime's loader;no source file or default mask is changed.
 T.arrays=loader.arrays;T.load=lambda dm,sp,arm:loader.torch_graph(dm,sp,'cuda')
 assert T.MASK_MODE=='old' and not T.EXTRA and T.EQ==0
 if not (O/'LOADER_INTEGRATION_VERIFIED.json').exists():
  prior=list(csv.DictReader((L/'loaded_indices_ledger.csv').open(encoding='utf-8-sig',newline='')));expected={(x['domain'],x['arm'],int(x['update'])):x for x in prior if x['variant']=='main_fanout05'};records=[];digests={};exposure={}
  for dm in ['orig','trans']:
   a=loader.arrays(dm);counts={};cc=loader.contract['domains'][dm]
   for arm in ARMS:
    nc=np.zeros(len(a['y']),np.int32);h=hashlib.sha256()
    for step in range(200):
     q=loader.step(dm,arm,step);ids=q.indices;yy=a['y'][ids];hh=hashlib.sha256(ids.tobytes()).hexdigest();ref=expected[dm,arm,step+1];assert hh==ref['index_sha'];assert len(np.unique(ids))==len(ids) and (a['trusted'][ids]&a['physical'][ids]).all();assert int((yy==1).sum())==cc['positive'] and int((yy==0).sum())==cc['negative_per_update'];nc[ids[len(q.positive):]]+=1;h.update(ids.tobytes());records.append(dict(domain=dm,arm=arm,update=step+1,index_sha=hh,positive=cc['positive'],negative=cc['negative_per_update'],normal_control_entries=int(ref['normal_control_entries'])))
    assert nc.max()<=128;counts[arm]=np.sort(nc[nc>0]);digests[dm+','+arm]=h.hexdigest();exposure[dm+','+arm]=dict(negative_unique=int((nc>0).sum()),max_exposure=int(nc.max()))
   assert all(np.array_equal(counts['G0'],c) for c in counts.values())
  table('integrated_indices_ledger.csv',records);write('LOADER_INTEGRATION_VERIFIED.json',dict(passed=True,actual_records=2000,old_preflight_indices_match=True,no_default_mask=True,budgets=loader.contract['domains'],ordered_digests=digests,exposure=exposure,model_updates=0))
 return contract,hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
def predict(model,loader,dm,sp):
 d=loader.torch_graph(dm,sp,'cuda');assert set(d)=={'x','edge','y'};model.eval()
 with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):p=torch.softmax(model(d['x'],d['edge']).float(),1)[:,1].cpu().numpy()
 assert np.isfinite(p).all();del d;gc.collect();torch.cuda.empty_cache();return p
def train(arm,loader,contract,binding):
 out=O/arm;out.mkdir(exist_ok=True)
 if (out/'EVALUATED.json').exists():
  ev=read(out/'EVALUATED.json');assert ev['binding']==binding;print('REUSE_COMPLETE',arm,flush=True);return ev
 T.seed(42);model=Model().cuda();assert sum(p.numel() for p in model.parameters())==46620;model.load_state_dict(torch.load(O/'init_s42.pt',map_location='cuda',weights_only=True));opt=torch.optim.Adam(model.parameters(),lr=.0002,weight_decay=.001);start=0;best=dict(score=-1.,epoch=-1);history=[]
 if (out/'resume.pt').exists():
  ck=torch.load(out/'resume.pt',map_location='cuda',weights_only=False);assert ck['binding']==binding and ck['arm']==arm;model.load_state_dict(ck['model']);opt.load_state_dict(ck['optimizer']);start=ck['completed'];best=ck['best'];history=ck['history'];print('RESUME',arm,start,flush=True)
 domains={dm:loader.torch_graph(dm,'train','cuda') for dm in ['orig','trans']};assert all(set(d)=={'x','edge','y'} for d in domains.values());torch.cuda.reset_peak_memory_stats()
 for step in range(start,200):
  begin=time.perf_counter();T.seed(42+step);model.train();opt.zero_grad(set_to_none=True);losses=[];hashes=[]
  for dm,d in domains.items():
   q=loader.step(dm,arm,step);ids=q.torch_indices('cuda');selected=d['y'].index_select(0,ids);assert int((selected==1).sum())==loader.contract['domains'][dm]['positive'] and int((selected==0).sum())==loader.contract['domains'][dm]['negative_per_update'];hashes.append(hashlib.sha256(q.indices.tobytes()).hexdigest())
   with torch.autocast('cuda',dtype=torch.bfloat16):logits=model(d['x'],d['edge'])
   loss=T.domain_loss(logits,d['y'],ids);assert torch.isfinite(loss);loss.backward();losses.append(float(loss.detach()));del logits,loss,ids
  assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters());norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.);assert torch.isfinite(norm);opt.step();rec=dict(update=step+1,orig_loss=losses[0],trans_loss=losses[1],grad_norm=float(norm),orig_indices_sha=hashes[0],trans_indices_sha=hashes[1],train_seconds=time.perf_counter()-begin)
  if (step+1)%5==0:
   p=predict(model,loader,'trans','val');metrics,_=T.metrics(p,'trans','val',.5);score=metrics['trusted']['ap'];assert np.isfinite(score);rec['val_ap']=score
   if score>best['score']:best=dict(score=score,epoch=step+1);save(out/'best.pt',model.state_dict());np.save(out/'selected_val_scores.npy',p)
  history.append(rec);save(out/'resume.pt',dict(binding=binding,arm=arm,model=model.state_dict(),optimizer=opt.state_dict(),completed=step+1,best=best,history=history));write(arm+'/history.json',history)
  if step==0:write(arm+'/FIRST_STEP.json',dict(passed=True,orig_loss=losses[0],trans_loss=losses[1],peak_gpu_bytes=torch.cuda.max_memory_allocated(),supervision_from_new_loader=True))
  if (step+1)%25==0 or step==0:print('UPDATE',arm,step+1,'bestAP',round(best['score'],6),'seconds',round(rec['train_seconds'],3),flush=True)
 write(arm+'/TRAINED.json',dict(updates=200,selected=best,checkpoint_sha=sha(out/'best.pt'),initial_sha=sha(O/'init_s42.pt'),peak_gpu_bytes=torch.cuda.max_memory_allocated()));del domains,opt;gc.collect();torch.cuda.empty_cache();model.load_state_dict(torch.load(out/'best.pt',map_location='cuda',weights_only=True));p=np.load(out/'selected_val_scores.npy');a=loader.arrays('trans','val');pos=p[a['trusted']&(a['y']==1)];neg=p[a['trusted']&(a['y']==0)];thresholds=dict(historical_fpr5=float(np.nextafter(np.quantile(neg,.95),np.inf)),val_recall80=float(np.quantile(pos,.2,method='lower')),val_recall90=float(np.quantile(pos,.1,method='lower')));ev=dict(binding=binding,arm=arm,seed=42,updates=200,selected=best,thresholds=thresholds,initial_sha=sha(O/'init_s42.pt'),checkpoint_sha=sha(out/'best.pt'),prediction_sha={})
 for dm in ['orig','trans']:
  for sp in ['train','val','test']:
   pred=p if (dm,sp)==('trans','val') else predict(model,loader,dm,sp);np.save(out/f'{dm}_{sp}_scores.npy',pred);ev['prediction_sha'][dm+'_'+sp]=sha(out/f'{dm}_{sp}_scores.npy')
 write(arm+'/EVALUATED.json',ev);print('ARM_COMPLETE',arm,'selected',best,flush=True);del model;gc.collect();torch.cuda.empty_cache();return ev
def main():
 assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available();torch.set_num_threads(2);loader=FiveGroupLoader();contract,binding=prepare(loader);print('NEW_LOADER_BUDGET_VERIFIED',flush=True);report=[];start=time.perf_counter()
 for arm in ARMS:report.append(train(arm,loader,contract,binding))
 for p,h in contract['protected_files'].items():assert sha(R/p)==h,p
 write('TRAINING_COMPLETE.json',dict(runs=report,arms=ARMS,actual_updates=1000,seed=42,SAT=0,EQ=0,old_files_unchanged=True,seconds=time.perf_counter()-start));print('FIVE_ARM_COMPLETE',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:(O/f'failure_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
