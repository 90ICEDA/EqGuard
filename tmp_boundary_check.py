import re,json,numpy as np
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); F=R/'generate_trans/folds/hosts_bt31'; V='s15850t100__injzeta_d1_s42__ys_id'
mp=json.load(open(F/'mappings'/f'{V}.json',encoding='utf-8')); na=mp['node_alignment']; mapped={t for ts in na.values() for t in ts}
meta=json.load(open(F/'data/for_train/metadata_trans.json',encoding='utf-8')); f=np.array(meta['file_ids']); cm=json.load(open(F/'data/for_train/class_map_trans.json',encoding='utf-8')); names=[x.rstrip('\n') for x in open(F/'data/processed/node_names_trans.txt',encoding='utf-8')]
pos={names[i] for i in np.where(f==V)[0] if cm.get(str(i))==1}
parent={}
def find(x):
 parent.setdefault(x,x)
 while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
 return x
def union(a,b):
 a=find(a); b=find(b)
 if a!=b: parent[b]=a
lines=open(F/'trans'/f'{V}.v',encoding='utf-8',errors='replace').read().splitlines()
for ln in lines:
 m=re.match(r'\s*assign\s+([^=]+?)\s*=\s*([^;]+);',ln)
 if m: union(m.group(1).strip().lstrip('\\'),m.group(2).strip().lstrip('\\'))
gs={}
for ln in lines:
 m=re.match(r'\s*([A-Za-z0-9_]+)\s+(\\?\S+)\s*\((.*)\)\s*;',ln)
 if not m: continue
 inst=m.group(2).lstrip('\\'); ports={}
 for pm in re.finditer(r'\.([A-Za-z0-9_]+)\s*\(\s*([^)]*?)\s*\)',m.group(3)): ports[pm.group(1)]=find(pm.group(2).strip().lstrip('\\'))
 gs[inst]=ports
def out(p):
 for k in ('Q','Y','QN','CO'):
  if k in p: return p[k]
def is_mapped(g):
 on=out(gs[g]); return (g in mapped) or (on in mapped)
driver={}; loads={}
for g,p in gs.items():
 for port,net in p.items():
  if port in ('Q','Y','QN','CO'): driver.setdefault(net,g)
  else: loads.setdefault(net,[]).append(g)
adj={g:set() for g in gs}
for net,dg in driver.items():
 for lg in loads.get(net,[]):
  adj[dg].add(lg); adj[lg].add(dg)
region=set(pos); fr=list(pos)
while fr:
 g=fr.pop()
 for h in adj[g]:
  if h not in region and not is_mapped(h): region.add(h); fr.append(h)
print('seeds',len(pos),'region',len(region),'mapped',sum(is_mapped(g) for g in gs),'new',sum(not is_mapped(g) for g in gs))
print('region mapped?',sum(is_mapped(g) for g in region),'new in region',sum(not is_mapped(g) for g in region))
# new gates connected to region but not included? all included by BFS; print examples
print('new not region',sum((not is_mapped(g)) and g not in region for g in gs))
