"""Region closure + outside audit for one view, write all-gate labels."""
import re,json,csv
from pathlib import Path
import numpy as np
ROOT=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FOLD=ROOT/'generate_trans/folds/hosts_bt31'
VIEW='s15850t100__injzeta_d1_s42__ys_id'; TRANS=FOLD/'trans'/f'{VIEW}.v'
def gates(p):
 d={}
 for ln in open(p,encoding='utf-8',errors='replace'):
  m=re.match(r'\s*([A-Za-z0-9_]+)\s+(\\?\S+)\s*\((.*)\)\s*;',ln)
  if not m: continue
  inst=m.group(2).lstrip('\\'); ports={}
  for pm in re.finditer(r'\.([A-Za-z0-9_]+)\s*\(\s*([^)]*?)\s*\)',m.group(3)): ports[pm.group(1)]=pm.group(2).strip().lstrip('\\')
  d[inst]=ports
 return d
def main():
 meta=json.load(open(FOLD/'data/for_train/metadata_trans.json',encoding='utf-8')); f=np.array(meta['file_ids']); cm=json.load(open(FOLD/'data/for_train/class_map_trans.json',encoding='utf-8')); names=[x.rstrip('\n') for x in open(FOLD/'data/processed/node_names_trans.txt',encoding='utf-8')]
 pos=[names[i] for i in np.where(f==VIEW)[0] if cm.get(str(i))==1]
 sat=json.load(open(ROOT/'10.15'/'00_说明'/'SAT_POS_EACH_FINAL_20261112.json',encoding='utf-8')); st={r['trans']:r['status'] for r in sat['results']}
 gs=gates(TRANS); allg=set(gs); tro=set(pos)
 print('gates',len(allg),'positive',len(tro),'outside',len(allg-tro),flush=True)
 driver={}; loads={}
 for g,ports in gs.items():
  for p,net in ports.items():
   if p in ('Q','Y','QN','CO'): driver.setdefault(net,g)
   else: loads.setdefault(net,[]).append((g,p))
 binp=set(); bout=set(); internal=0
 for g in tro:
  for p,net in gs[g].items():
   if p in ('Q','Y','QN','CO'):
    for h,_ in loads.get(net,[]):
     if h in tro: internal+=1
     else: bout.add(net)
   else:
    d=driver.get(net)
    if d is not None and d not in tro: binp.add(net)
 # all positive proved
 missing=[g for g in tro if st.get(g)!='success!']
 # label all
 rows=[]
 for g in sorted(allg): rows.append(dict(view=VIEW,gate=g,label=1 if g in tro else 0,region='trojan' if g in tro else 'normal'))
 out=ROOT/'10.15'/'00_说明'; (out/'REGION_CLOSURE_s15850_injzeta_20261112.json').write_text(json.dumps(dict(view=VIEW,total_gates=len(allg),trojan_gates=len(tro),outside_gates=len(allg-tro),trojan_missing_sat=missing,boundary_input_nets=sorted(binp),boundary_output_nets=sorted(bout),internal_edges=internal),ensure_ascii=False,indent=2),encoding='utf-8')
 with (out/'NODE_LABELS_s15850_injzeta_20261112.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['view','gate','label','region']); w.writeheader(); w.writerows(rows)
 print(json.dumps(dict(total=len(allg),trojan=len(tro),outside=len(allg-tro),missing=missing,boundary_in=len(binp),boundary_out=len(bout),internal=internal),ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__': main()
