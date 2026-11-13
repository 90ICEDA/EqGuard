"""Quantify alternative negative-cone definitions under current group_B trust coverage."""
import csv, json
from pathlib import Path
import numpy as np
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
PREP=R/'_p0pilot/seed42_supervised_prep_20261109'; OUT=R/'_p0pilot/lcone_phaseA_20261110'
g=np.load(FG/'group_B.npz'); y=g['y']; tr=g['trusted']; ph=g['physical']; o2n=g['old2new']; rows=g['rows']
# map original row -> local
rows_list=rows.tolist(); loc={r:i for i,r in enumerate(rows_list)}
cones=[]
with (PREP/'CONE_CACHE_V2.csv').open(encoding='utf-8-sig',newline='') as f:
    for r in csv.DictReader(f):
        if r['split']!='train' or r['kind']!='D' or int(r['label'])<0 or int(r['n_phys'])<2: continue
        mem=[]
        for x in r['phys_rows'].split('|'):
            if not x: continue
            i=loc.get(int(x))
            if i is not None: mem.append(i)
        if len(mem)<2: continue
        t=tr[mem]; yy=y[mem]; p=ph[mem]
        if not p.all(): continue
        nt=int(t.sum()); npos=int(((yy==1)&t).sum()); nneg=int(((yy==0)&t).sum())
        cones.append(dict(size=len(mem),nt=nt,npos=npos,nneg=nneg,untrusted=len(mem)-nt))
def stats(sel):
    ss=np.array([c['size'] for c in sel]); return dict(n=len(sel),mean=float(ss.mean()) if len(ss) else None,median=float(np.median(ss)) if len(ss) else None,
        ge5=int((ss>=5).sum()),ge10=int((ss>=10).sum()),max=int(ss.max()) if len(ss) else None)
cur=[c for c in cones if c['nt']==c['size'] and c['npos']==0 and c['nneg']==c['size']]
alt={}
for f in (0.3,0.5):
    alt[str(f)]=[c for c in cones if c['npos']==0 and c['nneg']>=1 and c['nneg']/c['size']>=f]
pos=[c for c in cones if c['npos']>0]
out=dict(cones=len(cones),current_negative=stats(cur),positive=stats(pos),
         alternative_negative={k:stats(v) for k,v in alt.items()},
         note='alt negative: no trusted positive, at least one trusted negative, trusted-negative fraction >= f; unknown members allowed')
OUT.mkdir(exist_ok=True); (OUT/'NEG_DEF_OPTIONS.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
