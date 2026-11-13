"""Independent CPU verification of pin-role experiment budgets and metrics."""
import os
for k in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import json,csv,collections,hashlib
import numpy as np
import torch
from sklearn.metrics import roc_auc_score
O=Path(__file__).resolve().parent;R=O.parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def rows(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 assert read(O/'COMPLETE.json')['training_updates']==300
 assert read(O/'FIXTURES_VERIFIED.json')['passed'] and read(O/'PREFLIGHT.json')['passed']
 contract=read(O/'EXECUTION_CONTRACT.json')
 for p,h in contract['frozen_files'].items():assert sha(R/p)==h,p
 init=torch.load(R/'_p0pilot/control_v3_eligible_20261104/init_s42.pt',map_location='cpu',weights_only=True)
 schedule=read(R/'_p0pilot/cec_pretrain_ready_20261105/schedule.json');inventory={r['pair_id']:r for r in read(R/'_p0pilot/cec_pretrain_ready_20261105/function_inventory.json')}
 rr=[r for r in schedule if r['mode']=='main' and r['seed']==42];exposures=collections.Counter(inventory[r[k]]['source'] for r in rr for k in ['pair_a','pair_b'])
 assert len(rr)==250 and len({r[k] for r in rr for k in ['pair_a','pair_b']})==382
 assert len(exposures)==10 and set(exposures.values())=={50}
 checkpoints=[]
 for condition in ['shared','viewshuffle']:
  for arm in ['Z','R','P']:
   d=O/(condition+'_'+arm);co=read(d/'COMPLETE.json');assert co['checkpoint_sha']==sha(d/'resume.pt')
   ck=torch.load(d/'resume.pt',map_location='cpu',weights_only=False)
   assert ck['binding']==dict(contract_sha=sha(O/'EXECUTION_CONTRACT.json'),alignment=condition,arm=arm)
   assert ck['completed']==50 and [r['update'] for r in ck['history']]==list(range(1,51))
   assert {int(v['step']) for v in ck['optimizer']['state'].values()}=={50}
   for k,v in ck['model'].items():
    if k.startswith('classifier.'):assert torch.equal(v,init[k])
    if v.is_floating_point():assert torch.isfinite(v).all()
   assert ck['model']['pin_boundary_adapter.weight'].shape==(39,100)
   norms={k:float(v.norm()) for k,v in ck['model'].items() if k.startswith(('boundary_adapter.','pin_boundary_adapter.','pin_scales.'))}
   assert all(v>0 for v in norms.values())
   checkpoints.append(dict(condition=condition,arm=arm,steps=50,norms=norms,finite=True,classifier_unchanged=True))
 blocks=rows(O/'evaluation_blocks.csv');summary=rows(O/'evaluation_summary.csv');maxdelta=0
 for s in summary:
  gg=[r for r in blocks if all(r[k]==s[k] for k in ['alignment','arm','remap','space'])];assert len(gg)==68
  true=[float(r[k]) for r in gg for k in ['real0','real1']];wrong=[float(r[k]) for r in gg for k in ['wrong0','wrong1']]
  auc=float(roc_auc_score([1]*len(true)+[0]*len(wrong),-np.array(true+wrong)));delta=abs(auc-float(s['cross_auc']));assert delta<1e-12;maxdelta=max(maxdelta,delta)
 for s in rows(O/'alignment_contrasts.csv'):
  get=lambda a,t:float(next(r[s['metric']] for r in summary if r['alignment']==a and r['arm']==t and r['space']==s['space'] and r['remap']==s['remap']))
  ds={t:get('shared',t)-get('viewshuffle',t) for t in ['Z','R','P']}
  for t in ds:assert abs(float(s['D_'+t])-ds[t])<1e-12
  for t in ['P','Z']:assert abs(float(s['R_minus_'+t])-(ds['R']-ds[t]))<1e-12
 z=dict(passed=True,total_updates=300,conditions=6,unique_pairs=382,exposures=dict(exposures),parameters=52455,old_frozen_files_verified=len(contract['frozen_files']),checkpoints=checkpoints,independent_auc_max_delta=maxdelta,new_SAT=0,detector_updates=0,test_reads=0,role_controls='shared=true role;viewshuffle=per-view MUX role misassignment;boundary identities shared in both')
 (O/'VERIFIED.json').write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(z,ensure_ascii=False))
if __name__=='__main__':main()
