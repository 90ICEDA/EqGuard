"""All views: labels by orig Trojan gate -> trans mapping (1:N all), outside=0."""
import re,json,csv
from pathlib import Path
ROOT=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FOLD=ROOT/'generate_trans/folds/hosts_bt31'; OUT=ROOT/'10.15'/'00_说明'
def gates(p):
 d={}
 for ln in open(p,encoding='utf-8',errors='replace'):
  m=re.match(r'\s*([A-Za-z0-9_]+)\s+(\\?\S+)\s*\((.*)\)\s*;',ln)
  if not m: continue
  inst=m.group(2).lstrip('\\'); ports={}
  for pm in re.finditer(r'\.([A-Za-z0-9_]+)\s*\(\s*([^)]*?)\s*\)',m.group(3)): ports[pm.group(1)]=pm.group(2).strip().lstrip('\\')
  d[inst]=ports
 return d
def outnets(p):
 return {p[k] for k in ('Q','Y','QN','CO') if k in p}
def one(view):
 mp=json.load(open(FOLD/'mappings'/f'{view}.json',encoding='utf-8')); na=mp.get('node_alignment',{})
 tro={o:ts for o,ts in na.items() if 'trojan' in o.lower()}
 gs=gates(FOLD/'trans'/f'{view}.v')
 outmap={}
 for g,p in gs.items():
  for n in outnets(p): outmap.setdefault(n,g)
 vals=set()
 for ts in tro.values(): vals.update(ts)
 region=set()
 for v in vals:
  if v in gs: region.add(v)
  elif v in outmap: region.add(outmap[v])
 labels=[dict(view=view,gate=g,label=1 if g in region else 0) for g in sorted(gs)]
 return dict(view=view,total_gates=len(gs),trojan_orig=len(tro),positive=len(region),negative=len(gs)-len(region),labels=labels)
def main():
 rows=[]; labels=[]
 for p in sorted(OUT.glob('SAT_ALL_*.json')):
  v=p.stem[len('SAT_ALL_'):]
  r=one(v); rows.append({k:r[k] for k in ('view','total_gates','trojan_orig','positive','negative')}); labels.extend(r['labels']); print(v,r['trojan_orig'],r['positive'],r['negative'],flush=True)
 with (OUT/'ORIG_BOUNDARY_COUNTS_20261112.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
 with (OUT/'ORIG_BOUNDARY_LABELS_20261112.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['view','gate','label']); w.writeheader(); w.writerows(labels)
 print('TOTAL',sum(r['positive'] for r in rows),sum(r['negative'] for r in rows))
if __name__=='__main__': main()
