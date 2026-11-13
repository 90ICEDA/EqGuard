import json,csv,sys,re,hashlib,numpy as np
from pathlib import Path
from collections import defaultdict
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); sys.path.insert(0,str(R/'_p0pilot/seed42_supervised_prep_20261109'))
import Signed_common as S
FT=R/'generate_trans/folds/hosts_bt31/data/for_train'; meta=json.load(open(FT/'metadata_trans.json',encoding='utf-8')); ids=meta['file_ids']; cm=json.load(open(FT/'class_map_trans.json',encoding='utf-8')); trust=np.load(FT/'trust_trans.npy')
m=json.load(open(R/'_p0pilot/nokeep41_20261111/NOKEEP41_MANIFEST.json',encoding='utf-8')); base=R/'generate_trans/nokeep41_20261111/jobs'
def norm(s):
 s=str(s).lstrip('\\'); s=re.sub(r'^g_+','',s); s=re.sub(r'__\d+$','',s); s=re.sub(r'_\d+$','',s); s=re.sub(r'__+','_',s); return s
def sigs(g, rounds=3):
 pins=g['pins']; cells=list(pins); idx={c:i for i,c in enumerate(cells)}; adj=defaultdict(set); net2=defaultdict(list)
 for c,(typ,con) in pins.items():
  for p,n in con:
   for x in str(n).replace('\\','').split(','):
    if x: net2[x].append(c)
 for xs in net2.values():
  for a in xs:
   for b in xs:
    if a!=b: adj[a].add(b)
 col={c:hashlib.sha1((str(pins[c][0])+'|'+str(len(adj[c]))).encode()).hexdigest()[:16] for c in cells}
 for _ in range(rounds):
  col={c:hashlib.sha1((col[c]+'|'+'|'.join(sorted(col[n] for n in adj[c]))).encode()).hexdigest()[:16] for c in cells}
 return cells,col
rows=[]
for v in m['views']:
 view=v['view']; orig=R/f'generate_trans/folds/hosts_bt31/trans/{view}.v'; tgt=base/v['base']/'conv'/v['host']/f"{v['base']}__keepnone__ys_{v['recipe']}.v"
 idx=[i for i,x in enumerate(ids) if x==view]; go=S.raw_network(orig,S.lib_pins); gt=S.raw_network(tgt,S.lib_pins); oc=list(go['pins']); tc=list(gt['pins'])
 if len(idx)!=len(oc): rows.append(dict(view=view,cells=len(tc),mapped=0,pos=0,origpos=0,exact=0,norm=0,wl=0,unknown=len(tc))); continue
 y=np.array([int(cm[str(i)]) for i in idx],np.int8); tr=trust[idx].astype(bool)
 smap={c:i for i,c in enumerate(oc)}; nmap=defaultdict(list)
 for i,c in enumerate(oc): nmap[norm(c)].append(i)
 _,scol=sigs(go); _,tcol=sigs(gt); sm=defaultdict(list); tm=defaultdict(list)
 for c in oc: sm[(go['pins'][c][0],scol[c])].append(c)
 for c in tc: tm[(gt['pins'][c][0],tcol[c])].append(c)
 ty=np.zeros(len(tc),np.int8); tt=np.zeros(len(tc),bool); how=np.empty(len(tc),object); how[:]='unknown'
 for j,c in enumerate(tc):
  i=smap.get(c); k='exact'
  if i is None:
   cand=nmap.get(norm(c),[]); i=cand[0] if len(cand)==1 else None; k='norm'
  if i is None:
   cand=sm.get((gt['pins'][c][0],tcol[c]),[]); i=smap.get(cand[0]) if len(cand)==1 else None; k='wl'
  if i is None: continue
  ty[j]=y[i]; tt[j]=tr[i]; how[j]=k
 rows.append(dict(view=view,cells=len(tc),mapped=int((how!='unknown').sum()),pos=int(((ty==1)&tt).sum()),origpos=int(((y==1)&tr).sum()),exact=int((how=='exact').sum()),norm=int((how=='norm').sum()),wl=int((how=='wl').sum()),unknown=int((how=='unknown').sum())))
 print(view,rows[-1],flush=True)
with open(R/'_p0pilot/nokeep41_20261111/WL_CANDIDATE_COVERAGE.csv','w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(dict(cells=sum(r['cells'] for r in rows),mapped=sum(r['mapped'] for r in rows),pos=sum(r['pos'] for r in rows),origpos=sum(r['origpos'] for r in rows),exact=sum(r['exact'] for r in rows),norm=sum(r['norm'] for r in rows),wl=sum(r['wl'] for r in rows)))
