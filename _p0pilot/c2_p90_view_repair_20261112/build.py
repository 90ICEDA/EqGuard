"""Recover cone view identities without changing historical C2 assets."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
C2 = P / 'c2_heldout_20261111'
CACHE = P / 'seed42_supervised_prep_20261109/CONE_CACHE_V2.csv'
FOLDS = ('ys_abc', 'ys_aig', 'ys_nand')


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def load_fold(fold, group_rows):
    with np.load(C2 / f'{fold}_train.npz') as data:
        train = {k: data[k] for k in ('view', 'start', 'stop', 'y', 'trusted', 'physical')}
    ranges = dict(zip(train['view'], zip(train['start'], train['stop'])))
    assert len(ranges) == len(train['view']) and all('ctl' not in v and not v.endswith('__' + fold) for v in ranges)
    glob_to_local = np.full(int(group_rows.max()) + 1, -1, dtype=np.int64)
    retained = np.zeros(len(group_rows), dtype=bool)
    for start, stop in ranges.values():
        retained |= (group_rows >= start) & (group_rows < stop)
    fold_rows = group_rows[retained]
    glob_to_local[fold_rows] = np.arange(len(fold_rows))
    assert len(fold_rows) == len(train['y'])
    return train, ranges, glob_to_local


def main():
    with np.load(P / 'four_group_contract_20261109/group_B.npz') as group:
        group_rows = group['rows']
    assert len(np.unique(group_rows)) == len(group_rows)
    folds = {fold: load_fold(fold, group_rows) for fold in FOLDS}
    positive = {fold: [] for fold in FOLDS}
    negative = {fold: [] for fold in FOLDS}
    with CACHE.open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['split'] != 'train' or r['kind'] != 'D' or int(r['n_phys']) < 2:
                continue
            view = r['view']
            relevant = [fold for fold in FOLDS if view in folds[fold][1]]
            if not relevant:
                continue
            original = np.fromstring(r['phys_rows'], sep='|', dtype=np.int64)
            assert len(original) == int(r['n_phys']) and np.all(original >= 0)
            for fold in relevant:
                train, ranges, to_local = folds[fold]
                start, stop = ranges[view]
                assert np.all((original >= start) & (original < stop)), (fold, view, r['cone_id'])
                members = to_local[original[original < len(to_local)]]
                members = np.unique(members[members >= 0])
                if len(members) < 2:
                    continue
                assert train['physical'][members].all()
                y = train['y'][members]
                trust = train['trusted'][members]
                if ((y == 1) & trust).any():
                    if len(members) > 20:
                        rng = np.random.default_rng(len(members))
                        members = np.sort(rng.choice(members, 20, replace=False))
                    positive[fold].append((view, r['cone_id'], members))
                elif ((y == 0) & trust).sum() / len(members) >= 0.5:
                    negative[fold].append((view, r['cone_id'], members))

    report = {'cache_sha256': sha(CACHE), 'folds': {}}
    for fold in FOLDS:
        old = C2 / f'{fold}_cones.npz'
        with np.load(old) as data:
            rows, ptr, label, old_views = (data[k] for k in ('rows', 'ptr', 'label', 'view'))
        cases = positive[fold] + negative[fold]
        assert len(cases) == len(label) and len(ptr) == len(label) + 1
        assert np.array_equal(label, np.arange(len(label)) < len(positive[fold]))
        assert np.array_equal(old_views, np.where(label == 1, 'pos', 'neg'))
        assert len({(v, c) for v, c, _ in cases}) == len(cases)
        for i, (view, cone, members) in enumerate(cases):
            assert np.array_equal(rows[ptr[i]:ptr[i+1]], members), (fold, i, view, cone)
        views = np.array([v for v, _, _ in cases])
        cone_ids = np.array([c for _, c, _ in cases])
        path = OUT / f'{fold}_cones.npz'
        with path.open('xb') as f:
            np.savez_compressed(f, rows=rows, ptr=ptr, label=label, view=views, cone_id=cone_ids)
        pos_counts, neg_counts = Counter(views[label == 1]), Counter(views[label == 0])
        train_views = set(folds[fold][1])
        no_pos = sorted(train_views - pos_counts.keys())
        report['folds'][fold] = dict(old_sha256=sha(old), repaired_sha256=sha(path),
                                     training_views=len(train_views), views_with_cones=len(set(views)),
                                     positive_cones=int(label.sum()), negative_cones=int((label == 0).sum()),
                                     no_positive_views={v: neg_counts[v] for v in no_pos},
                                     negative_cones_with_zero_fallback=sum(neg_counts[v] for v in no_pos),
                                     verified_equal_arrays=['rows', 'ptr', 'label'])
        print(fold, len(cases), len(no_pos), sum(neg_counts[v] for v in no_pos), flush=True)
    with (OUT / 'BUILD.json').open('x', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
