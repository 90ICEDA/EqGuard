"""Trace the frozen no-keep panel using aliases, formulas and saved endpoint evidence."""
import itertools
import statistics
from collections import Counter, defaultdict
from pathlib import Path
import re
import sys
import os

from evaluate_task2_nokeep_20261113 import CONFIRM, OUT, P, ROOT, dump, module, read, rows, sha, write_csv


def role(cell):
    return {'T':'触发','P':'载荷','S':'载荷选择','HJ':'输出劫持'}[re.search(r'(HJ|[TPS]\d+)$',cell).group(1).rstrip('0123456789')]


def main():
    module('task2_carrier_parser',CONFIRM/'build.py')
    a=sys.modules['audit']
    registry=read(P/'lcone_head_gate_20261112/CONFIRMATION_REGISTRY.json')['registered']
    witnesses=defaultdict(list)
    for r in registry:
        if r['status']=='registered_evidence_only':
            for e in r['endpoints']:
                if e['status']=='positive':
                    witnesses[Path(r['target']).stem].append((e['kind'],e['endpoint'],set(e['inserted_source_cells'])))
    for label in ('s38584','s38584_alpha'):
        for r in rows(OUT/f'{label}_WITNESS_REPLAY.csv'):
            witnesses[r['view']].append((r['kind'],r['endpoint'],set(r['source_lineage'].split('|'))))
    phase=[]
    for folder in ('control_signed_carrier_20261109_v3','control_signed_carrier_20261109_v3_1'):
        p=P/folder/'RELATIONS_V3.csv'
        if p.exists():
            phase.extend(r for r in rows(p) if r['accepted_or_unresolved']=='accepted')
    suffix=os.environ.get('EQGUARD_TRACE_SUFFIX','_V2')
    table, audit = [], []
    for r in rows(OUT/'PANEL40.csv'):
        path=ROOT/r['path']; view=path.stem
        if view not in witnesses:
            continue
        host, source = r['host'],r['source']
        origin=ROOT/f'generate_trans/hosts_bt2/{host}/{source}.v'
        clean=ROOT/f'generate_trans/hosts/{host}/base/{host}_clean.v'
        assert sha(path)==r['target_sha256']
        c,o,t=[a.endpoints(p) for p in (clean,origin,path)]
        prov,=[z for z in read(clean.parent.parent/'provenance.json') if z['view']==source]
        inserted,aliases,missing=a.bind_lineage(prov,c,o)
        assert not missing
        bound,_,_=a.binding(c,o,t,aliases)
        e=a.Expressions(); source_eval=a.construct(o,e,bound); target_eval=a.construct(t,e,bound)
        tg=t[0]; sg=o[0]
        scopes=defaultdict(set)
        direct_observation=defaultdict(list)
        for k,ep,lineage in witnesses[view]:
            net=dict(tg['pins'][ep][1])['D'] if k=='D' else ep
            members,issues=a.structural_cone(t,net); assert members and not issues
            src_net=dict(sg['pins'][ep][1])['D'] if k=='D' else ep
            canonical=tg['find'](net)
            drivers=tg['drivers'][canonical]; assert len(drivers)==1
            driver,=drivers
            direct_observation[sg['find'](src_net)].append((f'{k}:{ep}',canonical,driver))
            for gate in members:
                scopes[gate].add(f'{k}:{ep}')
        outputs=defaultdict(list)
        for net,drivers in list(tg['drivers'].items()):
            if len(drivers)!=1:
                continue
            driver,=drivers
            try:
                rid,_=target_eval(net)
                outputs[e.inputs(rid)].append((net,driver,rid))
            except (ValueError,KeyError,RecursionError):
                continue
        matched_phase=[p for p in phase if p['source_object']==source and p['source_sha']==sha(origin) and p['target_sha']==sha(path)]
        audit.append(dict(view=view,source_sha256=sha(origin),target_sha256=sha(path),phase_rows=len(matched_phase),
                          witnessed_endpoints=len(witnesses[view]),candidate_outputs=sum(map(len,outputs.values()))))
        candidates=[]
        for planned in prov['new_gates']:
            cell=aliases.get(planned,{}).get('instance',planned)
            assert cell in inserted
            typ,pins=sg['pins'][cell]
            for pin,net in pins:
                if pin not in a.S.lib_pins[typ]['outputs']:
                    continue
                root,_=source_eval(net); variables=sorted(e.inputs(root)); source_end={f'{k}:{ep}' for k,ep,ls in witnesses[view] if cell in ls}
                pool=outputs[frozenset(variables)]
                # For small local functions, verify equality and polarity over the same named free boundary.
                if len(variables)<=12:
                    pool=[entry for support,entries in outputs.items() if support <= frozenset(variables) for entry in entries]
                    count=1<<len(variables); mask=(1<<count)-1
                    env={v:sum(1<<i for i in range(count) if i>>j&1) for j,v in enumerate(variables)}
                    ev=e.evaluator(env,mask); ref=ev(root)
                    match=[(n,d,1 if ev(rt)==ref else -1,'local_full_truth') for n,d,rt in pool if ev(rt) in (ref,mask^ref)]
                    const=ref in (0,mask)
                    ev.cache_clear()
                else:
                    match=[(n,d,1,'structural_formula_identity') for n,d,rt in pool if rt==root]
                    const=False
                named_net=tg['find'](net)
                # Restrict name-independent carriers to an actually witnessed affected endpoint cone.
                admissible=[x for x in match if x[0]==named_net or scopes[x[1]] & source_end]
                admissible.sort(key=lambda x:(x[0]!=named_net,not bool(scopes[x[1]]&source_end),x[2]!=1,x[0]))
                candidates.append(dict(view=view,source=source,recipe=r['recipe'],keep=r['keep'],planned=planned,source_cell=cell,
                    role=role(cell),source_pin=pin,source_net=net,source_type=typ,inputs=len(variables),source_end=source_end,
                    matches=admissible,named_net=named_net,constant=const,named_present=bool(tg['drivers'].get(named_net)),
                    observed_output='|'.join(f'{ep}:{signal}:{driver}' for ep,signal,driver in sorted(direct_observation[sg['find'](net)]) if ep in source_end)))
        chosen=Counter(x['matches'][0][0] for x in candidates if x['matches'])
        for x in candidates:
            matches=x.pop('matches'); ends=x.pop('source_end'); named=x.pop('named_net'); const=x.pop('constant')
            n,d,pol,method=matches[0] if matches else ('','','','')
            structural_constant=tg['find'](x['source_net']) in ('#0','#1')
            if matches and chosen[n]>1:
                status='folded_or_merged'
            elif matches and n==named and pol==1 and (d==x['source_cell'] or tg['pins'][d][0]==x['source_type']):
                status='retained'
            elif matches:
                status='alternate_carrier'
            else:
                status='unknown'
            # Constant evidence is reported separately. An endpoint witness does not prove independent necessity of a source cell.
            table.append(dict(**x,status=status,target_net=n,target_driver=d,polarity=pol,evidence=method,
                candidate_count=len(matches),alternate_candidates='|'.join(f'{net}:{gate}:{phase}' for net,gate,phase,_ in matches),
                source_witness_endpoints='|'.join(sorted(ends)),carrier_witness_endpoints='|'.join(sorted(scopes[d]&ends)),
                source_constant=const,target_alias_constant=structural_constant,certified_eliminated=False))
        e.inputs.cache_clear()
    assert len(audit)==12 and len({(r['view'],r['source_cell'],r['source_pin']) for r in table})==len(table)
    write_csv(OUT/f'TASK2_CARRIER_TRACE{suffix}.csv',table)
    final=[]
    for r in table:
        status,basis=r['status'],r['evidence'] or 'unresolved_internal_function'
        if r['observed_output']:
            status,basis='alternate_carrier','bound_physical_D_PO_output_existing_witness_and_CEC'
        elif r['target_alias_constant']:
            status,basis='folded_or_merged','named_target_net_constant_only_functional_carrier_unresolved'
        final.append(dict(r,status=status,internal_carrier_status=r['status'],classification_basis=basis))
    write_csv(OUT/'TASK2_CARRIER_TRACE_FINAL.csv',final)
    write_csv(OUT/f'TASK2_CARRIER_INPUTS{suffix}.csv',audit)

    paired=[]
    for label in ('s38417','s38584','s38584_alpha'):
        source_rows=rows(OUT/f'{label}_N_NC_BY_SEED.csv')
        ix={(r['recipe'],r['keep'],r['seed'],r['arm'],r['point'],r['kind']):r for r in source_rows}
        assert len(ix)==96
        for recipe,arm,point,kind in itertools.product(('abc','nand'),('N','NC'),('best','last'),('D','PO')):
            line=dict(source=source_rows[0]['view'].split('__keep')[0],recipe=recipe,arm=arm,point=point,kind=kind)
            for k in ('cone_ap','top5','recall512','equal_fp','equal_unknown','equal_gates','graph_alarm'):
                prev,nxt=[[float(ix[recipe,keep,str(seed),arm,point,kind][k]) for seed in (42,1,2)] for keep in ('keepcur','keepnone')]
                line.update({f'{k}_keep':statistics.mean(prev),f'{k}_none':statistics.mean(nxt),f'{k}_delta':statistics.mean(b-a for a,b in zip(prev,nxt))})
            paired.append(line)
    write_csv(OUT/f'TASK2_KEEP_EFFECT_BY_SOURCE{suffix}.csv',paired)
    print(len(table),Counter(r['status'] for r in table),sum(r['phase_rows'] for r in audit),flush=True)


if __name__=='__main__':
    main()
