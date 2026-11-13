"""Audit D-driver neighborhoods and shared score maxima on frozen assets."""
import csv
import itertools
from collections import Counter, defaultdict, deque

import numpy as np

from audit import BOUNDARY, CACHE, EVIDENCE, OUT, P, load_module, read, sha, write_csv, write_json
from diagnose_pilot import load_cases, snapshot

SOURCES = ('injalpha_d1_s42', 'injdelta_d1_s42')
ARMS = ('N', 'NC-BCE', 'NC-BCE-Cap')
FOLD = 'ys_nand'


def view_graph(split, layouts, selected):
    folder = BOUNDARY / f'inputs/trans_{split}'
    edge = np.load(folder / 'edge_index.npy', mmap_mode='r')
    roles = np.load(folder / 'edge_roles.npy', mmap_mode='r')
    assert edge.shape[1] == len(roles)
    out = {}
    for view in sorted(selected):
        v = layouts[view]
        start, stop = v['start'], v['stop']
        which = (edge[1] >= start) & (edge[1] < stop)
        assert np.all((edge[0, which] >= start) & (edge[0, which] < stop))
        parents = defaultdict(dict)
        for a, b, role in zip(*edge[:, which], roles[which]):
            parents[int(b)][int(a)] = int(role)
        out[view] = parents
    return out


def cache_records(path, split, views):
    out = {}
    with path.open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['split'] != split or r['kind'] != 'D' or r['view'] not in views or not int(r['n_phys']):
                continue
            key = r['view'], r['cone_id']
            assert key not in out
            out[key] = r
    return out


def d_neighborhood(view, cid, parents, row_names, layout, cache):
    r = cache[view, cid]
    members = set(map(int, r['phys_rows'].split('|')))
    aux = set(int(x) for x in r['aux_globals'].split('|') if x)
    d = row_names[cid.split(':', 1)[1]]
    ds = [p for p, flags in parents.get(d, {}).items() if flags & 1]
    assert len(ds) == 1, (view, cid, ds)
    driver = ds[0]
    if r['driver'] in row_names:
        assert row_names[r['driver']] == driver
    # Auxiliary assign nodes may sit on a path between two physical gates.
    allow = members | aux
    assert driver in allow
    hops = {driver: 0}
    q = deque([driver])
    while q:
        curr = q.popleft()
        for p in parents.get(curr, {}):
            if p in allow and p not in hops:
                hops[p] = hops[curr]+1
                q.append(p)
    assert members <= hops.keys(), (view, cid, len(members-hops.keys()), len(aux), layout['physical_stop'])
    return driver, {i: hops[i] for i in members}


def main():
    panel = load_module('locality_endpoint', P / 'lcone_endpoint_frozen_20261112/audit.py')
    _, _, names_test, layouts_test = panel.S.load_snapshot('test')
    _, _, names_train, layouts_train = panel.S.load_snapshot('train')
    _, test, cases = load_cases()
    fold_rows = test['new2old']
    target_views = {src: next(v for v in layouts_test if f'__{src}__ys_nand' in v) for src in SOURCES}
    test_cache = cache_records(P / 'seed42_nc_ablation_20261109/CONE_CACHE_TEST.csv', 'test', set(target_views.values()))
    test_edges = view_graph('test', layouts_test, target_views.values())
    contract = read(OUT / 'PILOT_PREFLIGHT.json')
    train_evidence = {(r['view'], r['cone_id']): r for r in read(EVIDENCE) if r['kind'] == 'D' and r['label'] == 1}
    train_targets = {(r['view'], r['positive']) for f in contract['folds'].values() for r in f['pool']}
    train_views = {v for v, _ in train_targets}
    train_cache = cache_records(CACHE, 'train', train_views)
    train_edges = view_graph('train', layouts_train, train_views)
    train_rows = []
    for view, cid in sorted(train_targets):
        ev = train_evidence[view, cid]
        driver, hops = d_neighborhood(view, cid, train_edges[view], panel.S.view_rows(layouts_train, names_train, view),
                                     layouts_train[view], train_cache)
        assert sorted(hops) == ev['member_rows'] and ev['driver_row'] == driver
        train_rows.append(dict(view=view, source=ev['source'], endpoint=cid, driver=driver, members=len(hops),
                               driver_in_physical_cone=driver in hops,
                               within_one_hop=sum(h <= 1 for h in hops.values()),
                               within_two_hops=sum(h <= 2 for h in hops.values())))
    baseline, cap = (OUT / 'PILOT_TEST_MARGINS.npz', OUT / 'PILOT_CAPPED_TEST_MARGINS.npz')
    saved = read(OUT / 'PILOT_CAPPED_FROZEN_RESULTS.json')['frozen_score_hashes']
    assert saved == dict(baseline=sha(baseline), candidate=sha(cap))
    endpoint_rows, sharing = [], []
    for source, view in target_views.items():
        group = cases[source]
        row_names = panel.S.view_rows(layouts_test, names_test, view)
        geometry = {}
        for cid, (_, rr) in group.items():
            driver, hops = d_neighborhood(view, cid, test_edges[view], row_names, layouts_test[view], test_cache)
            assert set(fold_rows[rr]) == hops.keys()
            geometry[cid] = (driver, hops)
        with np.load(baseline) as n, np.load(cap) as c:
            for arm, point in itertools.product(ARMS, ('best', 'last')):
                margin = (c if arm == 'NC-BCE-Cap' else n)[f'{FOLD}_{arm}_{point}']
                scores, winners, order = snapshot(group, margin)
                winner_global = {cid: set(fold_rows[list(rows)]) for cid, rows in winners.items()}
                winning_counts = Counter(i for rows in winner_global.values() for i in rows)
                prefix = []
                gates = set()
                for cid in order:
                    g = gates | geometry[cid][1].keys()
                    if len(g) > 512:
                        break
                    gates = g
                    prefix.append(cid)
                for cid in order:
                    label, _ = group[cid]
                    if label != 'positive' and cid not in prefix:
                        continue
                    driver, hops = geometry[cid]
                    peaks = winner_global[cid]
                    near = [margin[test['old2new'][i]] for i, h in hops.items() if h <= 2]
                    assert near
                    higher = [i for i in order[:order.index(cid)] if scores[i] > scores[cid]]
                    endpoint_rows.append(dict(source=source, arm=arm, point=point, endpoint=cid, label=label,
                        rank=order.index(cid)+1, members=len(hops), driver_score=float(margin[test['old2new'][driver]]) if driver in hops else None,
                        cone_score=scores[cid], near_max=float(max(near)), winner_min_hops=min(hops[p] for p in peaks),
                        winner_max_hops=max(hops[p] for p in peaks), winner_shared_max_cones=max(winning_counts[p] for p in peaks),
                        strictly_higher_share_winner=sum(bool(peaks & winner_global[p]) for p in higher),
                        higher_shared_inside_positive=sum(bool(winner_global[p] & hops.keys()) for p in higher),
                        in_budget=cid in prefix))
                count = Counter(i for p in prefix for i in winner_global[p])
                prefix_sizes = Counter(group[p][0] for p in prefix)
                sharing.append(dict(source=source, arm=arm, point=point, prefix_endpoints=len(prefix), prefix_gates=len(gates),
                                    prefix_unknown=prefix_sizes['unknown'], prefix_negative=prefix_sizes['negative'],
                                    prefix_distinct_max_nodes=len(count),
                                    prefix_shared_max_endpoints=sum(any(count[i] > 1 for i in winner_global[p]) for p in prefix)))
    write_csv(OUT / 'D_LOCALITY_TEST.csv', endpoint_rows)
    write_csv(OUT / 'D_LOCALITY_TRAIN_POSITIVE.csv', train_rows)
    write_json(OUT / 'D_LOCALITY_AUDIT.json', dict(prefix=sharing, train_positive_views=len(train_rows),
              rows=len(endpoint_rows), optimizer_steps=0, forward_passes=0, sat_cec_calls=0, labels_modified=False))


if __name__ == '__main__':
    main()
