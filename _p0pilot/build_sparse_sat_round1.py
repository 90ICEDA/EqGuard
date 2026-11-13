"""Strict conditional SAT features from existing, query-aligned logs. No SAT search.

Only cone/DFF queries are used. A forced value needs a proved/refuted pair,
which proves the condition is feasible and excludes vacuous proofs. Only exact
source views or byte-identical files receive evidence; no name-only transport.
These are two-tested-pattern facts, not full-cut sufficiency or reset reachability.
"""
from __future__ import annotations
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'generate_trans/folds/hosts_bt31'
PT=WORK/'data/processed'
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/sparse_sat_round1'
NAMES=['reach_po_log','reach_dff_log','forced_pattern_fraction','feasible_pattern_fraction',
       'tested_joint_change_ratio','forced_one_fraction','evaluated_case','covered']


def log_statuses(path):
    result=[]
    with path.open(encoding='utf-8',errors='replace') as f:
        for line in f:
            if 'Executing SAT pass ' in line or 'Executing SAT pass (' in line:
                result.append('unknown')
            elif result:
                if 'no model found: SUCCESS' in line:
                    result[-1]='proved'
                elif 'model found: FAIL' in line:
                    result[-1]='refuted'
    return result


def facts(q):
    forced=[]
    feasible=0
    for a,b in [(q[0],q[1]),(q[2],q[3])]:
        forced.append(1 if (a,b)==('proved','refuted') else 0 if (a,b)==('refuted','proved') else None)
        feasible+=int('refuted' in (a,b))
    return [sum(v is not None for v in forced),feasible,
            int(all(v is not None for v in forced) and forced[0]!=forced[1]),
            sum(v==1 for v in forced if v is not None)]


def main():
    t=time.perf_counter()
    OUT.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(ROOT/'_p0pilot/functional_relations_agnostic.csv',encoding='utf-8-sig').fillna('')
    meta=json.loads((WORK/'data/for_train/metadata_trans.json').read_text(encoding='utf-8'))
    vid,views=pd.factorize(np.asarray(meta['file_ids'],dtype=object),sort=False)
    vid=vid.astype(np.int16)
    del meta
    n=len(vid)
    by_key=defaultdict(list)
    for view in views:
        parts=view.split('__')
        by_key[(parts[0],parts[1],parts[-1])].append(view)
    hashes={}
    def digest(path):
        key=str(path)
        if key not in hashes:
            hashes[key]=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        return hashes[key]
    # view -> cell -> accumulated sufficient statistics (cases, forced, feasible, change, ones)
    cells=defaultdict(lambda:defaultdict(lambda:np.zeros(5,np.int32)))
    ledger=[]
    evidence=[]
    for logpath,g in d.groupby('log',sort=False):
        complex_rows=g[g.kind.isin(['cone','dff_next'])]
        if complex_rows.empty:
            continue
        path=ROOT/logpath
        if not path.exists():
            ledger.append(dict(log=logpath,accepted=False,reason='missing_log'))
            continue
        actual=log_statuses(path)
        saved=g[['sat_q1','sat_q2','sat_q3','sat_q4']].to_numpy().reshape(-1).tolist()
        if actual!=saved:
            ledger.append(dict(log=logpath,accepted=False,reason='query_alignment_mismatch',actual=len(actual),saved=len(saved)))
            continue
        first=g.iloc[0]
        source=WORK/'trans'/str(first.design)
        parts=source.stem.split('__')
        eligible=[v for v in by_key.get((parts[0],parts[1],str(first.recipe)),[])
                  if digest(WORK/'trans'/f'{v}.v')==digest(source) and digest(source) is not None]
        raw=path.with_name(path.name.replace('.sat.log','.struct_raw.json'))
        if not raw.exists():
            ledger.append(dict(log=logpath,accepted=False,reason='missing_raw_json'))
            continue
        modules=json.loads(raw.read_text(encoding='utf-8'))['modules']
        mod=modules.get(str(first.top)) or next(iter(modules.values()))
        netbits={nm:info['bits'] for nm,info in mod['netnames'].items()}
        drivers=defaultdict(set)
        for cn,c in mod['cells'].items():
            directions=c.get('port_directions',{})
            for pin,bits in c['connections'].items():
                if directions.get(pin)=='output' or (not directions and pin in ('Y','Q','QN')):
                    for b in bits:
                        if isinstance(b,int):
                            drivers[b].add(cn)
        count=0
        for _,r in complex_rows.iterrows():
            q=[r[f'sat_q{i}'] for i in range(1,5)]
            if any(v not in ('proved','refuted') for v in q):
                continue
            target=netbits.get(str(r.target),[])
            driver=set().union(*(drivers.get(b,set()) for b in target if isinstance(b,int)))
            if len(target)!=1 or len(driver)!=1:
                continue
            attach=set(driver)
            if r.kind=='dff_next':
                attach.add(str(r.cell))
            vals=facts(q)
            for view in eligible:
                for cn in attach:
                    cells[view][cn.lstrip('\\')]+=np.asarray([1]+vals,dtype=np.int32)
            evidence.append(dict(source=source.name,target=r.target,kind=r.kind,driver=next(iter(driver)),
                                 eligible_views=';'.join(eligible),forced_patterns=vals[0],feasible_patterns=vals[1],
                                 tested_joint_change=vals[2],forced_ones=vals[3],log=logpath))
            count+=1
        ledger.append(dict(log=logpath,accepted=True,reason='aligned',queries=len(actual),
                           complex_rows=len(complex_rows),qualified_rows=count,eligible_views=len(eligible)))
    acc=np.zeros((n,5),np.int32)
    hit=0
    with (PT/'node_names_trans.txt').open(encoding='utf-8') as f:
        for i,line in enumerate(f):
            if i>=n:
                break
            row=cells.get(views[vid[i]],{}).get(line.strip().lstrip('\\'))
            if row is not None:
                acc[i]=row
                hit+=1
    inherited=np.load(PT/'satrel_node_feats_sat_p0clean4_core_reach.npy',mmap_mode='r')
    x=np.zeros((n,8),np.float32)
    x[:,:2]=inherited[:,:2]
    x[:,-1]=inherited[:,-1]
    count=np.maximum(acc[:,0],1)
    x[:,2]=acc[:,1]/(2*count)
    x[:,3]=acc[:,2]/(2*count)
    x[:,4]=acc[:,3]/count
    x[:,5]=acc[:,4]/np.maximum(acc[:,1],1)
    x[:,6]=acc[:,0]>0
    # The inherited mask is identical for all treatments; add qualified evidence
    # outside it, if any, to the shared mask, never erase validated evidence.
    added=int(((x[:,6]>0)&(x[:,-1]==0)).sum())
    x[:,-1]=np.maximum(x[:,-1],x[:,6])
    prefix='satrel_node_feats_sparseR1_'
    np.save(PT/(prefix+'real.npy'),x)
    perm=x.copy()
    rng=np.random.default_rng(20261025)
    active=np.flatnonzero(x[:,6]>0)
    for v in np.unique(vid[active]):
        idx=active[vid[active]==v]
        perm[idx,2:6]=x[rng.permutation(idx),2:6]
    np.save(PT/(prefix+'permuted.npy'),perm)
    zero=x.copy()
    zero[:,2:6]=0
    np.save(PT/(prefix+'zero.npy'),zero)
    assert np.isfinite(x).all() and x.min()>=0 and x.max()<=1
    assert np.array_equal(x[:,[0,1,6,7]],perm[:,[0,1,6,7]])
    assert np.array_equal(x[:,[0,1,6,7]],zero[:,[0,1,6,7]])
    import torch
    graph=torch.load(PT/'trans_graph.pt',map_location='cpu',weights_only=False,mmap=True)
    y=graph.y.numpy().reshape(-1)>0
    test=graph.test_mask.numpy().reshape(-1).astype(bool)
    coverage=[]
    for j,name in enumerate(NAMES):
        nz=x[:,j]!=0
        coverage.append(dict(column=name,nonzero=int(nz.sum()),positive_nonzero=int((nz&y).sum()),
                             test_nonzero=int((nz&test).sum()),test_positive_nonzero=int((nz&test&y).sum())))
    pd.DataFrame(ledger).to_csv(OUT/'log_qualification.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(evidence).to_csv(OUT/'conditional_evidence.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(coverage).to_csv(OUT/'feature_coverage.csv',index=False,encoding='utf-8-sig')
    info=dict(names=NAMES,shape=list(x.shape),matched_nodes=hit,qualified_relations=len(evidence),
              inherited_mask_added=added,permutation_changed_rows=int(np.any(x[:,2:6]!=perm[:,2:6],axis=1).sum()),
              elapsed_s=time.perf_counter()-t,seed_permutation=20261025,
              semantics='two tested cut patterns; seq1 arbitrary state; legacy cell map; no full-cut or reset-reach proof',
              no_new_sat_queries=True)
    (OUT/'feature_manifest.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(info,ensure_ascii=False,indent=2),flush=True)
    print(pd.DataFrame(coverage).to_string(index=False),flush=True)


if __name__=='__main__':
    main()
