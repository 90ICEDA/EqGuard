from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent;OLD=R/'_p0pilot/control_five_cause_20261107'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert json.loads((OLD/'VERIFIED.json').read_text(encoding='utf-8'))['passed']
records=[]
for seed in [1,2]:
 folder=R/f'_p0pilot/control_five_cause_seed{seed}_20261107';folder.mkdir(exist_ok=True)
 for name in ['run.py','verify.py','context_cases.py']:
  src=(OLD/name).read_text(encoding='utf-8');previous=src.replace("control_five_seed42_20261107",f'control_five_seed{seed}_20261107');target=previous;assert target!=src
  if name=='run.py':target=target.replace("OLD/'PUBLISHED.json'","R/'_p0pilot/control_five_multiseed_20261107/PUBLISHED.json'")
  p=folder/name
  if p.exists() and p.read_text(encoding='utf-8')!=target:
   assert p.read_text(encoding='utf-8')==previous;p.with_suffix(p.suffix+'.initial').write_bytes(p.read_bytes());p.write_text(target,encoding='utf-8')
  elif not p.exists():p.write_text(target,encoding='utf-8')
  records.append(dict(seed=seed,parent=str((OLD/name).relative_to(R)),parent_sha=sha(OLD/name),file=str(p.relative_to(R)),sha=sha(p)))
(O/'DERIVATION.json').write_text(json.dumps(dict(seed42_audit_reused=True,new_analysis_seeds=[1,2],records=records,training=0,SAT=0),indent=2),encoding='utf-8');print('Prepared cached-only seed1/2 audits;oldseed42 audit reused.')
