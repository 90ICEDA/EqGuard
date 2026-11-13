"""Independent CPU checkpoint,budget,ranking and JS/entropy verification."""
from pathlib import Path
import collections,csv,hashlib,importlib.util,json,math,gzip
import numpy as np
import torch
O=Path(__file__).resolve().parent;R=O.parents[1];C=R/'_p0pilot/cec_repaired_contract_20261107'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
V=load('retained_independent_metrics',R/'_p0pilot/cec_repaired_zrp_seed42_20261107/verify.py')
def main():
 assert read(O/'COMPLETE.json')['actual_optimizer_updates']==192;contract=read(O/'EXECUTION_CONTRACT.json');parent=contract['parent'];binding=hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest();initial=torch.load(O/'INITIAL_STATE.pt',map_location='cpu',weights_only=False);assert sha(O/'INITIAL_STATE.pt')==parent['initial_sha'];assert V.digest(initial['model'])==initial['digest'];schedule=read(C/'SCHEDULE_SEED42.json');hist={};budgets={};digests=[]
 with gzip.open(R/'_p0pilot/cec_boundary_panel_expand_20261107/local_graphs.json.gz','rt',encoding='utf-8') as f:raw=json.load(f)
 graphs=dict(zip(raw['cone_ids'],raw['graphs']));role_steps=collections.Counter()
 for s in schedule:role_steps.update({e[2] for u in s['units'] for c in u['cone_ids'] for e in graphs[c]['edge']})
 for arm in parent['arms']:
  ck=torch.load(O/arm/'resume.pt',map_location='cpu',weights_only=False);h=ck['history'];hist[arm]=h;assert ck['completed']==32 and ck['binding']==binding and ck['initial_digest']==initial['digest'];assert [r['step'] for r in h]==list(range(1,33));complete=read(O/arm/'COMPLETE.json');assert complete['checkpoint_sha']==sha(O/arm/'resume.pt') and complete['final_digest']==V.digest(ck['model']);digests.append(complete['final_digest'])
  assert sum(x.numel() for x in ck['model'].values())==47360 and all(x.dtype==torch.float32 and torch.isfinite(x).all() for x in ck['model'].values());names=list(initial['model']);opt=ck['optimizer'];assert len(opt['param_groups'])==1 and opt['param_groups'][0]['lr']==.0002 and opt['param_groups'][0]['weight_decay']==.001
  actual={n:int(opt['state'][pid]['step']) for n,pid in zip(names,opt['param_groups'][0]['params'])};expected={n:role_steps[int(n.split('.')[1])] if n.startswith('role_maps.') else 32 for n in names};assert actual==expected==complete['per_parameter_steps']==dict(collections.Counter(n for r in h for n,v in r['gradient_presence'].items() if v))
  b=collections.Counter()
  for r in h:
   for k in ['loss','JS','base_loss','gradient_norm','min_root_std','CE_R','CE_P','different','variance_weighted']:assert math.isfinite(r[k])
   base=r['different']+r['variance_weighted']+(r['CE_R'] if arm[0]=='R' else r['CE_P'] if arm[0]=='P' else 0);loss=base+(contract['coefficient'] if arm[1]=='1' else 0)*r['JS'];assert abs(loss-r['loss'])<4e-7
   b.update({k:r[k] for k in ['logical_units','logical_queries','encoded_units','encoded_queries','candidate_distances','common_negatives','JS_queries']})
  budgets[arm]=dict(b)
 assert len(set(digests))==6 and all(b==dict(logical_units=64,logical_queries=384,encoded_units=128,encoded_queries=768,candidate_distances=2304,common_negatives=768,JS_queries=384) for b in budgets.values())
 for i in range(32):assert len({h[i]['feature_a_sha'] for h in hist.values()})==len({h[i]['feature_b_sha'] for h in hist.values()})==1 and len({json.dumps(h[i]['gradient_presence'],sort_keys=True) for h in hist.values()})==1
 with (R/'_p0pilot/cec_dualcode_preflight_20261107/six_arm_budget_ledger.csv').open(encoding='utf-8-sig',newline='') as f:prior=list(csv.DictReader(f))
 for i in range(32):
  r=next(r for r in prior if r['arm']=='R0' and int(r['step'])==i+1)
  assert all(h[i]['feature_a_sha']==r['features_a_sha'] and h[i]['feature_b_sha']==r['features_b_sha'] for h in hist.values())
 pp=read(O/'EVALUATION_PANELS.json');main=pp['val_H3_primary'];assert len(main)==73;checks=0;maxerr=0;stability=rows('encoding_stability.csv');flat_checks=0
 for row in rows('evaluation_metrics.csv'):
  group=row['group'];domain='train' if group.startswith('train_') else 'val';base=pp['train_frozen_pool'] if domain=='train' else main
  if group in pp:uu=pp[group]
  elif '_source/' in group:
   source=group.split('_source/',1)[1];suffix=None
   if '/' in source:source,suffix=source.split('/',1)
   uu=[u for u in base if u['source']==source and (suffix is None or bool(u['has_mux'])==(suffix=='MUX'))]
  elif '_candidates' in group:uu=[u for u in base if u['functions']==int(group[-1])]
  else:uu=[u for u in base if bool(u['has_mux'])==group.endswith('_MUX')]
  with np.load(O/f"{domain}_{row['arm']}_tag{row['tag']}.npz") as z:ids=z['cone_ids'].tolist();x=z['root64'].astype(float)
  calc=V.metrics(uu,ids,x)
  for k,v in calc.items():err=abs(v-float(row[k]));maxerr=max(maxerr,err);assert err<1e-10
  checks+=1
  # Independent distribution diagnostics for all main/train states and12tags.
  if group not in ['val_H3_primary','train_frozen_pool']:continue
  ix={c:i for i,c in enumerate(ids)};entropy=std=normmargin=0
  for u in uu:
   n=u['functions'];v=x[[ix[c] for c in u['cones']]]
   for f in range(n):
    for side in [0,1]:
     ds=np.array([math.sqrt(math.dist(v[2*f+side],v[2*j+1-side])**2/64+1e-12) for j in range(n)]);p=np.exp(-ds);p/=p.sum();w=1/(len(uu)*2*n);entropy+=w*(-sum(float(y)*math.log(float(y)) for y in p)/math.log(n));sd=float(np.std(ds));std+=w*sd;normmargin+=w*np.mean([(ds[j]-ds[f])/max(sd,1e-8) for j in range(n) if j!=f])
  assert abs(entropy-float(row['normalized_candidate_entropy']))<1e-10 and abs(std-float(row['candidate_distance_std']))<1e-10 and abs(normmargin-float(row['normalized_pair_margin']))<1e-10;flat_checks+=1
 # Independent paired-map JS and ranking flips for main73 andtrain7.
 stability_checks=0
 for row in stability:
  if row['group'] not in ['val_H3_primary','train_frozen_pool']:continue
  domain=row['domain'];uu=main if domain=='val' else pp['train_frozen_pool'];vv=[]
  for tag in [row['tag_a'],row['tag_b']]:
   with np.load(O/f"{domain}_{row['arm']}_tag{tag}.npz") as z:ids=z['cone_ids'].tolist();x=z['root64'].astype(float)
   ix={c:i for i,c in enumerate(ids)};qq=[]
   for u in uu:
    n=u['functions'];v=x[[ix[c] for c in u['cones']]]
    for f in range(n):
     for side in [0,1]:
      ds=np.array([math.sqrt(math.dist(v[2*f+side],v[2*j+1-side])**2/64+1e-12) for j in range(n)]);p=np.exp(-ds);p/=p.sum();win=[float(ds[f]<ds[j])+.5*float(ds[f]==ds[j]) for j in range(n) if j!=f];qq.append((p,np.array(win),1/(len(uu)*2*n)))
   vv.append(qq)
  js=flip=0
  for (p,a,w),(q,b,_) in zip(*vv):
   m=(p+q)*.5;js+=w*.5*(sum(p*np.log(p/m))+sum(q*np.log(q/m)));flip+=w*float(np.mean(a!=b))
  assert abs(js-float(row['weighted_JS']))<1e-10 and abs(flip-float(row['pairwise_rank_flip_rate']))<1e-10;stability_checks+=1
 audit=rows('evaluation_forward_audit.csv');assert all(r['weights_unchanged']=='True' for r in audit)
 for p,h in contract['protected_files'].items():assert sha(R/p)==h,p
 result=dict(passed=True,actual_updates=192,updates_each=32,common_initialization=True,six_distinct_final_states=True,per_arm_budget=budgets,role_map_steps=dict(role_steps),independent_metric_sets=checks,max_metric_error=maxerr,independent_flat_distribution_checks=flat_checks,independent_stability_checks=stability_checks,evaluation_forwards=len(audit),old_files_unchanged=True,finetune=0,SAT=0,test_reads=0)
 (O/'VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
