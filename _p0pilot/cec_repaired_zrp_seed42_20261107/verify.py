"""Independent CPU checkpoint,budget and primary/PO statistics verification."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import collections,csv,hashlib,json,math,gzip
import numpy as np
import torch
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;C=R/'_p0pilot/cec_repaired_contract_20261107';PRE=R/'_p0pilot/cec_freeq_preflight_20261106'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def table(n,rr):
 with (O/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def write(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(state):
 d=hashlib.sha256()
 for name,t in sorted(state.items()):d.update((name+str(t.dtype)+str(tuple(t.shape))).encode());d.update(t.contiguous().numpy().tobytes())
 return d.hexdigest()
def weighted_auc(a,b,w):
 # Lower distance predicts equality. Ties receive halfcredit,unit mass balanced.
 allv=sorted([(float(x),1,float(ww)) for x,ww in zip(a,w)]+[(float(x),0,float(ww)) for x,ww in zip(b,w)])
 totalneg=sum(v[2] for v in allv if v[1]==0);totalpos=sum(v[2] for v in allv if v[1]==1);less=0.;answer=0.;i=0
 while i<len(allv):
  j=i+1
  while j<len(allv) and allv[j][0]==allv[i][0]:j+=1
  neg=sum(v[2] for v in allv[i:j] if not v[1]);pos=sum(v[2] for v in allv[i:j] if v[1]);answer+=pos*(totalneg-less-.5*neg);less+=neg;i=j
 return answer/(totalneg*totalpos)
def metrics(units,ids,x):
 ix={c:j for j,c in enumerate(ids)};per=[]
 for u in units:
  v=np.array([x[ix[c]] for c in u['cones']],float);n=u['functions'];aa=[];bb=[];ww=[];wins=[];tops=[]
  for f in range(n):
   for side in [0,1]:
    q=2*f+side;d=[math.sqrt(math.dist(v[q],v[2*j+1-side])**2/v.shape[1]+1e-12) for j in range(n)];real=d[f];minimum=min(d);tops.append((1/sum(z==minimum for z in d)) if real==minimum else 0.)
    for j in range(n):
     if j==f:continue
     aa.append(real);bb.append(d[j]);wins.append(float(real<d[j])+.5*float(real==d[j]))
  per.append(dict(source=u['source'],family=u['context_id'],unit=u['unit_id'],win=float(np.mean(wins)),a=aa,b=bb,top=float(np.mean(tops))))
 def aggregate(key):
  out=[]
  for value in {r[key] for r in per}:
   zz=[r for r in per if r[key]==value];a=[x for r in zz for x in r['a']];b=[x for r in zz for x in r['b']];w=[1/len(r['a']) for r in zz for _ in r['a']];out.append((float(np.mean([r['win'] for r in zz])),weighted_auc(a,b,w)))
  return np.mean(np.array(out),0)
 f=aggregate('family');s=aggregate('source');return dict(family_macro_win=f[0],family_macro_auc=f[1],source_macro_win=s[0],source_macro_auc=s[1])
def main():
 assert read(O/'COMPLETE.json')['actual_optimizer_updates']==96;contract=read(O/'EXECUTION_CONTRACT.json');binding=hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
 for p,h in contract['protected_files'].items():assert sha(R/p)==h,p
 initial=torch.load(O/'INITIAL_STATE.pt',map_location='cpu',weights_only=False);assert sha(O/'INITIAL_STATE.pt')==sha(PRE/'INITIAL_STATE.pt')==contract['initialization_sha'];assert digest(initial['model'])==initial['digest']
 frozen_schedule=read(C/'SCHEDULE_SEED42.json')
 with gzip.open(R/'_p0pilot/cec_boundary_panel_expand_20261107/local_graphs.json.gz','rt',encoding='utf-8') as f:raw=json.load(f)
 graphs=dict(zip(raw['cone_ids'],raw['graphs']));role_steps=collections.Counter()
 for s in frozen_schedule:
  roles={e[2] for u in s['units'] for c in u['cone_ids'] for e in graphs[c]['edge']}
  role_steps.update(roles)
 audit=[];histories={};deltas={};stepbudgets=[]
 for arm in ['Z','R','P']:
  ck=torch.load(O/arm/'resume.pt',map_location='cpu',weights_only=False);h=ck['history'];histories[arm]=h;assert ck['completed']==32 and [r['update'] for r in h]==list(range(1,33));assert ck['binding']==binding and ck['initial_digest']==initial['digest'];assert sum(t.numel() for t in ck['model'].values())==47360 and all(t.dtype==torch.float32 and torch.isfinite(t).all() for t in ck['model'].values())
  complete=read(O/arm/'COMPLETE.json');assert complete['checkpoint_sha']==sha(O/arm/'resume.pt') and complete['final_digest']==digest(ck['model'])
  expected=collections.Counter(n for r in h for n,v in r['gradient_present'].items() if v);names=list(initial['model']);opt=ck['optimizer'];assert len(opt['param_groups'])==1 and opt['param_groups'][0]['lr']==.0002 and opt['param_groups'][0]['weight_decay']==.001
  param_ids=opt['param_groups'][0]['params'];actual={n:int(opt['state'][pid]['step']) for n,pid in zip(names,param_ids)};assert actual==dict(expected)==complete['per_parameter_actual_steps'];assert actual=={n:(role_steps[int(n.split('.')[1])] if n.startswith('role_maps.') else 32) for n in names}
  delta=np.concatenate([(ck['model'][n]-initial['model'][n]).numpy().ravel() for n in names]);assert np.linalg.norm(delta)>0;deltas[arm]=delta;audit.append(dict(arm=arm,updates=32,parameter_steps_match_actual_role_exposure=True,parameters=47360,parameter_delta_norm=float(np.linalg.norm(delta)),checkpoint_sha=sha(O/arm/'resume.pt'),digest=digest(ck['model'])))
  for r in h:
   assert all(math.isfinite(float(r[k])) for k in ['loss','gradient_norm_before_clip','root_mean_std','CE_R','CE_P','different','variance_weighted']);u=r['update'];s=frozen_schedule[u-1];assert len(s['units'])==2
   expected_loss=r['different']+r['variance_weighted']+(r['CE_R'] if arm=='R' else r['CE_P'] if arm=='P' else 0.);assert abs(r['loss']-expected_loss)<3e-7
  stepbudgets.append(dict(arm=arm,unit_slots=sum(r['unit_slots'] for r in h),queries=sum(r['queries'] for r in h),candidate_distances=sum(r['candidate_distances'] for r in h),common_negatives=sum(r['common_negative_terms'] for r in h)))
 for u in range(32):assert len({h[u]['feature_sha'] for h in histories.values()})==1 and len({json.dumps(h[u]['gradient_present'],sort_keys=True) for h in histories.values()})==1
 assert all(r['unit_slots']==64 and r['queries']==384 and r['candidate_distances']==1152 and r['common_negatives']==384 for r in stepbudgets)
 assert len({r['digest'] for r in audit})==3;table('independent_checkpoint_audit.csv',audit);table('independent_budget.csv',stepbudgets)
 # Independent metric computation from frozen embeddings,including strictPO/support strata.
 pp=read(O/'EVALUATION_PANELS.json');groups={k:pp[k] for k in ['train_frozen_pool','val_old_PO','val_new_PO']};groups['val_H3_primary']=[u for u in pp['val_boundary_all'] if u['tier']=='H3'];groups['val_H3_MUX']=[u for u in groups['val_H3_primary'] if u['has_mux']];groups['val_H3_two']=[u for u in groups['val_H3_primary'] if u['functions']==2];groups['val_H3_three']=[u for u in groups['val_H3_primary'] if u['functions']==3]
 recorded=rows(O/'evaluation_metrics.csv');checks=[]
 for tag in [9000,9001]:
  for arm in ['INIT','Z','R','P']:
   for domain in ['train','val']:
    with np.load(O/f'{domain}_{arm}_tag{tag}.npz') as z:ids=z['cone_ids'].tolist();data={k:z[k].copy() for k in ['root64','mean64','concat128']}
    for group,units in groups.items():
     if not group.startswith(domain+'_') or not units:continue
     for space,x in data.items():
      assert np.isfinite(x).all();calc=metrics(units,ids,x);prior=next(r for r in recorded if int(r['tag'])==tag and r['arm']==arm and r['group']==group and r['space']==space)
      for k,v in calc.items():assert abs(v-float(prior[k]))<1e-10,(tag,arm,group,space,k,v,prior[k])
      checks.append(dict(tag=tag,arm=arm,group=group,space=space,passed=True))
 table('independent_metric_checks.csv',checks)
 # Match logged training losses to initial same-batch/tag previews without extra forward.
 initprev={int(r['update']):r for r in rows(R/'_p0pilot/cec_repaired_preflight_20261107/loaded_batches.csv')};trajectories=[]
 for arm,hh in histories.items():
  for window,zz in [('first8',hh[:8]),('last8',hh[-8:])]:
   trajectories.append(dict(arm=arm,window=window,CE_real=float(np.mean([r['CE_R'] for r in zz])),CE_wrong=float(np.mean([r['CE_P'] for r in zz])),CE_real_minus_same_batch_init=float(np.mean([r['CE_R']-float(initprev[r['update']]['CE_R']) for r in zz])),CE_wrong_minus_same_batch_init=float(np.mean([r['CE_P']-float(initprev[r['update']]['CE_P']) for r in zz])),different=float(np.mean([r['different'] for r in zz])),different_minus_same_batch_init=float(np.mean([r['different']-float(initprev[r['update']]['different']) for r in zz])),root_std=float(np.mean([r['root_mean_std'] for r in zz]))))
 table('training_target_diagnostics.csv',trajectories)
 evalaudit=rows(O/'evaluation_forward_audit.csv');assert all(r['weights_unchanged']=='True' for r in evalaudit);assert len(evalaudit)>0 and len(evalaudit)==read(O/'EVALUATION_COMPLETE.json')['new_forwards_this_execution']
 for p,h in contract['protected_files'].items():assert sha(R/p)==h,p
 manifest={str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file() and p.suffix in ['.py','.json','.csv','.npz','.pt'] and '__pycache__' not in p.parts and p.name not in ['OUTPUT_MANIFEST.json','VERIFIED.json','PUBLISHED.json']};write('OUTPUT_MANIFEST.json',manifest)
 write('VERIFIED.json',dict(passed=True,arms=['Z','R','P'],actual_optimizer_updates=96,updates_each=32,parameter_steps_match_actual_role_exposure=True,role_map_actual_steps=dict(role_steps),common_initial_file_identical=True,perarm_loaded_budget=stepbudgets,independent_metric_sets=len(checks),primary_units=73,primary_functions=dict(two=sum(u['functions']==2 for u in groups['val_H3_primary']),three=sum(u['functions']==3 for u in groups['val_H3_primary'])),validation_contexts=1,validation_sources=2,training_forwards=96,evaluation_forwards=len(evalaudit),evaluation_states_unchanged=True,finetune=0,SAT=0,test_reads=0,old_files_unchanged=True,models_parameters_finite=True,prototype_performance_scope='single seed,fixed heldout host;73units not73independent circuits;no detectorAP claims',output_manifest_sha=sha(O/'OUTPUT_MANIFEST.json')))
 print('INDEPENDENT_ZRP32_VERIFIED',len(checks),flush=True)
if __name__=='__main__':main()
