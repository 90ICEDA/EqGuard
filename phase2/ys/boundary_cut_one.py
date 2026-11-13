"""Boundary cut for one view: seeds=Trojan gates, region expands through new/unmapped gates."""
import re,json,csv,sys
from pathlib import Path
import numpy as np
ROOT=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FOLD=ROOT/'generate_trans/folds/hosts_bt31'
VIEW=sys.argv[1] if len(sys.argv)>1 else 's15850t100__injzeta_d1_s42__ys_id'
def gates(p):
 d={}
 for ln in open(p,encoding='utf-8',errors='replace'):
  m=re.match(r'\s*([A-Za-z0-9_]+)\s+(\\?\S+)\s*\((.*)\)\s*;',ln)
  if not m: continue
  inst=m.group(2).lstrip('\\'); ports={}
  for pm in re.finditer(r'\.([A-Za-z0-9_]+)\s*\(\s*([^)]*?)\s*\)',m.group(3)): ports[pm.group(1)]=pm.group(2).strip().lstrip('\\')
  d[inst]=ports
 return d
def outnet(p):
 for k in ('Q','Y','QN','CO'):
  if k in p: return p[k]
mp=json.load(open(FOLD/'mappings'/f'{VIEW}.json',encoding='utf-8')); na=mp['node_alignment']; trans=FOLD/'trans'/f'{VIEW}.v'; gs=gates(trans)
meta=json.load(open(FOLD/'data/for_train/metadata_trans.json',encoding='utf-8')); f=np.array(meta['file_ids']); cm=json.load(open(FOLD/'data/for_train/class_map_trans.json',encoding='utf-8')); names=[x.rstrip('\n') for x in open(FOLD/'data/processed/node_names_trans.txt',encoding='utf-8')]
pos=[names[i] for i in np.where(f==VIEW)[0] if cm.get(str(i))==1]
mapped_nets={t for ts in na.values() for t in ts}
# gate output net mapped?
def is_mapped(g):
 on=outnet(gs[g]); return bool((g in mapped_nets) or (on and on in mapped_nets))
# graph
driver={}; loads={}
for g,p in gs.items():
 for port,net in p.items():
  if port in ('Q','Y','QN','CO'): driver.setdefault(net,g)
  else: loads.setdefault(net,[]).append(g)
adj={g:set() for g in gs}
for net,dg in driver.items():
 for lg in loads.get(net,[]):
  if dg in adj: adj[dg].add(lg)
  if lg in adj: adj[lg].add(dg)
seeds=set(pos); region=set(seeds); frontier=list(seeds)
while frontier:
 g=frontier.pop()
 for h in adj.get(g,()):
  if h not in region and not is_mapped(h):
   region.add(h); frontier.append(h)
outside=set(gs)-region
# boundary
bout=set(); binp=set()
for g in region:
 on=outnet(gs[g])
 if on:
  for h in loads.get(on,[]):
   if h not in region: bout.add(on)
 for p,net in gs[g].items():
  if p not in ('Q','Y','QN','CO'):
   d=driver.get(net)
   if d and d not in region: binp.add(net)
rows=[]
for g in sorted(gs):
 lab=1 if g in region else (0 if is_mapped(g) else 'unknown')
 rows.append(dict(view=VIEW,gate=g,label=lab,region='trojan' if g in region else ('host' if is_mapped(g) else 'new_unknown')))
print(json.dumps(dict(view=VIEW,seeds=len(seeds),region=len(region),outside=len(outside),mapped=sum(is_mapped(g) for g in gs),new=sum(not is_mapped(g) for g in gs),boundary_in=len(binp),boundary_out=len(bout),labels={str(x):sum(1 for r in rows if r['label']==x) for x in (1,0,'unknown')}),ensure_ascii=False,indent=2))
out=ROOT/'10.15'/'00_璇存槑'; (out/f'BOUNDARY_{VIEW}.json').write_text(json.dumps(dict(view=VIEW,region=sorted(region),boundary_in=sorted(binp),boundary_out=sorted(bout),labels=rows),ensure_ascii=False,indent=2),encoding='utf-8')
