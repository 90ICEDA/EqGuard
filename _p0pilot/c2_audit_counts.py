"""C2 design audit: source-level held-out recipe feasibility (no training)."""
import json,csv,collections
from pathlib import Path
import numpy as np
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'; PREP=R/'_p0pilot/seed42_supervised_prep_20261109'
B=R/'_p0pilot/control_boundary_v3_20261104'; c=json.load(open(B/'input_contract.json',encoding='utf-8'))
g=np.load(FG/'group_B.npz'); gy=g['y']; gtr=g['trusted']; gph=g['physical']; grows=g['rows']; loc={r:i for i,r in enumerate(grows.tolist())}
arr={s:{n:np.load(B/f'inputs/trans_{s}'/(n+'.npy')) for n in ('y','trusted','physical')} for s in ('val','test')}
def views(split): return [v for v in c['shared_inputs'][f'trans_{split}']['views'] if 'ctl' not in v['view']]
tv={s:{v['view']:v for v in views(s)} for s in ('train','val','test')}
cones=[]
with (PREP/'CONE_CACHE_V2.csv').open(encoding='utf-8-sig',newline='') as f:
 for r in csv.DictReader(f):
  if r['split']!='train' or r['kind']!='D' or int(r['n_phys'])<2 or 'ctl' in r['view']: continue
  mem=[]
  for x in r['phys_rows'].split('|'):
   if not x: continue
   i=loc.get(int(x))
   if i is not None and gph[i]: mem.append(i)
  if len(mem)>=2: cones.append((r['view'],np.array(mem)))
def local_ids(vs): return {loc[int(i)] for v in vs for i in range(v['start'],v['stop']) if int(i) in loc}
out={}
for h in ('ys_abc','ys_aig','ys_nand'):
 train=[v for n,v in tv['train'].items() if n.split('__')[-1]!=h]
 held=[v for n,v in tv['train'].items() if n.split('__')[-1]==h]
 val=[v for n,v in tv['val'].items() if n.split('__')[-1]!=h]
 test=[v for n,v in tv['test'].items() if n.split('__')[-1]==h]
 tri=local_ids(train); hei=local_ids(held)
 def ids_global(vs): return {i for v in vs for i in range(v['start'],v['stop'])}
 vai=ids_global(val); tei=ids_global(test); vph=arr['val']['physical']; vtr=arr['val']['trusted']; vy=arr['val']['y']; tph=arr['test']['physical']; ttr=arr['test']['trusted']; ty=arr['test']['y']
 def count(split,ids):
  if split=='train': y=gy; t=gtr; ph=gph
  else: y=arr[split]['y']; t=arr[split]['trusted']; ph=arr[split]['physical']
  nodes=len(ids); phys=sum(1 for i in ids if ph[i]); pos=sum(1 for i in ids if ph[i] and y[i]==1 and t[i])
  return nodes,phys,pos
 negtot={i for i in tri if gph[i] and gy[i]==0}
 posc=[]; negc=[]
 for vn,mem in cones:
  if vn.split('__')[-1]==h: continue
  t=gtr[mem]; yy=gy[mem]
  if ((yy==1)&t).any(): posc.append(mem)
  elif int(((yy==0)&t).sum())>=1 and ((yy==0)&t).mean()>=0.5: negc.append(mem)
 u=set()
 for mem in negc: u.update(mem.tolist())
 sup=np.load(FG/'sup_B.npz',allow_pickle=True)['idx']; sh=[np.asarray(x,dtype=np.int64) for x in sup]
 held_mask=np.zeros(len(gy),bool); held_mask[list(hei)]=True
 pos_mask=np.zeros(len(gy),bool); pos_mask[list(tri)]=True; pos_mask &= (gph & (gy==1) & gtr)
 hcount=[int(held_mask[x].sum()) for x in sh]
 pcount=[int(pos_mask[x].sum()) for x in sh]
 nt,np_,npos=count('train',tri); vt,vp,vpos=count('val',vai); tt,tp,tpos=count('test',tei)
 out[h]=dict(train_views=len(train),heldout_train_views=len(held),val_views=len(val),test_views=len(test),
  train_nodes=len(tri),train_phys=np_,train_pos=npos,heldout_nodes=len(hei),val_nodes=len(vai),val_phys=vp,val_pos=vpos,test_nodes=len(tei),test_phys=tp,test_pos=tpos,
  pos_cones=len(posc),relaxed_neg_cones=len(negc),relaxed_neg_coverage=round(len(u&negtot)/max(1,len(negtot)),4),
  sup_avg_heldout_nodes=round(float(np.mean(hcount)),1),sup_avg_train_pos=round(float(np.mean(pcount)),1),
  train_view_overlap_val=len({v['view'] for v in train}&{v['view'] for v in val}),train_view_overlap_test=len({v['view'] for v in train}&{v['view'] for v in test}),heldout_view_overlap_test=len({v['view'] for v in held}&{v['view'] for v in test}))
(R/'_p0pilot/c2_heldout_20261111').mkdir(exist_ok=True)
json.dump(out,open(R/'_p0pilot/c2_heldout_20261111/C2_AUDIT_COUNTS.json','w'),indent=2)
print(json.dumps(out,ensure_ascii=False)[:2500])
