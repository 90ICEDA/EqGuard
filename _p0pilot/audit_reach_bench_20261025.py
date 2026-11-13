"""Compare legacy reach and alias-aware indexed reach on identical real queries."""
import json
import sys
import time
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'phase2/ys'))
import sat_functional_relations as P0
from structural_reach_index import ReachIndex
OUT=ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables/audit_20261025'


def selfcheck():
    mod=dict(netnames={'alias':{'bits':[1]},'driver':{'bits':[1]},'clk':{'bits':[3]}},
             ports={'out':dict(bits=[1],direction='output')},
             cells={'ff':dict(type='DFF',connections={'D':[1],'CLK':[3],'Q':[4]})})
    r=ReachIndex(mod)
    assert r.reach('alias')['reach_po']==r.reach('out')['reach_po']==1
    assert r.reach('alias')['reach_dff']==1
    assert r.reach('clk')['reach_dff']==0
    assert not r.reach('missing')['start_found']


def main():
    selfcheck()
    rows=[]
    stats=[]
    paths=[Path(p) for p in pd.read_csv(OUT/'two_case_timing.csv',encoding='utf-8-sig').cached_struct]
    # Other rs232 views reuse the original full_logs cache.
    paths += [p for p in (ROOT/'_p0pilot/full_logs/rs232t1000').glob('*.struct_raw.json')
              if any(f'__{i}_d1_s42__' in p.name for i in ['injalpha','injepsilon'])
              and not 'keep' in p.name and any(f'__{r}.' in p.name for r in ['ys_id','ys_abc','ys_aig'])]
    seen=set()
    for path in paths:
        modules=json.loads(path.read_text(encoding='utf-8'))['modules']
        top=next(iter(modules))
        if top in seen:
            continue
        seen.add(top)
        mod=modules[top]
        g=P0.load_graph(path,top)
        names=list(dict.fromkeys(list(mod['ports'])+list(mod.get('netnames',{}))))
        # Include output aliases, then a deterministic spread of internal names.
        names=list(mod['ports']) + names[::max(1,len(names)//100)]
        t=time.perf_counter()
        old=[P0.forward_reach(g,[name]) for name in names]
        old_s=time.perf_counter()-t
        t=time.perf_counter()
        ri=ReachIndex(mod)
        new=[ri.reach(name) for name in names]
        new_s=time.perf_counter()-t
        t=time.perf_counter()
        [ri.reach(name) for name in names]
        repeat_s=time.perf_counter()-t
        stats.append(dict(design=top,queries=len(names),legacy_s=old_s,index_build_and_queries_s=new_s,
                          cached_queries_s=repeat_s,speedup=old_s/max(new_s,1e-9),unsupported_cells=len(ri.unsupported)))
        for name,o,n in zip(names,old,new):
            rows.append(dict(design=top,net=name,legacy_po=o[0],legacy_dff=o[1],**n,
                             changed=(o!=(n['reach_po'],n['reach_dff']))))
    OUT.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT/'reach_semantics_compare.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(stats).to_csv(OUT/'reach_benchmark.csv',index=False,encoding='utf-8-sig')
    print(pd.DataFrame(stats).to_string(index=False))
    print(f'changed={sum(r["changed"] for r in rows)}/{len(rows)}')


if __name__=='__main__':
    main()
