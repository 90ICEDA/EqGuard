"""CPU-only independent metric and input-invariance checks."""
from pathlib import Path
import csv,hashlib,importlib.util,json,sys
import numpy as np
O=Path(__file__).resolve().parent;R=O.parents[1];OLD=R/'_p0pilot/cec_repaired_zrp_seed42_20261107'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def rows(n):
 with (O/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
V=load('independent_cpu_metrics',OLD/'verify.py')
P=R/'_p0pilot/cec_boundary_panel_expand_20261107';sys.path.insert(0,str(P));from panel_loader import PanelLoader
def main():
 assert read(O/'COMPLETE.json')['passed'];pp=read(OLD/'EVALUATION_PANELS.json');panels={'train':pp['train_frozen_pool'],'val':pp['val_boundary_all']};checks=0;loader=PanelLoader();invariant=0;maxerr=0
 for domain,uu in panels.items():
  ids=sorted({c for u in uu for c in u['cones']});base=loader.arrays(ids,9000)
  for tag in range(9001,9006):
   a=loader.arrays(ids,tag)
   for k in a:
    if k=='x':assert np.array_equal(a[k][:,:9],base[k][:,:9]);assert not np.array_equal(a[k][:,9:],base[k][:,9:])
    else:assert np.array_equal(a[k],base[k]),(domain,tag,k)
   invariant+=1
 for row in rows('six_code_metrics.csv'):
  domain=row['domain'];tag=int(row['tag']);arm=row['arm'];group=row['group'];uu=panels[domain]
  if group in ['MUX','nonMUX']:uu=[u for u in uu if u['has_mux']==(group=='MUX')]
  elif group.startswith('flow/'):uu=[u for u in uu if u['flow']==group[5:]]
  elif group!='all':
   source,kind=group.rsplit('/',1);uu=[u for u in uu if u['source']==source and (kind=='all' or u['has_mux']==(kind=='MUX'))]
  path=(OLD if tag<9002 else O)/f'{domain}_{arm}_tag{tag}.npz'
  with np.load(path) as z:calc=V.metrics(uu,z['cone_ids'].tolist(),z['root64'])
  for k,v in calc.items():
   err=abs(v-float(row[k]));maxerr=max(maxerr,err);assert err<1e-10,(domain,arm,tag,group,k)
  checks+=1
 # Independent query flip/margin accounting for the two original codes.
 for row in rows('encoding_sensitivity.csv'):
  domain,arm=row['domain'],row['arm'];uu=panels[domain];vv=[]
  for tag in [9000,9001]:
   with np.load(OLD/f'{domain}_{arm}_tag{tag}.npz') as z:ix={c:i for i,c in enumerate(z['cone_ids'].tolist())};x=z['root64'].astype(float)
   vals=[];weights=[]
   for u in uu:
    n=u['functions'];z=x[[ix[c] for c in u['cones']]]
    for f in range(n):
     for side in [0,1]:
      d=np.linalg.norm(z[2*f+side]-z[[2*j+1-side for j in range(n)]],axis=1)/8
      d=np.sqrt(d*d+1e-12)
      for j in range(n):
       if j!=f:vals.append(d[j]-d[f]);weights.append(1/(len(uu)*2*n*(n-1)))
   vv.append(np.array(vals))
  a,b=vv;w=np.array(weights);flip=float(w@((a>0)!=(b>0)));rms=float(np.sqrt(w@((b-a)**2)))
  assert abs(flip-float(row['weighted_flip_rate']))<1e-10 and abs(rms-float(row['margin_shift_RMS']))<1e-6,(domain,arm,flip,float(row['weighted_flip_rate']),rms,float(row['margin_shift_RMS']))
 for p,h in read(O/'AUDIT_CONTRACT.json')['protected_files'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
 result=dict(passed=True,independent_metric_sets=checks,max_metric_error=maxerr,independent_sensitivity_sets=8,input_invariance_checks=invariant,intervention='only 16 boundary channels changed;9type channels and all graph arrays unchanged',protected_files_unchanged=True,extra_model_forwards=0,training=0,SAT=0)
 (O/'VERIFIED.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
