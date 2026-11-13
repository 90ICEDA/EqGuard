"""Round 21A data contract: full-table representation + leave-one-family-out folds.

No SAT query, no label read, no model fitting. Uses only existing Round 18
small-netlist tables and the Round 19 offline candidate representation.
"""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
R18 = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
R19 = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_diagnosis_round19'
OUT = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_round21'

WIDTH = 114
FAMILIES = ['alpha', 'beta', 'epsilon', 'zeta']


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_json(p, x):
    Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')


def load_records():
    records = json.loads((R18 / 'records.json').read_text(encoding='utf-8'))
    base = np.load(R18 / 'base_inputs.npz')
    cand = np.load(R19 / 'candidate_boundary_repr.npz')
    perm_map = json.loads((R18 / 'permutation_stratified.json').read_text(encoding='utf-8'))
    n = len(records)
    ids = base['global_ids']
    view_index = base['view_index']
    assert n == 2435 == len(ids) == len(view_index) == cand['canonical_state_onehot'].shape[0]
    family = np.empty(n, dtype=object)
    view = np.empty(n, dtype=object)
    split_original = np.empty(n, dtype=object)
    status = np.empty(n, dtype=object)
    by_ln = {}
    for r in records:
        i = int(r['local_node'])
        assert 0 <= i < n and i not in by_ln
        by_ln[i] = r
        family[i] = r['family']
        view[i] = r['view']
        split_original[i] = r['split']
        status[i] = r['status']
    assert len(by_ln) == n and all(x is not None for x in family)
    return records, base, cand, perm_map, ids, view_index, family, view, split_original, status, by_ln


def build_arrays(cand, perm_map, by_ln, covered):
    n = len(by_ln)
    state = cand['canonical_state_onehot'].astype(np.float32)
    pattern_valid = cand['pattern_valid'].astype(np.float32)
    k = cand['k'].astype(np.float32)
    per_input = cand['per_input_original'].astype(np.float32)
    input_valid = cand['input_valid'].astype(np.float32)
    assert state.shape == (n, 16, 5) and pattern_valid.shape == (n, 16)
    assert per_input.shape == (n, 4, 3) and input_valid.shape == (n, 4)
    assert np.isfinite(state).all() and np.isfinite(per_input).all()
    assert np.isin(state, (0.0, 1.0)).all() and np.all(state.sum(2) <= 1.0)
    assert np.all(state[pattern_valid == 0] == 0.0)
    assert np.all(((cand['k'] == 0) & (pattern_valid.sum(1) == 0)) |
                  ((cand['k'] > 0) & (pattern_valid.sum(1) == 2.0 ** cand['k'])))
    assert np.all(input_valid.sum(1) == cand['k'])
    metadata = np.zeros((n, WIDTH), np.float32)
    metadata[:, 80:96] = pattern_valid
    metadata[:, 96] = k / 4.0
    metadata[:, 97] = covered
    metadata[:, 110:114] = input_valid
    real = metadata.copy()
    real[:, 0:80] = state.reshape(n, 80)
    real[:, 98:110] = per_input.reshape(n, 12)
    return state, per_input, metadata, real


def build_permuted(state, per_input, metadata, perm_map, by_ln, covered):
    n = len(by_ln)
    perm_state = np.zeros_like(state)
    perm_per_input = np.zeros_like(per_input)
    dest_seen = set()
    for item in perm_map:
        d, s = int(item['destination']), int(item['source'])
        assert 0 <= d < n and 0 <= s < n and d not in dest_seen
        dest_seen.add(d)
        assert covered[d] == 1 and covered[s] == 1
        assert tuple(item['stratum']) == (by_ln[d]['split'], by_ln[d]['target_role'],
                                          by_ln[d]['driver_type'], by_ln[d]['k'])
        assert (by_ln[d]['split'], by_ln[d]['target_role'], by_ln[d]['driver_type'],
                by_ln[d]['k']) == (by_ln[s]['split'], by_ln[s]['target_role'],
                                   by_ln[s]['driver_type'], by_ln[s]['k'])
        perm_state[d] = state[s]
        perm_per_input[d] = per_input[s]
    assert len(dest_seen) == 2291
    permuted = metadata.copy()
    permuted[:, 0:80] = perm_state.reshape(n, 80)
    permuted[:, 98:110] = perm_per_input.reshape(n, 12)
    return permuted

def build():
    OUT.mkdir(parents=True, exist_ok=True)
    (records, base, cand, perm_map, ids, view_index, family, view,
     split_original, status, by_ln) = load_records()
    n = len(records)
    covered = cand['covered'].astype(np.float32)
    state, per_input, metadata, real = build_arrays(cand, perm_map, by_ln, covered)
    permuted = build_permuted(state, per_input, metadata, perm_map, by_ln, covered)
    for a, name in ((metadata, 'metadata'), (real, 'real'), (permuted, 'permuted')):
        assert a.shape == (n, WIDTH) and np.isfinite(a).all()
        assert np.unique(a, axis=0).shape[0] > 1, name

    np.savez_compressed(OUT / 'features.npz', metadata=metadata, real=real,
                        permuted=permuted, global_ids=ids, view_index=view_index,
                        family=np.asarray(family, dtype=str), view=np.asarray(view, dtype=str))

    folds = []
    for i, test_family in enumerate(FAMILIES):
        val_family = FAMILIES[(i + 1) % len(FAMILIES)]
        train_families = [f for f in FAMILIES if f not in (test_family, val_family)]
        folds.append(dict(
            fold=f'test_{test_family}',
            train_families=train_families,
            val_families=[val_family],
            test_families=[test_family],
            train_indices=np.flatnonzero(np.isin(family, train_families)).tolist(),
            val_indices=np.flatnonzero(np.isin(family, [val_family])).tolist(),
            test_indices=np.flatnonzero(np.isin(family, [test_family])).tolist(),
        ))
    for f in folds:
        sets = [set(f[k]) for k in ('train_indices', 'val_indices', 'test_indices')]
        assert not sets[0] & sets[1] and not sets[0] & sets[2] and not sets[1] & sets[2]
        assert sum(len(s) for s in sets) == n

    nodes = []
    for i in range(n):
        nodes.append(dict(local_node=i, global_id=int(ids[i]), view_index=int(view_index[i]),
                          view=str(view[i]), family=str(family[i]),
                          split_original=str(split_original[i]), status=str(status[i]),
                          covered=bool(covered[i]), k=int(cand['k'][i])))
    write_json(OUT / 'folds.json', dict(families=FAMILIES, folds=folds,
                                        node_order='local_node == base_inputs row order',
                                        rule='test one family; val next family; train remaining two',
                                        posthoc=True, confirmatory=False))
    with (OUT / 'nodes.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(nodes[0]))
        w.writeheader()
        w.writerows(nodes)

    schema = dict(width=WIDTH, base_columns=39, total_input=39 + WIDTH,
                  layout=dict(
        state_onehot=[0, 80], pattern_valid=[80, 96], k_over_4=96,
        covered=97, per_input=[98, 110], input_valid=[110, 114]),
        metadata_only='k/4, covered, pattern_valid, input_valid; all content slots zero',
        real='full 16x5 state + pattern mask + k + covered + 4x3 per-input + input mask',
        permuted='state and per-input copied from same-stratum donor; destination mask/k/covered retained',
        state_shape=[16, 5], states=['infeasible', 'forced_zero', 'forced_one',
                                     'feasible_undecided', 'solver_unknown'],
        rows=n, covered_nodes=int(covered.sum()), permutation_pairs=2291,
        nonlocal_metadata='no raw bit/node ID/hash is used as a feature')
    write_json(OUT / 'feature_schema.json', schema)

    protocol = dict(
        round=21, step='21A', status='frozen_pending_execution',
        purpose='posthoc leave-one-family-out diagnostic of full-table representation',
        confirmatory=False, new_sat_queries=0, new_training_runs_planned=36,
        data_source='Round18 8 small rs232t1000/ys_abc netlists; Round19 candidate table',
        rows=n, families=FAMILIES,
        folds=[f['fold'] for f in folds], seeds=[42, 1, 2],
        arms=['metadata', 'real', 'permuted'], updates=250, val_every=10,
        model=dict(name='GINNodeClassifier', in_channels=39 + WIDTH, hidden=64,
                   layers=4, classes=2, dropout=0.2),
        optimizer=dict(name='Adam', lr=0.001, weight_decay=0.001),
        precision='float32', amp=False, deterministic=True,
        normalization='39 base columns fit on each fold train families only; clip +/-10',
        table_normalization='none; state one-hot and bounded per-input stats retained',
        class_weight='neg/pos from each fold train labels only',
        checkpoint_primary='final at exactly 250 updates; best-val saved only as secondary',
        threshold='95th percentile of each fold validation negatives; strict p > threshold',
        test_policy='all three arms and three seeds committed before test labels read',
        metrics=['AP', 'ROC_AUC', 'recall', 'FPR', 'precision_or_null'],
        paired=['real-metadata', 'real-permuted', 'permuted-metadata'],
        go_no_go=dict(
            primary='real must beat permuted on the same fold/seed',
            require_fold_signs='at least 3 of 4 family-level mean deltas > 0 for real-permuted and real-metadata',
            require_overall='mean real-permuted test AP > 0 and mean real-metadata test AP > 0',
            require_data_use='test AP must be reported with prevalence; no test threshold tuning',
            not_enough='if fail, do not trigger 21B extraction; SAT remains unproven as a dense feature'),
        hashes=dict(features=sha_file(OUT / 'features.npz'),
                    folds=sha_file(OUT / 'folds.json'),
                    schema=sha_file(OUT / 'feature_schema.json'),
                    records=sha_file(R18 / 'records.json'),
                    candidate=sha_file(R19 / 'candidate_boundary_repr.npz'),
                    permutation=sha_file(R18 / 'permutation_stratified.json')),
        test_labels_read=False,
    )
    write_json(OUT / 'protocol.json', protocol)
    print(json.dumps(dict(rows=n, covered=int(covered.sum()), folds=protocol['folds'],
                          hashes=protocol['hashes']), indent=2))


if __name__ == '__main__':
    build()
