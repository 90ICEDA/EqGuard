"""Relaxed test negative cones + score/localization analysis (injected views only)."""
import csv,json,collections
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score,roc_auc_score
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; OLD=R/'_p0pilot/seed42_nc_ablation_20261109'
z0=np.load(FG/'run_B_N/best_testpred.npz'); rows=z0['rows']; y=z0['y']; tr=z0['trusted']; ph=z0['physical']; loc={r:i for i,r in enumerate(rows.tolist())}
cones=[]; counts=collections.Counter()
with (OLD/'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig',newline='') as f:
 for r in csv.DictReader(f):
  if r['split']!='test' or 'ctl' in r['view'] or r['kind'] not in ('D','PO') or int(r['n_phys'])<2: continue
  mem=[]
  for x in r['phys_rows'].split('|'):
   if not x: continue
   i=loc.get(int(x))
   if i is not None and ph[i]: mem.append(i)
  if len(mem)<2: continue
  mem=np.array(mem); t=tr[mem]; yy=y[mem]
  npos=int(((yy==1)&t).sum()); nneg=int(((yy==0)&t).sum())
  if npos>0: lab=1
  elif nneg>=1 and nneg/len(mem)>=0.5: lab=0
  else: continue
  cones.append(dict(kind=r['kind'],view=r['view'],lab=lab,mem=mem,noisy=int(((yy==1)&~t).sum())))
pos=[x for x in cones if x['lab']==1]; neg=[x for x in cones if x['lab']==0]
# test negative totals injected
inj_neg=set(np.where(ph&(y==0))[0].tolist()) # includes control; filter by cone views only later
# use all injected view ranges
test_ctrl=set()
c=json.load(open((R/'_p0pilot/control_boundary_v3_20261104/input_contract.json'),encoding='utf-8'))
for v in c['shared_inputs']['trans_test']['views']:
 if 'ctl' in v['view']:
  test_ctrl.update(range(v['start'],v['stop']))
inj_neg={i for i in inj_neg if i not in test_ctrl}
def cov(sel):
 u=set()
 for x in sel: u.update(x['mem'].tolist())
 return len(u&inj_neg),round(len(u&inj_neg)/len(inj_neg),4)
strict=[x for x in neg if x['noisy']==0 and all(tr[x['mem']]&(y[x['mem']]==0))]
print('injected neg nodes',len(inj_neg),'pos cones',len(pos),'relaxed neg',len(neg),'strict neg',len(strict),'noisy',sum(1 for x in neg if x['noisy']>0))
print('strict cov',cov(strict),'relaxed cov',cov(neg))
models={'NB':z0['scores'],'relaxed':np.load(R/'_p0pilot/lcone_relaxed_20261111/run_relaxed_s1_lam0.01/best_testpred.npz')['scores']}
fs={'max':lambda z:z.max(),'second':lambda z:np.sort(z)[-2],'top2mean':lambda z:np.sort(z)[-2:].mean(),'top3mean':lambda z:np.sort(z)[-3:].mean(),
    'mean':lambda z:z.mean(),'median':lambda z:np.median(z),'q75':lambda z:np.quantile(z,.75),'q25':lambda z:np.quantile(z,.25),
    'max_times_top2':lambda z:z.max()*np.sort(z)[-2:].mean(),'top2sum':lambda z:np.sort(z)[-2:].sum()}
out={'counts':dict(pos=len(pos),relaxed_neg=len(neg),strict_neg=len(strict),injected_neg=len(inj_neg),strict_cov=cov(strict),relaxed_cov=cov(neg),neg_mean=float(np.mean([len(x['mem']) for x in neg])),pos_mean=float(np.mean([len(x['mem']) for x in pos])),noisy=sum(1 for x in neg if x['noisy']>0))}
for name,s in models.items():
 out[name]={}
 for kind in ('D','PO'):
  pp=[x for x in pos if x['kind']==kind]; nn=[x for x in neg if x['kind']==kind]
  arr=pp+nn; lab=np.array([x['lab'] for x in arr]);
  out[name][kind]={}
  for fn,func in fs.items():
   vals=np.array([float(func(s[x['mem']])) for x in arr])
   out[name][kind][fn]=round(float(average_precision_score(lab,vals)),4)
  # localization on positive cones
  top1=[]; top3p=[]; top3r=[]; pct=[]
  for x in pp:
   sc=s[x['mem']]; order=np.argsort(-sc); ispos=(y[x['mem']]==1)&tr[x['mem']]; P=int(ispos.sum()); n=len(sc)
   if P==0: continue
   ranks=np.empty(n,int); ranks[order]=np.arange(n); pr=ranks[ispos]
   top1.append(float(ispos[order[0]])); top3p.append(float(ispos[order[:min(3,n)]].sum()/min(3,n))); top3r.append(float(ispos[order[:min(3,n)]].sum()/P)); pct.append(float(pr.mean()/(n-1)))
  out[name][kind]['loc']=dict(top1=round(float(np.mean(top1)),4),top3_prec=round(float(np.mean(top3p)),4),top3_recall=round(float(np.mean(top3r)),4),mean_pct=round(float(np.mean(pct)),4))
json.dump(out,open(r'_p0pilot/lcone_relaxed_20261111/TEST_RELAX_SCORES.json','w'),indent=2)
print(json.dumps(out,ensure_ascii=False)[:3000])
