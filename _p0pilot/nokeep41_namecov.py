import json,csv,sys,re,numpy as np
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); sys.path.insert(0,str(R/'_p0pilot/seed42_supervised_prep_20261109'))
import Signed_common as S
FT=R/'generate_trans/folds/hosts_bt31/data/for_train'; meta=json.load(open(FT/'metadata_trans.json',encoding='utf-8')); ids=meta['file_ids']; cm=json.load(open(FT/'class_map_trans.json',encoding='utf-8')); trust=np.load(FT/'trust_trans.npy')
m=json.load(open(R/'_p0pilot/nokeep41_20261111/NOKEEP41_MANIFEST.json',encoding='utf-8')); base=R/'generate_trans/nokeep41_20261111/jobs'
def norm(s):
 s=str(s).lstrip('\\')
 s=re.sub(r'^g_+','',s)
 s=re.sub(r'__\d+$','',s)
 s=re.sub(r'_\d+$','',s)
 s=re.sub(r'__+','_',s)
 return s
rows=[]
for v in m['views']:
 view=v['view']; orig=R/f'generate_trans/folds/hosts_bt31/trans/{view}.v'; tgt=base/v['base']/'conv'/v['host']/f"{v['base']}__keepnone__ys_{v['recipe']}.v"
 idx=[i for i,x in enumerate(ids) if x==view]; go=S.raw_network(orig,S.lib_pins); gt=S.raw_network(tgt,S.lib_pins); oc=list(go['pins']); tc=list(gt['pins'])
 if len(idx)!=len(oc): rows.append(dict(view=view,cells=len(tc),mapped=0,unknown=len(tc),pos=0,origpos=0,exact=0,prov=0,norm=0,note='mismatch')); continue
 y=np.array([int(cm[str(i)]) for i in idx],np.int8); tr=trust[idx].astype(bool)
 smap={c:i for i,c in enumerate(oc)}; nmap={}
 for i,c in enumerate(oc): nmap.setdefault(norm(c),[]).append(i)
 mapj=tgt.with_suffix('.map.json'); inst=json.load(open(mapj,encoding='utf-8')).get('inst_prov',{}) if mapj.exists() else {}
 ty=np.zeros(len(tc),np.int8); tt=np.zeros(len(tc),bool); status=np.empty(len(tc),object); status[:]='unknown'
 for j,c in enumerate(tc):
  i=smap.get(c); how='exact'
  if i is None:
   sn=inst.get(c); i=smap.get(sn) if sn is not None else None; how='prov'
  if i is None:
   cand=nmap.get(norm(c),[]); i=cand[0] if len(cand)==1 else None; how='norm'
  if i is None: continue
  ty[j]=y[i]; tt[j]=tr[i]; status[j]=how
 pos=int(((ty==1)&tt).sum()); neg=int(((ty==0)&tt).sum()); unk=int((status=='unknown').sum())
 rows.append(dict(view=view,cells=len(tc),mapped=len(tc)-unk,unknown=unk,pos=pos,neg=neg,origpos=int(((y==1)&tr).sum()),exact=int((status=='exact').sum()),prov=int((status=='prov').sum()),norm=int((status=='norm').sum())))
with open(R/'_p0pilot/nokeep41_20261111/NAME_CANDIDATE_COVERAGE.csv','w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r})); w.writeheader(); w.writerows(rows)
print(dict(cells=sum(r['cells'] for r in rows),mapped=sum(r['mapped'] for r in rows),unknown=sum(r['unknown'] for r in rows),pos=sum(r['pos'] for r in rows),origpos=sum(r['origpos'] for r in rows),exact=sum(r['exact'] for r in rows),prov=sum(r['prov'] for r in rows),norm=sum(r['norm'] for r in rows)))
