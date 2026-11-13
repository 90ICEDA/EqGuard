"""Independent CPU checkpoint, budget and held-out metric audit."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,hashlib,json
import numpy as np
import torch
from sklearn.metrics import roc_auc_score
O=Path(__file__).resolve().parent;R=O.parents[1];C=R/'_p0pilot/cec_relative_contract_20261106'
ARMS=['Z','A_R','A_P','S_R','S_P']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def state_sha(model,projection):
 h=hashlib.sha256()
 for pre,sd in [('model',model),('projection',projection)]:
  for n,t in sorted(sd.items()):h.update((pre+n+str(t.dtype)+str(tuple(t.shape))).encode());h.update(t.contiguous().numpy().tobytes())
 return h.hexdigest()
def main():
 complete=read(O/'COMPLETE.json');assert complete['optimizer_updates']==250 and complete['finetune']==complete['SAT']==complete['test_reads']==0
 execution=read(O/'EXECUTION_CONTRACT.json')
 for p,h in execution['frozen_files'].items():assert sha(R/p)==h,p
 initial=torch.load(O/'INITIAL_STATE.pt',map_location='cpu',weights_only=False);assert state_sha(initial['model'],initial['projection'])==initial['digest']
 old=torch.load(R/'_p0pilot/control_v3_eligible_20261104/init_s42.pt',map_location='cpu',weights_only=True)
 for k,t in old.items():assert torch.equal(t,initial['model'][k]),k
 for k,t in initial['model'].items():
  if k not in old:assert k.startswith(('boundary_adapter.','pin_boundary_adapter.','pin_scales.')) and t.count_nonzero()==0
 torch.manual_seed(819);proj=torch.nn.Sequential(torch.nn.Linear(128,64),torch.nn.ReLU(),torch.nn.Linear(64,32));assert all(torch.equal(t,initial['projection'][k]) for k,t in proj.state_dict().items())
 schedule=read(C/'schedule_seed42.json');verified=[];timing=[]
 for arm in ARMS:
  ck=torch.load(O/arm/'resume.pt',map_location='cpu',weights_only=False);done=read(O/arm/'COMPLETE.json');hist=read(O/arm/'history.json')
  assert ck['completed']==done['updates']==50 and ck['initial_sha']==initial['digest'] and sha(O/arm/'resume.pt')==done['checkpoint_sha'];assert ck['history']==hist and [r['update'] for r in hist]==list(range(1,51))
  op=ck['optimizer'];assert {int(s['step']) for s in op['state'].values() if 'step' in s}=={50}
  assert all(p['lr']==.0002 and p['weight_decay']==.001 for p in op['param_groups'])
  for n,t in ck['model'].items():
   assert torch.isfinite(t).all()
   if n.startswith(('classifier.','fn_head.')):assert torch.equal(t,initial['model'][n])
   if n.endswith('num_batches_tracked'):assert int(t)==int(initial['model'][n])+50
  assert all(torch.isfinite(t).all() for t in ck['projection'].values())
  counts=collections.Counter();query=neg=slots=0
  for r in hist:
   rr=[x for x in schedule if x['update']==r['update']];assert r['triple_ids']==[x['triple_id'] for x in rr];assert r['source_count']==len(rr) and r['queries']==4*len(rr) and r['common_negatives']==6*len(rr) and r['boundary_tag']==r['update'] and r['rng_seed']==100042+r['update']
   assert all(np.isfinite(r[k]) for k in ['loss','grad_norm','projection_std','A_R','A_P','S_R','S_P','different','variance_weighted']);assert r['projection_std']>.01
   counts.update(x['source'] for x in rr);query+=r['queries'];neg+=r['common_negatives'];slots+=len(rr);timing.append(r['seconds'])
   association=r[arm] if arm!='Z' else 0.;assert abs(r['loss']-(association+r['different']+r['variance_weighted']))<2e-6
  assert len(counts)==8 and set(counts.values())=={25} and slots==200 and query==800 and neg==1200
  verified.append(dict(arm=arm,updates=50,optimizer_actual_step=50,triple_slots=slots,positive_pair_slots=2*slots,queries=query,common_negative_terms=neg,minimum_projection_std=min(r['projection_std'] for r in hist),final_projection_std=hist[-1]['projection_std'],median_step_seconds=float(np.median([r['seconds'] for r in hist])),model_SHA=sha(O/arm/'resume.pt'),unused_heads_unchanged=True,BN_actual_updates=50))
 table('checkpoint_audit.csv',verified)
 certs=read(C/'evaluation_panel.json');primary=sorted({r['source'] for r in rows(C/'evaluation_support.csv') if r['primary_source']=='True'});published=rows(O/'evaluation_summary.csv');sourcepub=rows(O/'evaluation_by_source.csv');independent=[]
 for arm in ARMS:
  with np.load(O/f'val_{arm}_remap9000.npz') as cache:
   ix={c:j for j,c in enumerate(cache['cone_ids'].tolist())};assert set(ix)=={c for t in certs for c in t['cones']}
   for space,x in [('root64',cache['concat128'][:,:64]),('mean64',cache['concat128'][:,64:]),('concat128',cache['concat128']),('projection32',cache['projection32'])]:
    obs=collections.defaultdict(list)
    for t in certs:
     vv=[x[ix[c]].astype(np.float64) for c in t['cones']]
     # Four anchors, each uses truth and swapped candidate from the same other view.
     for ai,ri,wi in [(0,1,3),(2,3,1),(1,0,2),(3,2,0)]:
      rms=lambda j,k:float(np.sqrt(np.mean((vv[j]-vv[k])**2)))
      obs[t['source']].append((rms(ai,ri),rms(ai,wi)))
    macro_win=[];macro_auc=[];all_r=[];all_w=[]
    for source in primary:
     a,b=np.array(obs[source]).T;win=float(np.mean((a<b)+.5*(a==b)));auc=float(roc_auc_score([1]*len(a)+[0]*len(b),-np.r_[a,b]));macro_win.append(win);macro_auc.append(auc);all_r.extend(a);all_w.extend(b)
     pub=next(r for r in sourcepub if r['arm']==arm and r['condition']=='correct' and r['space']==space and r['source']==source);assert abs(win-float(pub['anchor_win']))<1e-12 and abs(auc-float(pub['cross_auc']))<1e-12
    out=dict(arm=arm,space=space,source_macro_win=float(np.mean(macro_win)),source_macro_auc=float(np.mean(macro_auc)),cross_auc=float(roc_auc_score([1]*len(all_r)+[0]*len(all_w),-np.r_[all_r,all_w])))
    pub=next(r for r in published if r['arm']==arm and r['condition']=='correct' and r['space']==space and r['scope']=='primary_two_sources')
    assert all(abs(out[k]-float(pub[k]))<1e-12 for k in ['source_macro_win','source_macro_auc','cross_auc']);independent.append(out)
 table('independent_primary_metrics.csv',independent)
 pr=read(O/'PRIMARY_RESULT.json');d={r['arm']:r for r in independent if r['space']=='root64'}
 for metric in ['source_macro_win','source_macro_auc','cross_auc']:
  r=pr['contrasts'][metric];assert abs(r['S_R_minus_S_P']-(d['S_R'][metric]-d['S_P'][metric]))<1e-12 and abs(r['S_R_minus_Z']-(d['S_R'][metric]-d['Z'][metric]))<1e-12
 # Acceptance must remain as preregistered, never replace it with improved AUC alone.
 win_gate=d['S_R']['source_macro_win']-d['S_P']['source_macro_win']>=.02 and d['S_R']['source_macro_win']-d['Z']['source_macro_win']>=.02
 ss=lambda arm,source:float(next(x['anchor_win'] for x in sourcepub if x['arm']==arm and x['source']==source and x['space']=='root64' and x['condition']=='correct'))
 source_gate=all(ss('S_R',source)>=ss('S_P',source) and ss('S_R',source)>=ss('Z',source) for source in primary)
 auc_gate=d['S_R']['source_macro_auc']>d['S_P']['source_macro_auc'] and d['S_R']['source_macro_auc']>d['Z']['source_macro_auc']
 passed=win_gate and source_gate and auc_gate
 assert pr['functional_performance_gate']==passed and pr['predeclared_win_gate']==win_gate and pr['predeclared_source_direction_gate']==source_gate and pr['source_macro_AUC_direction_agrees']==auc_gate
 for p,h in execution['frozen_files'].items():assert sha(R/p)==h,p
 result=dict(passed=True,optimizer_updates=250,all_five_exact50=True,no_duplicate_or_missing_updates=True,budgets_match_each_arm=True,all_five_same_initial_state=True,initial_semantic_zero=True,original_classifier_and_unused_head_unchanged=True,all_states_finite=True,all_model_BN_actual_updates=50,independent_source_and_primary_metrics_exact_match=True,predeclared_performance_gate_passed=passed,old_files_unchanged=True,finetune=0,SAT=0,test_reads=0,median_training_step_seconds=float(np.median(timing)),whole_run_seconds_approx=(O/'COMPLETE.json').stat().st_mtime-(O/'EXECUTION_CONTRACT.json').stat().st_mtime,output_SHA={f'{a}/resume.pt':sha(O/a/'resume.pt') for a in ARMS})
 (O/'VERIFIED.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
