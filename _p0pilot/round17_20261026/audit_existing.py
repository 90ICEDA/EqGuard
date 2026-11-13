"""Offline historical feature compatibility and structural-index benchmark."""
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT/'10.15/06_统一评测协议/N4_三向泛化/tables'
OUT = TABLES/'sat_audit_round17'
sys.path.insert(0, str(ROOT/'phase2/ys'))
import sat_functional_relations as P0
from sat_boundary_semantics import summarize


def main():
    matches = []
    # Canonical permutation leaves the 18 aggregate features unchanged.
    records = json.loads((TABLES/'sat_boundary_round9/boundary_records.json').read_text())
    for r in records:
        text = r.get('canonical_signature') or r.get('signature')
        if not text:
            continue
        table = {parts[0]: tuple(parts[1:]) for parts in (row.split(':') for row in text.split(';'))}
        features, _ = summarize(table, len(next(iter(table))))
        assert features == r['features'], r.get('relation_id', r.get('boundary_id'))
        matches.append(dict(source='round9', id=r.get('relation_id', r.get('boundary_id')), matched=True))
    for p in [TABLES/'sat_pair_round10/all_aligned_tables.json',
              *sorted((TABLES/'sat_pair_round11').glob('aligned_tables*.json'))]:
        for r in json.loads(p.read_text()):
            features, inputs = summarize(r['truth'], 4)
            assert features == r['features'] and inputs == r['inputs']
            matches.append(dict(source=p.name, id=r['relation_id'], side=r['side'], matched=True))
    g = dict(names={i:f'n{i}' for i in range(1, 6001)},
             ports={'out':dict(direction='output',bits=list(range(4001, 6001)))},
             cells={f'gate{i}':dict(type='AND2X2',connections={'IN1':[i], 'IN2':[i+2000], 'Q':[i+4000]})
                    for i in range(1,2001)})
    starts = [f'n{i}' for i in range(4001,4201)]
    t = time.perf_counter()
    uncached = [P0.forward_reach(g, [s]) for s in starts]
    uncached_s = time.perf_counter()-t
    t = time.perf_counter()
    index = P0.forward_index(g)
    cached = [P0.forward_reach(g, [s], index=index) for s in starts]
    cached_s = time.perf_counter()-t
    assert cached == uncached
    # A minimal old/new input-index counterexample, no new circuit evidence.
    path = ROOT/'phase2/ys/sat_functional_relations_v3.py.bak_round17_20261026'
    # .bak is not a recognized Python extension.
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader('old_v3_for_counterexample', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    old = importlib.util.module_from_spec(spec); loader.exec_module(old)
    import sat_functional_relations_v3 as new
    import itertools
    pats = list(itertools.product((0,1),repeat=3))
    c = dict(kind='mux', cut={'S0':'s','A':'a','B':'b'},_patterns=pats,_nq=16)
    got = [status for p in pats for status in (['proved','refuted'] if p[0] else ['refuted','proved'])]
    old_result = old.parse_case(c,got);new_result = new.parse_case(c,got)
    assert old_result['control_influence']==0 and new_result['control_influence']==1
    info = dict(compatibility_records=len(matches), all_features_unchanged=True, records=matches,
                projection_S0_old=old_result, projection_S0_new=new_result,
                index_benchmark=dict(cells=2000, targets=200, uncached_s=uncached_s,
                                     cached_including_build_s=cached_s,
                                     ratio=uncached_s/cached_s,
                                     equal_outputs=True,
                                     scope='synthetic structural indexing only; not SAT solver or training speed'),
                training_runs=0, new_project_sat_queries=0,
                code_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in [ROOT/'phase2/ys/sat_boundary_semantics.py',
                                       ROOT/'phase2/ys/sat_functional_relations.py',
                                       ROOT/'phase2/ys/sat_functional_relations_agnostic.py',
                                       ROOT/'phase2/ys/sat_functional_relations_v3.py']})
    (OUT/'existing_evidence_audit.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in info.items() if k not in ('records','projection_S0_old','projection_S0_new')},indent=2))


if __name__=='__main__':
    main()
