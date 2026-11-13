import json, numpy as np
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
old=json.load(open(R/'_p0pilot/lcone_v2c_20261110/LCONE_FINAL_OFFLINE.json',encoding='utf-8'))['metrics']
rows=[]
for s in (42,1,2,3,4):
 if s in (42,1,2):
  n=old[f'N_{s}']
 else:
  n=json.load(open(R/f'_p0pilot/four_group_contract_20261109/run_B_N_s{s}/best_eval.json',encoding='utf-8'))
 r=json.load(open(R/f'_p0pilot/lcone_relaxed_20261111/run_relaxed_s{s}_lam0.01/best_eval.json',encoding='utf-8'))
 print(s,'N',round(n['base_ap'],4),round(n['add_ap'],4),'R',round(r['base_ap'],4),round(r['add_ap'],4),'d',round(r['base_ap']-n['base_ap'],4),round(r['add_ap']-n['add_ap'],4))
 rows.append((n['base_ap'],n['add_ap'],r['base_ap'],r['add_ap']))
a=np.array(rows); db=a[:,2]-a[:,0]; da=a[:,3]-a[:,1]
for name,x in [('base',db),('add',da)]:
 print(name,'mean',round(float(x.mean()),4),'sd',round(float(x.std(ddof=1)),4),'positive',int((x>0).sum()),'ci',np.round([x.mean()-2.776*x.std(ddof=1)/np.sqrt(5), x.mean()+2.776*x.std(ddof=1)/np.sqrt(5)],4))
