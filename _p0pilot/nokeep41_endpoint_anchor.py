import json,csv,sys,re,numpy as np
from pathlib import Path
from collections import defaultdict
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); sys.path.insert(0,str(R/'_p0pilot/seed42_supervised_prep_20261109'))
import Signed_common as S
FT=R/'generate_trans/folds/hosts_bt31/data/for_train'; meta=json.load(open(FT/'metadata_trans.json',encoding='utf-8')); ids=meta['file_ids']; cm=json.load(open(FT/'class_map_trans.json',encoding='utf-8')); trust=np.load(FT/'trust_trans.npy')
m=json.load(open(R/'_p0pilot/nokeep41_20261111/NOKEEP41_MANIFEST.json',encoding='utf-8')); base=R/'generate_trans/nokeep41_20261111/jobs'
def norm(s):
 s=str(s).lstrip('\\'); s=re.sub(r'^g_+','',s); s=re.sub(r'__\d+$','',s); s=re.sub(r'_\d+$','',s); s=re.sub(r'__+','_',s); return s
def graph(g):
 pins=g['pins']; drv={}; fan=defaultdict(set); cell_in={}; cell_out={}
 for c,(typ,con) in pins.items():
  for p,n in con:
   if p in ('Y','Q','QN','Q_N'): drv[str(n)]=c; cell_out.setdefault(c,set()).add(str(n))
   else: fan[str(n)].add(c); cell_in.setdefault(c,set()).add(str(n))
 return drv,fan,cell_in,cell_out
def endpoints(g):
 pins=g['pins']; ds=[]; pos=[]
 for c,(typ,con) in pins.items():
  if 'DFF' in typ.upper():
   d=dict(con); ds.append(('D',c,d.get('D')))
 # PO: use raw ports; from cone builder? parse module ports
 for p in g.get('po',[]): pos.append(('PO',p,p))
 return ds,pos
def fanin_cells(net,drv,cell_in,seen=None):
 seen=set() if seen is None else seen; out=set(); stack=[net]
 while stack:
  n=stack.pop(); c=drv.get(n)
  if c is None or c in seen: continue
  seen.add(c); out.add(c)
  for nn in cell_in.get(c,()): stack.append(nn)
 return out
rows=[]
for v in m['views']:
 view=v['view']; orig=R/f'generate_trans/folds/hosts_bt31/trans/{view}.v'; tgt=base/v['base']/'conv'/v['host']/f"{v['base']}__keepnone__ys_{v['recipe']}.v"
 idx=[i for i,x in enumerate(ids) if x==view]; go=S.raw_network(orig,S.lib_pins); gt=S.raw_network(tgt,S.lib_pins); oc=list(go['pins']); tc=list(gt['pins'])
 if len(idx)!=len(oc): rows.append(dict(view=view,cells=len(tc),unique=0,ambig=0,none=len(tc),pos=0,origpos=0)); continue
 y=np.array([int(cm[str(i)]) for i in idx],np.int8); tr=trust[idx].astype(bool); smap={c:i for i,c in enumerate(oc)}
 sdrv,sfan,sin,sout=graph(go); tdrv,tfan,tin,tout=graph(gt)
 sds,spos=endpoints(go); tds,tpos=endpoints(gt)
 # anchor ids for all cells
 sanc=defaultdict(set); tanc=defaultdict(set); s_ep={}; t_ep={}
 for k,c,n in sds:
  eid=f'D:{c}'; s_ep[eid]=c
  for x in fanin_cells(n,sdrv,sin): sanc[x].add(eid)
 for k,c,n in spos:
  eid=f'PO:{n}'; s_ep[eid]=n
  for x in fanin_cells(n,sdrv,sin): sanc[x].add(eid)
 # target endpoint ids map by same name
 t_ep={}
 for k,c,n in tds: t_ep[f'D:{c}']=c
 for k,c,n in tpos: t_ep[f'PO:{n}']=n
 for eid,c in t_ep.items():
  if eid not in s_ep: continue
  mem=fanin_cells(dict(tds and {}).get('x') if False else None,tdrv,tin) if False else None
 # recompute target fanin per target endpoint
 for k,c,n in tds+[(a,b,c) for a,b,c in tpos]:
  eid=f'D:{c}' if k=='D' else f'PO:{n}'
  if eid not in s_ep: continue
  for x in fanin_cells(n,tdrv,tin): tanc[x].add(eid)
 # match by anchor set + gate type
 sm=defaultdict(list); tm=defaultdict(list)
 for c in oc: sm[(str(go['pins'][c][0]),frozenset(sanc[c]))].append(c)
 for c in tc: tm[(str(gt['pins'][c][0]),frozenset(tanc[c]))].append(c)
 unique=ambig=none=0; ty=np.zeros(len(tc),np.int8); tt=np.zeros(len(tc),bool)
 for j,c in enumerate(tc):
  cand=sm.get((str(gt['pins'][c][0]),frozenset(tanc[c])),[])
  if len(cand)==1: unique+=1; i=smap[cand[0]]; ty[j]=y[i]; tt[j]=tr[i]
  elif len(cand)>1: ambig+=1
  else: none+=1
 rows.append(dict(view=view,cells=len(tc),unique=unique,ambig=ambig,none=none,pos=int(((ty==1)&tt).sum()),origpos=int(((y==1)&tr).sum())))
 print(view,rows[-1],flush=True)
with open(R/'_p0pilot/nokeep41_20261111/ENDPOINT_ANCHOR_COVERAGE.csv','w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(dict(cells=sum(r['cells'] for r in rows),unique=sum(r['unique'] for r in rows),ambig=sum(r['ambig'] for r in rows),none=sum(r['none'] for r in rows),pos=sum(r['pos'] for r in rows),origpos=sum(r['origpos'] for r in rows)))
