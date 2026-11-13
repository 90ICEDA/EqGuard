"""Sparse diagnostic real/permuted features for 40 relations; no training."""
import json
import sys
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables'
OUT = TABLES / 'sat_repair_round7'
sys.path.insert(0, str(ROOT / '_p0pilot/round6_20261025'))
from r6_truth import classify, influence_from_tt
from build_features_r6 import COLS, record
from audit_repair import table_pairs


def main():
    sources = [('r5', 'sat_nonlocal_round5'), ('r6', 'sat_expand_round6'), ('r7', 'sat_repair_round7')]
    rels, nodes, records, info = [], [], {}, []
    for rnd, folder in sources:
        rel = pd.read_csv(TABLES / folder / f'{rnd}_nonlocal_relations.csv')
        rels.append(rel)
        nodes.append(pd.read_csv(TABLES / folder / f'{rnd}_nodes.csv'))
    rel = pd.concat(rels, ignore_index=True)
    nd = pd.concat(nodes, ignore_index=True)
    for r in rel.itertuples():
        k = len(r.cut_nets.split(';'))
        cls = classify(r.truth_table, k, bool(r.enum_complete), r.query_status)
        tt, pairs = table_pairs(r.truth_table, k)
        inf = influence_from_tt(r.truth_table, k)
        maximum = max((d / c for c, d in pairs if c), default=0.0)
        obj = SimpleNamespace(k=k, **cls, influence_mean=inf['influence_mean'],
            influence_max=maximum, influence_pair_coverage=inf['influence_pair_coverage'],
            influence_valid_inputs=inf['influence_valid_inputs'])
        records[r.relation_id] = record(obj)
        info.append(dict(relation_id=r.relation_id, role=r.role, design=r.design,
            function_status=cls['function_status'], function_class=cls['function_class'],
            has_cond_fact=int(cls['n_forced'] > 0), **inf))
    node_ids = sorted(nd.node_index.unique())
    idx = {int(n): i for i, n in enumerate(node_ids)}
    rid_nodes = nd.groupby('relation_id').node_index.apply(lambda x: sorted(set(x))).to_dict()
    def aggregate(recs):
        a = np.zeros((len(node_ids), len(COLS)), np.float32)
        multi = defaultdict(int)
        for rid, ns in rid_nodes.items():
            v = np.array([recs[rid][c] for c in COLS], np.float32)
            for n in ns:
                a[idx[n]] = np.maximum(a[idx[n]], v)
                multi[n] += 1
        for n, count in multi.items():
            a[idx[n], COLS.index('multi_relation_norm')] = min(count / 2, 1)
            a[idx[n], -1] = 1
        return a
    real = aggregate(records)
    perm_records = dict(records)
    rng = np.random.default_rng(20261025)
    for _, frame in rel.assign(k=rel.cut_nets.str.count(';') + 1).groupby(['design', 'k']):
        order = rng.permutation(len(frame))
        if len(frame) > 1 and np.array_equal(order, np.arange(len(frame))):
            order = np.roll(order, 1)
        for dst, src in zip(frame.relation_id, frame.relation_id.iloc[order]):
            perm_records[dst] = records[src]
    perm = aggregate(perm_records)
    assert np.isfinite(real).all() and real.min() >= 0 and real.max() <= 1
    roles = nd.drop_duplicates('node_index').set_index('node_index').role
    changed = np.any(real != perm, axis=1)
    structural = [0, 9, 23, 24]
    assert np.array_equal(real[:, structural], perm[:, structural])
    np.savez_compressed(OUT / 'diagnostic_features_sparse.npz', node_index=np.array(node_ids), real=real, permuted=perm)
    pd.DataFrame(info).to_csv(OUT / 'corrected_relations_40.csv', index=False, encoding='utf-8-sig')
    summary = dict(relations=len(rel), support=len(node_ids), columns=COLS,
        sparse_diagnostic_only=True, dense_training_file_created=False,
        changed_by_role={role: sum(bool(changed[i]) for i, n in enumerate(node_ids) if roles.loc[n] == role)
                         for role in ('train', 'val')},
        classes=pd.DataFrame(info).function_class.value_counts().to_dict(),
        changed_columns={c: int(np.count_nonzero(real[:, i] != perm[:, i])) for i, c in enumerate(COLS)},
        aggregation='numeric max; function flags OR; count/2 capped; annotations, not Trojan labels',
        conditional_forcing_relations=sum(x['has_cond_fact'] for x in info))
    (OUT / 'feature_diagnostics.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
