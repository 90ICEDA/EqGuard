"""Build balanced weak-negative cone set (f=0.5) size-matched to v2c positives."""
import os, sys, json, csv
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'): os.environ[k]='1'
os.environ['P2B_MASK']='old'
from pathlib import Path
import numpy as np, hashlib
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
PREP=R/'_p0pilot/seed42_supervised_prep_20261109'; V2=R/'_p0pilot/lcone_v2c_20261110'
OUT=R/'_p0pilot/lcone_weak03_20261110'; OUT.mkdir(exist_ok=True)
g=np.load(FG/'group_B.npz'); y=g['y']; tr=g['trusted']; ph=g['physical']; rows=g['rows']; loc={r:i for i,r in enumerate(rows.tolist())}
# positives from v2c all
pos_src=np.load(V2/'cones_v2c_all_D.npz'); pos_idx=np.where(pos_src['label']==1)[0]
pos=[]
for i in pos_idx:
    mem=pos_src['rows'][pos_src['ptr'][i]:pos_src['ptr'][i+1]]
    pos.append(dict(mem=np.array(mem,np.int64),view=str(pos_src['view'][i]),label=1))
# weak negatives from cache
weak=[]
with (PREP/'CONE_CACHE_V2.csv').open(encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
        if r['split']!='train' or r['kind']!='D' or int(r['n_phys'])<2: continue
        mem=[]
        for x in r['phys_rows'].split('|'):
            if not x: continue
            i=loc.get(int(x))
            if i is not None: mem.append(i)
        if len(mem)<2: continue
        t=tr[mem]; yy=y[mem]
        npos=int(((yy==1)&t).sum()); nneg=int(((yy==0)&t).sum())
        if npos==0 and nneg>=1 and nneg/len(mem)>=0.3:
            weak.append(dict(mem=np.array(mem,np.int64),view=r['view'],label=0))
def cap(mem, seed):
    if len(mem)<=20: return mem
    h=hashlib.sha256((str(seed)+':'+','.join(map(str,mem[:5]))).encode()).hexdigest()
    rng=np.random.default_rng(int(h[:8],16)); return np.sort(rng.choice(mem,20,replace=False))
for p in pos: p['mem']=cap(p['mem'],len(p['mem']))
for w in weak: w['mem']=cap(w['mem'],len(w['mem']))
# size match positives
by_size={}
for w in weak: by_size.setdefault(len(w['mem']),[]).append(w)
rng=np.random.default_rng(42); neg=[]
for p in pos:
    s=len(p['mem']); cand=by_size.get(s,[])
    if cand: neg.append(cand.pop(rng.integers(len(cand))))
# fill remaining from nearest sizes if needed
for p in pos:
    if len(neg)>=len(pos): break
    s=len(p['mem']); best=None
    for d in range(1,20):
        for ss in (s-d,s+d):
            if by_size.get(ss): best=ss; break
        if best: break
    if best: neg.append(by_size[best].pop())
# pad/truncate
neg=neg[:len(pos)]
print('pos',len(pos),'neg',len(neg),'pos size',round(np.mean([len(p['mem']) for p in pos]),2),'neg size',round(np.mean([len(n['mem']) for n in neg]),2))
sel=pos+neg
flat=[]; ptr=[0]; lab=[]; view=[]
for x in sel:
    flat.extend(x['mem'].tolist()); ptr.append(len(flat)); lab.append(x['label']); view.append(x['view'])
np.savez_compressed(OUT/'cones_weak03_D.npz',rows=np.array(flat,np.int64),ptr=np.array(ptr,np.int64),label=np.array(lab,np.int8),view=np.array(view))
json.dump(dict(pos=len(pos),neg=len(neg),pos_mean=float(np.mean([len(p['mem']) for p in pos])),neg_mean=float(np.mean([len(n['mem']) for n in neg]))),open(OUT/'WEAK03_BUILD.json','w'))
