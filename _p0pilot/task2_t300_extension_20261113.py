"""Bind the second held-out design variant and run frozen N/NC evaluation."""
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from evaluate_task2_nokeep_20261113 import CONFIRM, OUT, P, ROOT, dump, evaluate, inspect_log, module, read, sha

HOST = 's38417t300'
SOURCE = HOST + '__injbeta_d1_s42'
WORK = OUT / 'S38417T300_BETA'
ASSETS = WORK / 'graphs'


def main():
    b = module('t300_builder', CONFIRM / 'build.py')
    a = sys.modules['audit']
    assess = module('t300_existing_witness', P/'lcone_head_gate_20261112/register_confirmation.py').assess
    contract = read(P/'control_boundary_v3_20261104/input_contract.json')['shared_inputs']
    exposure = {s:sorted({r['view'].split('__')[0] for r in v['views']}) for s,v in contract.items()}
    assert all(HOST not in hosts for split,hosts in exposure.items() if split.endswith(('train','val')))
    base=ROOT/'generate_trans/hosts_e2'/HOST
    clean, orig = base/'base'/f'{HOST}_clean.v', base/f'{SOURCE}.v'
    assert sha(clean)!=sha(ROOT/'generate_trans/hosts/s38417t100/base/s38417t100_clean.v')
    prov,=[r for r in read(base/'provenance.json') if r['view']==SOURCE]
    old=ROOT/'generate_trans/keepab_e2/conv'/HOST/f'{SOURCE}__keepbnd__ys_abc.v'
    old_log=ROOT/'generate_trans/keepab_e2/logs'/f'cecconv_{old.stem}.log'
    gold,target,_=inspect_log(old_log)
    assert gold==orig and target==old
    reference=assess(clean,orig,old,prov)
    positives={(r['kind'],r['endpoint']):r for r in reference['endpoints'] if r['status']=='positive'}
    assert Counter(k for k,_ in positives)=={'D':37,'PO':1}
    lib=b.V.load_library(b.S.F/'verilog_lib.v')
    mapping={r['full_gate_name']:r['simplified_gate_type'] for r in read(b.S.F/'gate_full_to_simplified_mapping.json')}
    order=read(b.S.F/'gatelookup_recommended.json')['simplified_gate_type_order']
    paths=sorted((WORK/'conv'/HOST).glob('*.v')); assert len(paths)==4
    reports=[]
    for target in paths:
        log=WORK/'logs'/f'cecconv_{target.stem}.log'
        gold,observed,count=inspect_log(log)
        assert gold==orig and observed==target
        c,o,t=map(a.endpoints,(clean,orig,target))
        inserted,aliases,missing=a.bind_lineage(prov,c,o)
        assert not missing
        state,_,_=a.binding(c,o,t,aliases)
        expr=a.Expressions(); evals=[a.construct(g,expr,state) for g in (c,o,t)]
        raw=t[0]; names=[n for n in raw['cells'] if n not in set(raw['virtual_names'])]
        net,parsed,x,names_all,index=b.graph(target,names,lib,mapping,order)
        ends=[('D',n,dict(pins)['D']) for n,(typ,pins) in net['pins'].items() if 'DFF' in typ and 'D' in dict(pins)]
        ends.extend(('PO',n,n) for n in sorted(t[2]))
        entries,ptr,members,verified=[],[0],[],[]
        for k,n,signal in ends:
            entry=dict(kind=k,endpoint=n,status='unknown',rankable=False); entries.append(entry)
            cells,issues=a.structural_cone(t,signal); owners=net['drivers'].get(net['find'](signal),set())
            physical=sorted(index[g] for g in cells if index[g]<len(names))
            if issues or len(owners)!=1 or not physical:
                continue
            driver,=owners
            entry.update(rankable=True,packed_index=len(ptr)-1,driver_row=index[driver]); members.extend(physical); ptr.append(len(members))
            try:
                if k=='D' and n not in state:
                    continue
                signals=[dict(g[0]['pins'][n][1])['D'] for g in (c,o,t)] if k=='D' else [n]*3
                result=[ev(v) for ev,v in zip(evals,signals)]; roots=[x[0] for x in result]
                assert result[-1][1]==cells
                if (k,n) in positives:
                    evidence=positives[k,n]['witness']; assignment=evidence['assignment']
                    boundary=set().union(*(expr.inputs(rt) for rt in roots))
                    if boundary<=assignment.keys() and inserted.intersection(result[1][1]):
                        ev=expr.evaluator(assignment,1); value=[ev(rt) for rt in roots]
                        if value==evidence['clean_orig_trans'] and value[0]!=value[1]==value[2]:
                            entry['status']='positive'; verified.append((k,n))
                elif len(set(roots))==1:
                    entry['status']='negative'
                elif len(set().union(*(expr.inputs(rt) for rt in roots)))<=12:
                    lab,_,_,_=a.qualify(expr,roots)
                    if lab=='negative': entry['status']='negative'
            except (KeyError,ValueError,RecursionError):
                continue
        assert verified and {k for k,_ in verified}=={'D','PO'}
        folder=ASSETS/target.stem; folder.mkdir(parents=True)
        with (folder/'GRAPH_ENDPOINTS.npz').open('xb') as f:
            np.savez_compressed(f,x39=x,edge_index=parsed['edge_index'],physical=np.arange(len(names_all))<len(names),
                                members=np.asarray(members),ptr=np.asarray(ptr))
        dump(folder/'ENDPOINTS.json',entries)
        reports.append(dict(view=target.stem,source=SOURCE,target_sha256=sha(target),cec_sha256=sha(log),proven=count,
                            graph_sha256=sha(folder/'GRAPH_ENDPOINTS.npz'),endpoint_sha256=sha(folder/'ENDPOINTS.json'),
                            positives=verified,counts=dict(Counter(e['kind']+'|'+e['status'] for e in entries if e['rankable']))))
        print(target.stem, reports[-1]['counts'],flush=True)
        expr.inputs.cache_clear()
    shared=set.intersection(*[set(map(tuple,r['positives'])) for r in reports]); assert {k for k,_ in shared}=={'D','PO'}
    for r in reports:
        path=ASSETS/r['view']/'ENDPOINTS.json'
        data=read(path)
        for e in data:
            if e['status']=='positive' and (e['kind'],e['endpoint']) not in shared:
                e['status']='unknown'
        r['view_native_positive_count']=len(r['positives'])
        path.write_text(__import__('json').dumps(data,indent=2),encoding='utf-8')
        r['endpoint_sha256']=sha(path)
    dump(WORK/'GRAPH_REPORT.json',dict(views=reports,shared_positive=sorted(shared),source_sha256=sha(orig),clean_sha256=sha(clean),
                                      reference_target_sha256=sha(old),reference_log_sha256=sha(old_log),split_hosts=exposure))
    evaluate('s38417t300_beta',ASSETS,reports)


if __name__=='__main__':
    main()
