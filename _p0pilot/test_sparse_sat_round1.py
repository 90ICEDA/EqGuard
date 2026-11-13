"""Check query semantics, matched controls, and actual scale/clipping behavior."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from build_sparse_sat_round1 import facts,PT,OUT,NAMES


def main():
    assert facts(['proved','refuted','refuted','proved'])==[2,2,1,1]
    assert facts(['proved','proved','refuted','refuted'])==[0,1,0,0]
    assert facts(['refuted','refuted','refuted','refuted'])==[0,2,0,0]
    x=np.load(PT/'satrel_node_feats_sparseR1_real.npy',mmap_mode='r')
    p=np.load(PT/'satrel_node_feats_sparseR1_permuted.npy',mmap_mode='r')
    z=np.load(PT/'satrel_node_feats_sparseR1_zero.npy',mmap_mode='r')
    assert x.shape==p.shape==z.shape
    assert np.array_equal(x[:,[0,1,6,7]],p[:,[0,1,6,7]])
    assert np.array_equal(x[:,[0,1,6,7]],z[:,[0,1,6,7]])
    assert np.count_nonzero(z[:,2:6])==0
    assert np.all(x[x[:,-1]==0,:-1]==0)
    assert np.isfinite(x).all() and x.min()>=0 and x.max()<=1
    work=PT.parents[1]
    ids=json.loads((work/'data/for_train/metadata_trans.json').read_text(encoding='utf-8'))['file_ids']
    vid,_=pd.factorize(np.asarray(ids,dtype=object),sort=False)
    active=np.flatnonzero(x[:,6]>0)
    for v in np.unique(vid[active]):
        idx=active[vid[active]==v]
        a=np.asarray(x[idx,2:6]); b=np.asarray(p[idx,2:6])
        assert np.array_equal(a[np.lexsort(a.T[::-1])],b[np.lexsort(b.T[::-1])])
    # This mirrors the current legacy transform numerically; bounded is identity.
    mask=x[:,-1]>0
    rows=[]
    for j,name in enumerate(NAMES[:-1]):
        data=np.asarray(x[:,j])
        sub=data[mask].astype(np.float64)
        mu=float(sub.mean()); sd=max(float(sub.std(ddof=1)),1e-6)
        raw=(sub-mu)/sd
        bounded=np.clip(sub,-10,10)
        assert np.array_equal(sub,bounded)
        rows.append(dict(column=name,legacy_mu=mu,legacy_std=sd,
                         nonzero=int((sub!=0).sum()),legacy_clipped=int((np.abs(raw)>10).sum()),
                         bounded_clipped=0,legacy_unique_nonzero=len(np.unique(np.clip(raw[sub!=0],-10,10))),
                         bounded_unique_nonzero=len(np.unique(sub[sub!=0]))))
    pd.DataFrame(rows).to_csv(OUT/'normalization_comparison.csv',index=False,encoding='utf-8-sig')
    print(pd.DataFrame(rows).to_string(index=False))
    print('PASS: feasible proof pairs; no vacuous proofs; matched base/masks; per-view joint permutation; bounded values unchanged and no clipping')


if __name__=='__main__':
    main()
