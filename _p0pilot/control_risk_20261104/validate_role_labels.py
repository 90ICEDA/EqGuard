from pathlib import Path
import json,csv,collections,numpy as np
R=Path(__file__).resolve().parents[2];O=Path(__file__).resolve().parent
rows=list(csv.DictReader((O/'trans_role_descendant_pairs.csv').open(encoding='utf-8-sig')))
c=json.loads((R/'_p0pilot/round32_20261029/input_contract.json').read_text(encoding='utf-8'));vs={};ctx={}
for sp in ['train','val','test']:
 q=c['shared_inputs']['trans_'+sp];p=R/q['folder'];ctx[sp]={k:np.load(p/(k+'.npy'),mmap_mode='r') for k in ['y','trusted','physical']}
 for v in q['views']:vs[v['view']]=dict(v,split=sp)
need=collections.defaultdict(set)
for x in rows:
 for side in ['control','trojan']:need[x[side+'_view']].update(filter(None,x[side+'_targets'].split('|')))
ranges=sorted((vs[n]['old_start'],vs[n]['old_stop'],n) for n in need);i=0;indices={}
with (R/'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').open(encoding='utf-8') as f:
 for g,line in enumerate(f):
  while i<len(ranges) and g>=ranges[i][1]:i+=1
  if i>=len(ranges):break
  lo,hi,n=ranges[i];name=line.strip().lstrip('\\')
  if g>=lo and name in need[n]:indices[(n,name)]=vs[n]['start']+g-lo
for x in rows:
 a=ctx[x['split']];good=True
 for side,label in [('control',0),('trojan',1)]:
  names=list(filter(None,x[side+'_targets'].split('|')));ids=[indices[(x[side+'_view'],n)] for n in names if (x[side+'_view'],n) in indices]
  ok=bool(names) and len(ids)==len(names) and bool(a['physical'][ids].all()) and bool(a['trusted'][ids].all()) and bool((a['y'][ids]==label).all())
  x[side+'_old_trusted_role_ok']=ok;good=good and ok
 x['nodewise_training_candidate']=good and x['shared_with_host']=='False'
with (O/'trans_role_descendant_pairs_labelchecked.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
out=[]
for sp in ['train','val','test']:
 a=[x for x in rows if x['split']==sp and x['nodewise_training_candidate']]
 nodes={(x['control_view'],n) for x in a for n in x['control_targets'].split('|')}
 out.append(dict(split=sp,labelchecked_role_occurrences=len(a),unique_control_target_nodes=len(nodes),unique_control_views=len({x['control_view'] for x in a}),unique_control_sources=len({x['control_source'] for x in a})))
(O/'role_label_counts.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(out)
