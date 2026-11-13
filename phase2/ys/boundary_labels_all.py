"""All views: alias-resolved boundary closure around Trojan seeds; outside=0."""
import re,json,csv
from pathlib import Path
import numpy as np
ROOT=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FOLD=ROOT/'generate_trans/folds/hosts_bt31'; OUT=ROOT/'10.15'/'00_说明'
meta=json.load(open(FOLD/'data/for_train/metadata_trans.json',encoding='utf-8')); f=np.array(meta['file_ids']); cm=json.load(open(FOLD/'data/for_train/class_map_trans.json',encoding='utf-8')); names=[x.rstrip('\n') for x in open(FOLD/'data/processed/node_names_trans.txt',encoding='utf-8')]
def one(view):
 mp=json.load(open(FOLD/'mappings'/f'{view}.json',encoding='utf-8')); mapped={t for ts in mp['node_alignment'].values() for t in ts}
 pos={names[i] for i in np.where(f==view)[0] if cm.get(str(i))==1}
 parent={}
 def find(x):
  parent.setdefault(x,x)
  while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
  return x
 def union(a,b):
  a=find(a); b=find(b)
  if a!=b: parent[b]=a
 lines=open(FOLD/'trans'/f'{view}.v',encoding='utf-8',errors='replace').read().splitlines()
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
  for lg in loads.get(net,[]): adj[dg].add(lg); adj[lg].add(dg)
 region=set(pos); fr=list(pos)
 while fr:
  g=fr.pop()
  for h in adj.get(g,()):
   if h not in region and not is_mapped(h): region.add(h); fr.append(h)
 labels=[dict(view=view,gate=g,label=1 if g in region else 0) for g in sorted(gs)]
 return dict(view=view,total=len(gs),positive=len(region),negative=len(gs)-len(region),seeds=len(pos),mapped=sum(is_mapped(g) for g in gs),labels=labels)
def main():
 rows=[]; labels=[]
 for p in sorted(OUT.glob('SAT_ALL_*.json')):
  v=p.stem[len('SAT_ALL_'):]; r=one(v); rows.append({k:r[k] for k in ('view','total','positive','negative','seeds','mapped')}); labels.extend(r['labels']); print(v,r['positive'],r['negative'],flush=True)
 with (OUT/'BOUNDARY_COUNTS_20261112.csv').open('w',encoding='utf-8-sig',newline='') as fh:
  w=csv.DictWriter(fh,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
 with (OUT/'BOUNDARY_LABELS_20261112.csv').open('w',encoding='utf-8-sig',newline='') as fh:
  w=csv.DictWriter(fh,fieldnames=['view','gate','label']); w.writeheader(); w.writerows(labels)
 print('TOTAL',sum(r['positive'] for r in rows),sum(r['negative'] for r in rows))
if __name__=='__main__': main()
