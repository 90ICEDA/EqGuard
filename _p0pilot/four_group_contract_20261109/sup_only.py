"""Sampling-only rebuild (no cones/precheck): common 8192 + extra 144 from H minus common, quota 502."""
import hashlib, json, sys
from pathlib import Path
import numpy as np
R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
L = R / '_p0pilot/control_loader_po_20261105'
sys.path.insert(0, str(L))
from supervision_loader import FiveGroupLoader

def sha(a): return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
loader = FiveGroupLoader(); c = json.loads((B/'input_contract.json').read_text(encoding='utf-8'))
vs = {v['view']: v for v in c['shared_inputs']['trans_train']['views']}
A = np.load(OUT/'group_A.npz'); Bg = np.load(OUT/'group_B.npz')
pools = loader.pools['trans']; common_ids = np.asarray(pools['common_negative'], np.int64); h_ids = np.asarray(pools['H'], np.int64)
def pool(ids, o2n, g):
    x = o2n[ids]; x = x[x>=0]; return x[(g['y'][x]==0)&g['trusted'][x]&g['physical'][x]]
cA,pA,hA = pool(common_ids,A['old2new'],A), None, pool(h_ids,A['old2new'],A)
cB,hB = pool(common_ids,Bg['old2new'],Bg), pool(h_ids,Bg['old2new'],Bg)
print('cap',len(cA),len(hA),len(cB),len(hB)); sys.stdout.flush()
def srcpos(g, keep):
    d={}
    for v in keep:
        lay=vs[v]; a,b=lay['start'],lay['stop']; s=v.split('__ys_')[0]
        loc=np.where((g['y']==1)&g['trusted']&g['physical'])[0]
        loc=loc[(g['rows'][loc]>=a)&(g['rows'][loc]<b)]
        d.setdefault(s,[]).extend(loc.tolist())
    return d
ka={v for v in vs if v.split('__')[-1] in ('ys_abc','ys_id','ys_opt')}
kb={v for v in vs if v.split('__')[-1] in ('ys_abc','ys_id','ys_opt','ys_aig','ys_nand')}
pa,pb=srcpos(A,ka),srcpos(Bg,kb); srcs=sorted(set(pa)&set(pb))
quota={s:min(len(pa[s]),len(pb[s])) for s in srcs}
def pick(d,s,n):
    arr=np.array(d[s],np.int64); rr=np.random.default_rng(int(hashlib.sha256(s.encode()).hexdigest()[:8],16)); return rr.permutation(arr)[:n]
posA=np.concatenate([pick(pa,s,quota[s]) for s in srcs]).astype(np.int64)
posB=np.concatenate([pick(pb,s,quota[s]) for s in srcs]).astype(np.int64)
print('pos',len(posA),len(posB)); sys.stdout.flush()
stepsA=[];stepsB=[]
for step in range(200):
    r=np.random.default_rng(42+step); cc=r.choice(cA,8192,replace=False); ee=r.choice(np.setdiff1d(hA,cc),144,replace=False)
    r2=np.random.default_rng(42+step); cc2=r2.choice(cB,8192,replace=False); ee2=r2.choice(np.setdiff1d(hB,cc2),144,replace=False)
    ia=np.concatenate([posA,cc,ee]).astype(np.int64); ib=np.concatenate([posB,cc2,ee2]).astype(np.int64)
    assert len(np.unique(ia))==len(ia)==len(posA)+8336 and len(np.unique(ib))==len(ib)==len(posB)+8336
    stepsA.append(ia);stepsB.append(ib)
    if step%50==0: print('step',step); sys.stdout.flush()
np.savez_compressed(OUT/'sup_A.npz', idx=np.array(stepsA), pos=posA, common=cA, h=hA, srcs=np.array(srcs), quota=np.array([quota[s] for s in srcs]), stepsha=np.array([sha(x) for x in stepsA]))
np.savez_compressed(OUT/'sup_B.npz', idx=np.array(stepsB), pos=posB, common=cB, h=hB, srcs=np.array(srcs), quota=np.array([quota[s] for s in srcs]), stepsha=np.array([sha(x) for x in stepsB]))
json.dump(dict(cap=[len(cA),len(hA),len(cB),len(hB)],pos=[len(posA),len(posB)],steps=200),open(OUT/'SUP_OK.json','w'))
print('SUP_DONE')
