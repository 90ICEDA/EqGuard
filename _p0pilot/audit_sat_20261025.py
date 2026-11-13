"""Read-only legacy audit and separately versioned, query-aligned SAT recheck.

Run with ginvenv/Scripts/python.exe -X utf8 -u ... [coverage|cases].
New outputs only. Grouped bincount avoids O(nodes * views * columns) scans.
SAT recheck retains the legacy cell map / arbitrary initial-state semantics.
It does NOT assert reset reachability or SAT output observability.
"""
from __future__ import annotations
import argparse
import itertools
import json
import re
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PT = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
WORK = ROOT / 'generate_trans/folds/hosts_bt31'
TABLES = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables'
OUT = TABLES / 'audit_20261025'
sys.path.insert(0, str(ROOT / 'phase2/ys'))


def save(rows, name):
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / name, index=False, encoding='utf-8-sig')


def coverage():
    import torch
    t0 = time.perf_counter()
    meta = json.loads((WORK / 'data/for_train/metadata_trans.json').read_text(encoding='utf-8'))
    vid, views = pd.factorize(np.asarray(meta['file_ids'], dtype=object), sort=False)
    del meta
    graph = torch.load(PT / 'trans_graph.pt', map_location='cpu', weights_only=False, mmap=True)
    y = graph.y.numpy().reshape(-1) > 0
    test = graph.test_mask.numpy().reshape(-1).astype(bool)
    trust = np.load(PT / 'trust_trans.npy', mmap_mode='r').reshape(-1).astype(bool)
    x = np.load(PT / 'satrel_node_feats_sat_p0clean4_safe.npy', mmap_mode='r')
    names = json.loads((PT / 'satrel_node_feats_sat_p0clean4_meta.json').read_text(encoding='utf-8'))['names']['safe']
    assert len(y) == len(vid) == len(x)
    nv = len(views)
    n = np.bincount(vid, minlength=nv)
    pos = np.bincount(vid[y], minlength=nv)
    rows = []
    normalization = []
    covered = np.asarray(x[:, -1]) > 0
    for j, name in enumerate(names):
        col = np.asarray(x[:, j])
        nz = col != 0
        hits = np.bincount(vid[nz], minlength=nv)
        ph = np.bincount(vid[nz & y], minlength=nv)
        th = np.bincount(vid[nz & test], minlength=nv)
        finite = bool(np.isfinite(col).all())
        if j < len(names)-1:
            sub=col[covered].astype(np.float64)
            mu=float(sub.mean())
            sd=max(float(sub.std(ddof=1)),1e-6)
            normalization.append(dict(column=name,covered_mu=mu,covered_std=sd,
                                      covered_nonzero=int(np.count_nonzero(sub)),
                                      clipped_covered=int((np.abs((sub-mu)/sd)>10).sum()),
                                      support_outside_covered=int((nz & ~covered).sum())))
        rows.append(dict(scope='ALL', view='ALL', column=name, nodes=len(x), positives=int(y.sum()),
                         nonzero=int(nz.sum()), positive_nonzero=int((nz & y).sum()),
                         nonzero_rate=float(nz.mean()), positive_nonzero_rate=float((nz & y).sum()/max(y.sum(),1)),
                         test_nonzero=int((nz & test).sum()), finite=finite))
        for k, v in enumerate(views):
            rows.append(dict(scope='view', view=v, column=name, nodes=int(n[k]), positives=int(pos[k]),
                             nonzero=int(hits[k]), positive_nonzero=int(ph[k]),
                             nonzero_rate=float(hits[k]/n[k]), positive_nonzero_rate=float(ph[k]/max(pos[k],1)),
                             test_nonzero=int(th[k]), finite=finite))
    save(rows, 'column_coverage.csv')
    save(normalization, 'normalization_audit.csv')
    d=pd.DataFrame(rows)
    d=d[d.scope=='view'].copy()
    d['host']=d.view.str.split('__').str[0]
    d['recipe']=d.view.str.split('__').str[-1]
    grouped=[]
    for dim in ['host','recipe']:
        a=d.groupby([dim,'column'])[['nodes','positives','nonzero','positive_nonzero','test_nonzero']].sum().reset_index()
        a['dimension']=dim
        a['group']=a[dim]
        a['nonzero_rate']=a.nonzero/a.nodes
        grouped.extend(a.drop(columns=[dim]).to_dict('records'))
    save(grouped,'column_coverage_by_host_recipe.csv')
    # Masks distinguish sampled evidence from the union of unrelated layers.
    masks = np.load(PT / 'satrel_node_mask_sat_p0clean2.npy', mmap_mode='r')
    stages = []
    stage_masks = {f'layer_{s}': masks[:, j] > 0 for j, s in enumerate('SPR')}
    stage_masks.update(covered=x[:, -1] > 0, core_any=np.any(x[:, :7] != 0, axis=1),
                       case_any=np.any(x[:, 7:11] != 0, axis=1),
                       proved_sat=x[:, 11] != 0, partial_sat=x[:, 12] != 0,
                       reach_any=np.any(x[:, 4:6] != 0, axis=1))
    for name, mask in stage_masks.items():
        stages.append(dict(stage=name, nodes=int(mask.sum()), fraction=float(mask.mean()),
                           positives=int((mask & y).sum()), test_nodes=int((mask & test).sum()),
                           test_positives=int((mask & test & y).sum()),
                           trusted_positives=int((mask & y & trust).sum()),
                           trusted_test_positives=int((mask & test & y & trust).sum())))
    save(stages, 'node_funnel.csv')
    # Count source evidence independently; these rows are NOT a single monotone funnel.
    source_rows = []
    for path in [ROOT / '_p0pilot/functional_relations_agnostic.csv',
                 ROOT / '_p0pilot/functional_relations_v3.csv', TABLES / 'functional_relations_v3.csv']:
        if not path.exists():
            continue
        d = pd.read_csv(path, encoding='utf-8-sig').fillna('')
        dims = [c for c in ['design', 'kind', 'case_class', 'status', 'status_v3'] if c in d]
        for keys, sub in d.groupby(dims, dropna=False):
            row = dict(source=str(path.relative_to(ROOT)), rows=len(sub))
            row.update(zip(dims, keys if isinstance(keys, tuple) else (keys,)))
            if 'q_unknown' in sub:
                row['queries_unknown'] = int(pd.to_numeric(sub.q_unknown).sum())
            source_rows.append(row)
    save(source_rows, 'source_evidence.csv')
    checks = []
    c3 = np.load(PT / 'satrel_node_feats_sat_p0clean3.npy', mmap_mode='r')
    for j in range(7):
        checks.append(dict(check=f'core_column_{j}_inherited', passed=bool(np.array_equal(x[:,j], c3[:,j]))))
    checks.append(dict(check='covered_inherited', passed=bool(np.array_equal(x[:,-1], c3[:,-1]))))
    reach = np.load(PT / 'satrel_node_feats_sat_p0clean4_core_reach.npy', mmap_mode='r')
    checks.append(dict(check='reach_control_exact_columns', passed=bool(np.array_equal(reach, x[:,[4,5,13]]))))
    checks.append(dict(check='all_case_support_inside_covered', passed=bool(np.all(~stage_masks['case_any'] | stage_masks['covered']))))
    save(checks, 'integrity_checks.csv')
    elapsed = time.perf_counter()-t0
    (OUT / 'coverage_timing.json').write_text(json.dumps(dict(elapsed_s=elapsed, nodes=len(x), views=nv), indent=2))
    print(pd.DataFrame(stages).to_string(index=False), flush=True)
    print(f'[coverage] {elapsed:.2f}s checks={checks}', flush=True)


def parse_block(block):
    if re.search(r'(timed out|timeout reached|Interrupted)', block, re.I):
        return 'unknown'
    if 'no model found: SUCCESS' in block:
        return 'proved'
    if 'model found: FAIL' in block:
        return 'refuted'
    if 'SAT solving finished - no model found.' in block:
        return 'unsat'
    if 'SAT solving finished - model found:' in block:
        return 'sat'
    return 'unknown'


def marked_results(out, n):
    blocks = re.split(r'AUDIT_QUERY_(\d+)\s*\n', out)
    result = ['unknown'] * n
    for i in range(1, len(blocks)-1, 2):
        qid = int(blocks[i])
        if qid < n:
            result[qid] = parse_block(blocks[i+1])
    return result


def exact_influence(patterns, forced):
    table = dict(zip(patterns, forced))
    k = len(patterns[0]) if patterns else 0
    influence = [0]*k
    for p, val in table.items():
        if val is None:
            continue
        for i in range(k):
            other = list(p)
            other[i] ^= 1
            v = table.get(tuple(other))
            if v is not None and v != val:
                influence[i] = 1
    return influence


def checks():
    # Asymmetric function catches the legacy MSB/LSB bug; sampled lists catch non-neighbours.
    pats = list(itertools.product((0,1), repeat=3))
    assert exact_influence(pats, [p[0] for p in pats]) == [1,0,0]
    assert exact_influence([(1,1,1,1),(0,0,0,0)], [1,0]) == [0,0,0,0]
    out = 'AUDIT_QUERY_0\nSAT proof finished - no model found: SUCCESS!\nAUDIT_QUERY_1\nSAT solving timed out.\nAUDIT_QUERY_2\nSAT proof finished - model found: FAIL!\n'
    assert marked_results(out,3) == ['proved','unknown','refuted']


def cases():
    import sat_functional_relations as P0
    import sat_functional_relations_agnostic as AG
    import sat_functional_relations_v3 as V3
    from structural_reach_index import ReachIndex
    checks()
    logdir = ROOT / '_p0pilot/audit_20261025_logs'
    logdir.mkdir(parents=True, exist_ok=True)
    rows, query_rows, timing = [], [], []
    for inst in ['injalpha', 'injepsilon']:
        for recipe in ['ys_id','ys_abc','ys_aig']:
            files = sorted((WORK/'trans').glob(f'rs232t1000__{inst}_d1_s42__{recipe}.v'))
            if not files:
                raise RuntimeError(f'missing canonical view {inst} {recipe}')
            v = files[0]
            top = P0.module_name(v)
            cached = ROOT / f'_p0pilot/full_logs/rs232t1000/{top}.struct_raw.json'
            if not cached.exists() or cached.stat().st_mtime < v.stat().st_mtime:
                cached = logdir / f'{top}.struct.json'
                P0.run_yosys(f'read_verilog "{P0.wsl(v)}"\nhierarchy -top {top}\nflatten\nproc\nwrite_json "{P0.wsl(cached)}"\n', logdir/f'{top}.struct.log')
            g = P0.load_graph(cached, top)
            raw_module=json.loads(cached.read_text(encoding='utf-8'))['modules'][top]
            ri=ReachIndex(raw_module)
            chosen=[]
            for picker in [AG.pick_mux_agnostic, AG.pick_cone_agnostic, AG.pick_dff_next_agnostic]:
                options=picker(g)
                if options:
                    # Audit includes one named mechanism where available; never used to build training features.
                    options.sort(key=lambda c: ('trojan' not in (c['cell']+' '+c['target']).lower(), c['cell']))
                    chosen.append(options[0])
            query_spec=[]
            def queries(c, timeout, max_patterns):
                pats=list(itertools.product((0,1), repeat=len(c['cut'])))
                c['_patterns']=pats
                c['_qids']=[]
                lines=[]
                for p in pats:
                    sets=' '.join(f'-set {c["_refs"][k]} {bit}' for k,bit in zip(c['cut'],p))
                    ids=[]
                    for kind in ['feasible','one','zero']:
                        qid=len(query_spec)
                        query_spec.append((c, p, kind))
                        ids.append(qid)
                        prove='' if kind=='feasible' else f'-prove {c["_pref"] or AG._sat_ref2(c["target"])} {int(kind=="one")}'
                        lines += [f'log AUDIT_QUERY_{qid}', f'sat -seq 1 {sets} {prove} -timeout 3']
                    c['_qids'].append(ids)
                return lines
            original=V3.case_queries_v3
            V3.case_queries_v3=queries
            try:
                script=V3.build_script_v3(v,top,chosen,logdir/f'{top}.sat.json',3,set(g['ports']),8)
            finally:
                V3.case_queries_v3=original
            log=logdir/f'{top}.sat.log'
            t0=time.perf_counter()
            out=P0.run_yosys(script,log,timeout=240)
            elapsed=time.perf_counter()-t0
            if 'ERROR:' in out:
                raise RuntimeError(f'Yosys error: inspect {log}')
            result=marked_results(out,len(query_spec))
            timing.append(dict(design=top,elapsed_s=elapsed,queries=len(result),cached_struct=str(cached)))
            for qid, ((c,p,kind),status) in enumerate(zip(query_spec,result)):
                query_rows.append(dict(design=top,cell=c['cell'],target=c['target'],pattern=''.join(map(str,p)),query=kind,qid=qid,result=status,log=str(log.relative_to(ROOT))))
            for c in chosen:
                forced=[]
                feasible=[]
                vacuous=unknown=0
                for ids in c['_qids']:
                    f,q1,q0=[result[i] for i in ids]
                    feasible.append(f=='sat')
                    vacuous+=int(q1==q0=='proved')
                    unknown+=int('unknown' in (f,q1,q0))
                    forced.append(V3._forced(q1,q0) if f=='sat' else None)
                inf=exact_influence(c['_patterns'],forced)
                # Compare only legacy logic over the SAME new query answers (isolates parser algorithm).
                old=c.copy()
                old['_nq']=2*len(forced)
                legacy=V3.parse_case(old,[result[i] for ids in c['_qids'] for i in ids[1:]])
                complete=not unknown and all(not f or val is not None for f,val in zip(feasible,forced)) and any(feasible)
                npo,ndff=P0.forward_reach(g,[c['target']])
                corrected_reach=ri.reach(c['target'])
                ctrl=inf[list(c['cut']).index('S0')] if 'S0' in c['cut'] else None
                rows.append(dict(view=v.stem,design=top,inst=inst,recipe=recipe,kind=c['kind'],cell=c['cell'],target=c['target'],cut_order=';'.join(c['cut']),cut_nets=';'.join(c['cut'].values()),patterns=len(forced),feasible_patterns=sum(feasible),vacuous_patterns=vacuous,unknown_patterns=unknown,complete_decided=int(complete),influence_i=json.dumps(inf),legacy_influence_i=legacy['influence_i'],control_influence=ctrl,legacy_control_influence=legacy['control_influence'],legacy_reach_po=npo,legacy_reach_dff=ndff,**corrected_reach,observability_status='structural_only',state_semantics='seq1_arbitrary_init_legacy_cell_map',log=str(log.relative_to(ROOT))))
            save(rows,'two_case_relations.csv')
            save(query_rows,'two_case_queries.csv')
            save(timing,'two_case_timing.csv')
            print(f'[audit] {top} cases={len(chosen)} queries={len(result)} unknown={result.count("unknown")} seconds={elapsed:.1f}',flush=True)
    print(pd.DataFrame(rows).to_string(index=False),flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('mode',choices=['coverage','cases'])
    args=a.parse_args()
    (coverage if args.mode=='coverage' else cases)()
