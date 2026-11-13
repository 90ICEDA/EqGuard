import json,csv,sys,numpy as np
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); sys.path.insert(0,str(R/'_p0pilot/seed42_supervised_prep_20261109'))
import Signed_common as S
FT=R/'generate_trans/folds/hosts_bt31/data/for_train'; meta=json.load(open(FT/'metadata_trans.json',encoding='utf-8')); ids=meta['file_ids']; cm=json.load(open(FT/'class_map_trans.json',encoding='utf-8')); trust=np.load(FT/'trust_trans.npy')
m=json.load(open(R/'_p0pilot/nokeep41_20261111/NOKEEP41_MANIFEST.json',encoding='utf-8')); outd=R/'_p0pilot/nokeep41_20261111/labels'; outd.mkdir(exist_ok=True); base=R/'generate_trans/nokeep41_20261111/jobs'
summ=[]
for v in m['views']:
 view=v['view']; orig=R/f'generate_trans/folds/hosts_bt31/trans/{view}.v'; tgt=base/v['base']/'conv'/v['host']/f"{v['base']}__keepnone__ys_{v['recipe']}.v"
 idx=[i for i,x in enumerate(ids) if x==view]
 go=S.raw_network(orig,S.lib_pins); gt=S.raw_network(tgt,S.lib_pins)
 oc=list(go['pins']); tc=list(gt['pins'])
 if len(idx)!=len(oc):
  ty=np.zeros(len(tc),np.int8); tt=np.zeros(len(tc),bool); status=np.empty(len(tc),object); status[:]='unknown'
  np.savez_compressed(outd/f'{view}.npz',cell=np.array(tc),y=ty,trusted=tt,status=status,source_view=view)
  summ.append(dict(view=view,cells=len(tc),mapped=0,unknown=len(tc),pos=0,neg=0,trusted_pos_orig=0,note=f'node_cell_mismatch:{len(idx)}vs{len(oc)}'))
  print(view,'MISMATCH',len(idx),len(oc),flush=True); continue
 y=np.array([int(cm[str(i)]) for i in idx],np.int8); tr=trust[idx].astype(bool)
 smap={c:i for i,c in enumerate(oc)}
 mapj=tgt.with_suffix('.map.json'); inst=json.load(open(mapj,encoding='utf-8')).get('inst_prov',{}) if mapj.exists() else {}
 ty=np.zeros(len(tc),np.int8); tt=np.zeros(len(tc),bool); status=np.empty(len(tc),object); status[:]='unknown'
 for j,c in enumerate(tc):
  i=smap.get(c)
  if i is not None:
   ty[j]=y[i]; tt[j]=tr[i]; status[j]='mapped_exact'; continue
  sn=inst.get(c)
  if sn is None: continue
  i=smap.get(sn)
  if i is None and sn.startswith('\\'): i=smap.get(sn[1:])
  if i is None: continue
  ty[j]=y[i]; tt[j]=tr[i]; status[j]='mapped_prov'
 np.savez_compressed(outd/f'{view}.npz',cell=np.array(tc),y=ty,trusted=tt,status=status,source_view=view)
 pos=int(((ty==1)&tt).sum()); neg=int(((ty==0)&tt).sum()); unk=int((status=='unknown').sum())
 summ.append(dict(view=view,cells=len(tc),mapped=int((status!='unknown').sum()),unknown=unk,pos=pos,neg=neg,trusted_pos_orig=int(((y==1)&tr).sum())))
 print(view,'mapped',summ[-1]['mapped'],'/',len(tc),'pos',pos,'origpos',summ[-1]['trusted_pos_orig'],'unk',unk,flush=True)
with open(R/'_p0pilot/nokeep41_20261111/LABEL_TRANSFER_SUMMARY.csv','w',newline='',encoding='utf-8') as f:
 fields=sorted({k for s in summ for k in s})
 w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(summ)
json.dump(dict(total=len(summ),cells=sum(s['cells'] for s in summ),mapped=sum(s['mapped'] for s in summ),unknown=sum(s['unknown'] for s in summ),
 pos=sum(s['pos'] for s in summ),neg=sum(s['neg'] for s in summ),orig_pos=sum(s['trusted_pos_orig'] for s in summ)),
 open(R/'_p0pilot/nokeep41_20261111/LABEL_TRANSFER.json','w'),indent=2)
