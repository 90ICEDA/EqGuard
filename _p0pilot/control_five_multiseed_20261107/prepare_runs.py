"""Derive seed1/2 copies from completed seed42;preserve all parent artifacts."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/control_five_seed42_20261107'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
assert read(OLD/'VERIFIED.json')['passed']
parents={str((OLD/n).relative_to(R)):h for n,h in read(OLD/'OUTPUT_MANIFEST.json').items()}
for p,h in parents.items():assert sha(R/p)==h,p
records=[]
for seed in [1,2]:
 out=R/f'_p0pilot/control_five_seed{seed}_20261107';out.mkdir(exist_ok=True)
 for name in ['run.py','analyze.py','verify.py']:
  src=(OLD/name).read_text(encoding='utf-8');text=src
  if name=='run.py':
   changes={'seed42':f'seed{seed}','seed=42':f'seed={seed}','init_s42.pt':f'init_s{seed}.pt','T.seed(42)':f'T.seed({seed})','T.seed(42+step)':f'T.seed({seed}+step)','loader.step(dm,arm,step)':f'loader.step(dm,arm,step,seed={seed})'}
   for a,b in changes.items():assert a in text,a;text=text.replace(a,b)
   # Protect completed seed42 in addition to inherited data/model/loader sources.
   anchor="protected=dict(loader.checked_files)"
   replacement=anchor+"\n for n,h in read(R/'_p0pilot/control_five_seed42_20261107/OUTPUT_MANIFEST.json').items():\n  p=R/'_p0pilot/control_five_seed42_20261107'/n;assert sha(p)==h,n;protected[str(p.relative_to(R))]=h"
   assert anchor in text;text=text.replace(anchor,replacement)
  elif name=='verify.py':
   for a,b in [('init_s42.pt',f'init_s{seed}.pt'),('seed=42',f'seed={seed}')]:assert a in text,a;text=text.replace(a,b)
  p=out/name
  if p.exists():assert p.read_text(encoding='utf-8')==text,p
  else:p.write_text(text,encoding='utf-8')
  records.append(dict(seed=seed,file=str(p.relative_to(R)),sha=sha(p),parent=str((OLD/name).relative_to(R)),parent_sha=sha(OLD/name)))
 warm='''from pathlib import Path
import json,time,traceback
import run as task
O=Path(__file__).resolve().parent
try:
 torch=task.torch;p=torch.nn.Parameter(torch.ones(32,device='cuda'));p.grad=torch.ones_like(p)
 norm=torch.nn.utils.clip_grad_norm_([p],1.);assert torch.isfinite(norm);torch.cuda.synchronize();del p,norm;torch.cuda.empty_cache()
 (O/'CUDA_WARMUP.json').write_text(json.dumps(dict(dummy_reduction_only=True,model_updates=0,optimizer_objects=0)),encoding='utf-8')
 print('TINY_REDUCTION_WARMUP_PASSED',flush=True);task.main()
except Exception:
 (O/f'failure_wrapper_{time.strftime("%H%M%S")}.log').write_text(traceback.format_exc(),encoding='utf-8');raise
'''
 p=out/'warm_run.py'
 if p.exists():assert p.read_text(encoding='utf-8')==warm
 else:p.write_text(warm,encoding='utf-8')
derivation=dict(seed42_reused=True,new_seeds=[1,2],arms=['G0','GB','GM','GBM','GAll'],updates_each=200,new_updates_planned=2000,factors_changed='model initialization seed andperstep RNGseed only;sampler identical;freshprocess perseed;smallCUDAprewarm,no optimizer',records=records,protected_seed42=parents)
(O/'DERIVATION.json').write_text(json.dumps(derivation,indent=2),encoding='utf-8');print('Prepared seed1/2 independent copies;seed42 unchanged.')
