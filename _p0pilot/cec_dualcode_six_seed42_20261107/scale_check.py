"""Saved-output scale-neutral diagnostics; no model execution."""
from pathlib import Path
import csv,json
import numpy as np
import analyze as A
O=Path(__file__).resolve().parent
def prob(d):
 p=np.exp(-d+np.min(d));return p/p.sum()
def js(p,q):
 m=(p+q)/2;return float(.5*(p@np.log(p/m)+q@np.log(q/m)))
def main():
 pp=A.read('EVALUATION_PANELS.json');gg=A.groups(pp);rows=[]
 for domain in ['train','val']:
  for ta in [9000,9002,9004,9006,9008,9010]:
   qq={}
   us=pp['train_frozen_pool'] if domain=='train' else pp['val_H3_primary']
   for arm in ['R0','R1']:
    for tag in [ta,ta+1]:
     ids,x=A.cached(domain,arm,tag);qq[arm,tag]=A.queries(us,ids,x)
   for group,uu in gg.items():
    if not group.startswith(domain+'_') or group in ['val_old_PO','val_new_PO']:continue
    keep={u['unit_id'] for u in uu};sums=dict(raw_R0=0.,raw_R1=0.,normalized_R0=0.,normalized_R1=0.,R1_matched_R0_scale=0.);nearzero=0
    for key in qq['R0',ta]:
     if key[0] not in keep:continue
     n=len(qq['R0',ta][key]['d']);w=1/(len(uu)*2*n);d={}
     for arm in ['R0','R1']:
      for tag in [ta,ta+1]:d[arm,tag]=qq[arm,tag][key]['d']
     for arm in ['R0','R1']:
      a,b=d[arm,ta],d[arm,ta+1];sums['raw_'+arm]+=w*js(prob(a),prob(b));sums['normalized_'+arm]+=w*js(prob((a-a.mean())/max(a.std(),1e-8)),prob((b-b.mean())/max(b.std(),1e-8)))
     fixed=[]
     for tag in [ta,ta+1]:
      a,b=d['R0',tag],d['R1',tag];nearzero+=int(b.std()<1e-8);fixed.append((b-b.mean())/max(b.std(),1e-8)*a.std())
     sums['R1_matched_R0_scale']+=w*js(prob(fixed[0]),prob(fixed[1]))
    rows.append(dict(domain=domain,group=group,tag_a=ta,tag_b=ta+1,nearzero_distance_spread=nearzero,**sums))
 A.table('SCALE_NEUTRAL_DIAGNOSTICS.csv',rows)
 # Direct metric cross-check vs independently verified original paired-map JS.
 with (O/'encoding_stability.csv').open(encoding='utf-8-sig',newline='') as f:old=list(csv.DictReader(f))
 for r in rows:
  for arm in ['R0','R1']:
   prior=next(x for x in old if x['group']==r['group'] and x['arm']==arm and int(x['tag_a'])==r['tag_a']);assert abs(float(prior['weighted_JS'])-r['raw_'+arm])<1e-12
 result={}
 for group in ['train_frozen_pool','val_H3_primary','val_MUX']:
  rr=[r for r in rows if r['group']==group];result[group]={k:float(np.mean([r[k] for r in rr])) for k in ['raw_R0','raw_R1','normalized_R0','normalized_R1','R1_matched_R0_scale']};result[group]['nearzero_spread']=sum(r['nearzero_distance_spread'] for r in rr)
 (O/'SCALE_NEUTRAL_SUMMARY.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
