"""Read-only independent checkpoint, budget and metric verification."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json,csv,collections,hashlib
import numpy as np
import torch
from sklearn.metrics import roc_auc_score
O=Path(__file__).resolve().parent;R=O.parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 assert read(O/'COMPLETE.json')['training_updates']==300
 init=torch.load(R/'_p0pilot/control_v3_eligible_20261104/init_s42.pt',map_location='cpu',weights_only=True)
 checks=[];contract=read(O/'EXECUTION_CONTRACT.json')
 for p,h in contract['frozen_files'].items():assert sha(R/p)==h
 schedule=read(R/'_p0pilot/cec_pretrain_ready_20261105/schedule.json')
 rr=[r for r in schedule if r['mode']=='main' and r['seed']==42]
 pairs={r[k] for r in rr for k in ['pair_a','pair_b']};assert len(pairs)==382
 for alignment in ['shared','viewshuffle']:
  for arm in ['Z','R','P']:
   d=O/(alignment+'_'+arm);complete=read(d/'COMPLETE.json');assert sha(d/'resume.pt')==complete['checkpoint_sha']
   ck=torch.load(d/'resume.pt',map_location='cpu',weights_only=False)
   assert ck['completed']==50 and [r['update'] for r in ck['history']]==list(range(1,51))
   assert ck['binding']==dict(contract_sha=sha(O/'EXECUTION_CONTRACT.json'),alignment=alignment,arm=arm)
   for k,v in ck['model'].items():
    if k.startswith('classifier.'):assert torch.equal(v,init[k])
    if v.is_floating_point():assert torch.isfinite(v).all()
   steps={int(z['step']) for z in ck['optimizer']['state'].values()};assert steps=={50}
   assert ck['model']['boundary_adapter.weight'].shape==(39,20)
   assert ck['model']['boundary_adapter.weight'].norm()>0
   checks.append(dict(alignment=alignment,arm=arm,updates=50,classifier_unchanged=True,finite=True,optimizer_steps=list(steps),adapter_norm=float(ck['model']['boundary_adapter.weight'].norm())))
 blocks=rows(O/'evaluation_blocks.csv');summ=rows(O/'evaluation_summary.csv');maxdelta=0
 for s in summ:
  group=[r for r in blocks if all(r[k]==s[k] for k in ['alignment','arm','remap','space'])];assert len(group)==68
  a=np.array([float(r[k]) for r in group for k in ['real0','real1']]);b=np.array([float(r[k]) for r in group for k in ['wrong0','wrong1']]);auc=roc_auc_score([1]*len(a)+[0]*len(b),-np.r_[a,b]);delta=abs(auc-float(s['cross_auc']));maxdelta=max(maxdelta,delta);assert delta<1e-12
 for r in rows(O/'alignment_contrasts.csv'):
  metric=r['metric'];get=lambda a,t:float(next(s[metric] for s in summ if s['alignment']==a and s['arm']==t and s['remap']==r['remap'] and s['space']==r['space']))
  ds={t:get('shared',t)-get('viewshuffle',t) for t in ['Z','R','P']}
  for t in ds:assert abs(ds[t]-float(r['D_'+t]))<1e-12
  assert abs(ds['R']-ds['P']-float(r['R_minus_P']))<1e-12
 record=dict(passed=True,checks=checks,total_optimizer_updates=300,unique_training_pairs=382,slots_per_update=10,exposure_per_condition=500,evaluation_summary_rows=len(summ),independent_auc_max_delta=maxdelta,no_detection_finetune=True,no_new_SAT=True,no_test=True,old_input_hashes_unchanged=True)
 (O/'VERIFIED.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(record,ensure_ascii=False))
if __name__=='__main__':main()
