"""Build N+control baseline supervision: replace some common negatives with train control negatives."""
import numpy as np, json, hashlib
from pathlib import Path
R=Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train'); FG=R/'_p0pilot/four_group_contract_20261109'
OUT=R/'_p0pilot/lcone_trainctl_20261110'
g=np.load(FG/'group_B.npz'); y=g['y']; tr=g['trusted']; ph=g['physical']; rows=g['rows']; loc={r:i for i,r in enumerate(rows.tolist())}
c=json.load(open(R/'_p0pilot/control_boundary_v3_20261104/input_contract.json',encoding='utf-8'))
ctl=np.zeros(len(y),bool)
for v in c['shared_inputs']['trans_train']['views']:
    if 'ctl' in v['view']:
        a,b=v['start'],v['stop']; ids=rows[(rows>=a)&(rows<b)]; ctl[[loc[int(x)] for x in ids]]=True
tr2=np.load(R/'_p0pilot/label_expand_20261031/trust_trans_v2_trainctl.npy')[rows]
pool=np.where(ctl&ph&(y==0))[0]
print('control neg pool',len(pool))
sup=np.load(FG/'sup_B.npz',allow_pickle=True); idx=sup['idx']; sh=[]
new=[]
for step in range(len(idx)):
    ids=np.asarray(idx[step],dtype=np.int64).copy()
    negpos=np.where(y[ids]==0)[0]
    # replace up to 2048 non-control negatives with control negatives
    cand=negpos[~ctl[ids[negpos]]]
    k=min(2048,len(cand),len(pool))
    rng=np.random.default_rng(42+step)
    sel=cand[rng.choice(len(cand),k,replace=False)]
    repl=pool[rng.choice(len(pool),k,replace=False)]
    ids[sel]=repl
    new.append(ids)
    sh.append(hashlib.sha256(ids.tobytes()).hexdigest())
np.savez_compressed(OUT/'sup_B_ctl.npz',idx=np.array(new,dtype=object),stepsha=np.array(sh))
print('steps',len(new),'avg ctl frac',round(float(np.mean([ctl[x].mean() for x in new])),4),'len',len(new[0]))
