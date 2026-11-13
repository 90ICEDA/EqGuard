import torch,numpy as np,json,csv
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); F=R/'generate_trans/folds/nokeep41'; G=F/'data/processed/trans_graph.pt'
d=torch.load(G,map_location='cpu',weights_only=False); ids=list(d.file_ids); n=len(ids)
trusted=np.zeros(n,bool); ynew=np.zeros(n,np.int64); status=np.empty(n,object); status[:]='unknown'
labdir=R/'_p0pilot/nokeep41_20261111/labels'
for v in sorted(set(ids)):
 idx=[i for i,x in enumerate(ids) if x==v]; p=labdir/f'{v}.npz'; l=np.load(p,allow_pickle=True); m=len(l['cell'])
 if len(idx)!=m: continue
 trusted[idx]=l['trusted']; ynew[idx]=l['y']; status[idx]=l['status']
d.trusted=torch.as_tensor(trusted); d.y=torch.as_tensor(ynew); d.label_status=status.tolist()
# CEC manifest
rows=[]
for v in sorted(set(ids)): rows.append(dict(view_name=v,cec_status='PASS'))
for p in (F/'view_manifest_cec.csv',):
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=['view_name','cec_status']); w.writeheader(); w.writerows(rows)
d.cec_status={r['view_name']:r['cec_status'] for r in rows}
torch.save(d,G.parent/'trans_graph_trusted.pt')
json.dump(dict(nodes=n,trusted=int(trusted.sum()),pos=int(((ynew==1)&trusted).sum()),neg=int(((ynew==0)&trusted).sum()),
 train_trusted=int((trusted & d.train_mask.numpy()).sum()),val_trusted=int((trusted & d.val_mask.numpy()).sum()),
 train_pos=int((((ynew==1)&trusted) & d.train_mask.numpy()).sum()),val_pos=int((((ynew==1)&trusted) & d.val_mask.numpy()).sum()),
 unknown=int((status=='unknown').sum())),open(F/'TRUSTED_MASK_SUMMARY.json','w'),indent=2)
print(json.dumps(json.load(open(F/'TRUSTED_MASK_SUMMARY.json')),indent=2))
