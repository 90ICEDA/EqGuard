"""Strict labels: expand 1:N Trojan originals, shared->unknown, outside untrusted->unknown."""
import json,re,csv
from pathlib import Path
import numpy as np
ROOT=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FOLD=ROOT/'generate_trans/folds/hosts_bt31'; OUT=ROOT/'10.15'/'00_说明'
meta=json.load(open(FOLD/'data/for_train/metadata_trans.json',encoding='utf-8')); f=np.array(meta['file_ids']); cm=json.load(open(FOLD/'data/for_train/class_map_trans.json',encoding='utf-8')); names=[x.rstrip('\n') for x in open(FOLD/'data/processed/node_names_trans.txt',encoding='utf-8')]; trust=np.load(FOLD/'data/for_train/trust_trans.npy',mmap_mode='r')
def gates(p):
 d={}
 for ln in open(p,encoding='utf-8',errors='replace'):
  m=re.match(r'\s*([A-Za-z0-9_]+)\s+(\\?\S+)\s*\((.*)\)\s*;',ln)
  if m: d[m.group(2).lstrip('\\')]={}
 return d
def one(view):
 mp=json.load(open(FOLD/'mappings'/f'{view}.json',encoding='utf-8')); na=mp['node_alignment']; rev={}
 for o,ts in na.items():
  for t in ts: rev.setdefault(t,[]).append(o)
 idx=np.where(f==view)[0]; n2i={names[i]:i for i in idx}; tg=set()
 p=ROOT/'tmp_tmp.v'
 # gate names from mapping trans values, plus class positives
 pos_names=[names[i] for i in idx if cm.get(str(i))==1]
 gset=set(pos_names)
 for ts in na.values(): gset.update(ts)
 # all trans gates from netlist
 vpath=FOLD/'trans'/f'{view}.v'
 if vpath.exists(): gset.update(gates(vpath))
 tro_orig={o for o in na if 'trojan' in o.lower()}
 pos=set()
 for t in gset:
  os=set(rev.get(t,[]))
  if os & tro_orig and not (os - tro_orig): pos.add(t)
 unknown=set(); shared=set()
 for t in gset:
  os=set(rev.get(t,[]))
  if os & tro_orig and (os - tro_orig): shared.add(t)
 # map seed positives to unknown if unmapped
 for x in pos_names:
  if not rev.get(x): unknown.add(x)
 labels=[]; cnt={'1':0,'0':0,'unknown':0}
 for g in sorted(gset):
  if g in pos: lab=1
  elif g in shared or g in unknown: lab='unknown'
  else:
   i=n2i.get(g); lab=0 if (i is not None and bool(trust[i]) and cm.get(str(i),0)==0) else 'unknown'
  labels.append(dict(view=view,gate=g,label=lab)); cnt[str(lab)]+=1
 return dict(view=view,total_gates=len(gset),positive=cnt['1'],negative=cnt['0'],unknown=cnt['unknown'],shared=sorted(shared)[:20],labels=labels)
def main():
 rows=[]; all_labels=[]
 for p in sorted(OUT.glob('SAT_ALL_*.json')):
  v=p.stem[len('SAT_ALL_'):]; r=one(v); rows.append({k:r[k] for k in ('view','total_gates','positive','negative','unknown')}); all_labels.extend(r['labels']); print(v,r['positive'],r['negative'],r['unknown'],flush=True)
 with (OUT/'STRICT_LABEL_COUNTS_20261112.csv').open('w',encoding='utf-8-sig',newline='') as fh:
  w=csv.DictWriter(fh,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
 with (OUT/'STRICT_LABELS_20261112.csv').open('w',encoding='utf-8-sig',newline='') as fh:
  w=csv.DictWriter(fh,fieldnames=['view','gate','label']); w.writeheader(); w.writerows(all_labels)
 print('TOTAL',sum(r['positive'] for r in rows),sum(r['negative'] for r in rows),sum(r['unknown'] for r in rows))
if __name__=='__main__': main()
