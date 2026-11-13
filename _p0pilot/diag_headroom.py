"""Phase A3: headroom of N-B per view/recipe on test."""
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); B=R/'_p0pilot/control_boundary_v3_20261104'
OUT=R/'_p0pilot/lcone_phaseA_20261110'
c=json.loads((B/'input_contract.json').read_text(encoding='utf-8'))
vs={v['view']:v for v in c['shared_inputs']['trans_test']['views']}
z=np.load(R/'_p0pilot/four_group_contract_20261109/run_B_N/best_testpred.npz')
s,rows,y,t=z['scores'],z['rows'],z['y'],z['trusted']
per={}
for v,lay in vs.items():
    a,b=np.searchsorted(rows,[lay['start'],lay['stop']]); yy,tt,ss=y[a:b],t[a:b],s[a:b]
    if len(np.unique(yy[tt]))>1:
        per[v]=dict(ap=float(average_precision_score(yy[tt],ss[tt])),pos=int((yy[tt]==1).sum()),trusted=int(tt.sum()))
vals=np.array([x['ap'] for x in per.values()])
out=dict(views=len(vals),mean=float(vals.mean()),median=float(np.median(vals)),min=float(vals.min()),max=float(vals.max()),
         frac_gt_0_5=float((vals>0.5).mean()),frac_gt_0_8=float((vals>0.8).mean()),frac_lt_0_1=float((vals<0.1).mean()),
         per_view=per)
(OUT/'HEADROOM.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({k:out[k] for k in ('views','mean','median','min','max','frac_gt_0_5','frac_gt_0_8','frac_lt_0_1')},ensure_ascii=False))
