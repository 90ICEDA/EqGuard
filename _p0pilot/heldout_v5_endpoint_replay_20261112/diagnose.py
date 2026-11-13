"""Decompose v5 budget misses and equal-recall unknown-cone changes."""
import csv
import itertools
from collections import Counter

import numpy as np

from evaluate import OUT, P, V4, V5, bind, load_module, read, sha, write_csv, write_json

METRICS = OUT / 'BY_VIEW.csv'
LIMIT = 512


def union(items, members):
    return set().union(*(members[i] for i in items))


def saved_margin(fold, seed, arm, point, test_rows, audit):
    if seed == 42:
        file = P / 'heldout_recipe_v5_eval2_20261109' / f'{fold}_{arm}_{point}_testpred.npz'
        with np.load(file) as data:
            ids = np.searchsorted(data['rows'], test_rows)
            assert np.array_equal(data['rows'][ids], test_rows)
            margin = data['scores'][ids]
    else:
        file = V5 / fold / arm / f'seed{seed}' / f'{point}_pred.npz'
        with np.load(file) as data:
            assert np.array_equal(data['test_rows'], test_rows)
            margin = data['test']
    assert sha(file) == audit['scored_prediction_sha256'] and np.isfinite(margin).all()
    return margin


def snapshot(group, margin):
    scores = {i: float(margin[a].max()) for i, (_, a) in group.items()}
    winners = {i: set(a[margin[a] == scores[i]].tolist()) for i, (_, a) in group.items()}
    assert all(winners.values())
    order = sorted(group, key=lambda i: (-scores[i], i))
    return scores, winners, order


def trace(order, members):
    seen = set()
    path = []
    for i in order:
        delta = len(members[i] - seen)
        before = len(seen)
        seen.update(members[i])
        path.append((i, before, delta, len(seen)))
    return path


def validate_snapshot(snap, members, labels, positive, prior):
    scores, _, order = snap
    path = trace(order, members)
    hit = {i for i, _, _, count in path if count <= LIMIT and i in positive}
    threshold = min(scores[i] for i in positive)
    checked = {i for i in order if scores[i] >= threshold}
    counts = Counter(labels[i] for i in checked)
    assert float(prior['recall_512']) == len(hit) / len(positive)
    assert int(prior['gates_512']) == max((count for _, _, _, count in path if count <= LIMIT), default=0)
    assert int(prior['allpos_gates']) == len(union(checked, members))
    assert int(prior['allpos_endpoints']) == len(checked)
    assert int(prior['allpos_unknown']) == counts['unknown']
    return path, hit, checked


def aig_change(key, group, states, replay):
    members = {i: set(a.tolist()) for i, (_, a) in group.items()}
    labels = {i: label for i, (label, _) in group.items()}
    n, nc = (replay[a][2] for a in ('N', 'NC'))
    common = n & nc
    common_gates = union(common, members)
    added, removed = nc - n, n - nc
    pos = {i for i in group if labels[i] == 'positive'}
    gates = {a: union(replay[a][2], members) for a in ('N', 'NC')}
    result = dict(key, n_gates=len(gates['N']), nc_gates=len(gates['NC']),
                  net_gates=len(gates['NC']) - len(gates['N']),
                  only_nc_gates=len(gates['NC'] - gates['N']), only_n_gates=len(gates['N'] - gates['NC']),
                  shared_gates=len(gates['NC'] & gates['N']))
    changed = []
    for arm, action, subset in (('NC', 'added', added), ('N', 'removed', removed)):
        scores, winners, order = states[arm]
        pos_winners = union(pos, winners)
        common_winners = union(common, winners)
        unknown = {i for i in subset if labels[i] == 'unknown'}
        counts = Counter(w for i in unknown for w in winners[i])
        prefix = union(unknown, members)
        result[action] = dict(counts=dict(Counter(labels[i] for i in subset)),
                              unknown_member_occurrences=sum(len(members[i]) for i in unknown),
                              unknown_union=len(prefix), unknown_incremental_vs_common=len(prefix-common_gates),
                              unknown_sharing_positive_max=sum(bool(winners[i] & pos_winners) for i in unknown),
                              unknown_sharing_common_max=sum(bool(winners[i] & common_winners) for i in unknown),
                              unknown_sharing_other_changed_max=sum(any(counts[w] > 1 for w in winners[i]) for i in unknown),
                              unknown_distinct_max_nodes=len(counts),
                              unknown_largest=max((len(members[i]) for i in unknown), default=0))
        for i in sorted(subset):
            other = 'N' if arm == 'NC' else 'NC'
            changed.append(dict(**key, action=action, endpoint=i, label=labels[i],
                                gates=len(members[i]), new_vs_common=len(members[i] - common_gates),
                                rank_N=states['N'][2].index(i)+1, rank_NC=states['NC'][2].index(i)+1,
                                max_score=scores[i], shares_positive_max=bool(winners[i] & pos_winners),
                                shares_common_max=bool(winners[i] & common_winners),
                                shares_other_changed_max=any(counts[w] > 1 for w in winners[i]),
                                max_nodes='|'.join(map(str, sorted(winners[i]))),
                                other_max_nodes='|'.join(map(str, sorted(states[other][1][i])))))
    assert result['net_gates'] == result['only_nc_gates'] - result['only_n_gates']
    return result, changed


def loss_detail(key, group, states, replay):
    members = {i: set(a.tolist()) for i, (_, a) in group.items()}
    labels = {i: label for i, (label, _) in group.items()}
    lost = replay['N'][1] - replay['NC'][1]
    gained = replay['NC'][1] - replay['N'][1]
    rows = []
    for endpoint in sorted(lost):
        row = dict(key, endpoint=endpoint, positive_gates=len(members[endpoint]))
        for arm in ('N', 'NC'):
            scores, winners, order = states[arm]
            path = replay[arm][0]
            at = order.index(endpoint)
            strict = [i for i in order[:at] if scores[i] > scores[endpoint]]
            tied = [i for i in order[:at] if scores[i] == scores[endpoint]]
            blocker_rank = next((j for j, x in enumerate(path) if x[3] > LIMIT), None)
            blocker = order[blocker_rank] if blocker_rank is not None else None
            def describe(i):
                rank = order.index(i)
                _, before, added, after = path[rank]
                return dict(endpoint=i, label=labels[i], rank=rank+1, size=len(members[i]),
                            before=before, incremental=added, after=after)
            row[arm] = dict(positive=describe(endpoint), blocker=describe(blocker) if blocker else None,
                            earlier_higher=len(strict), earlier_ties=len(tied),
                            earlier_sharing_max=sum(bool(winners[i] & winners[endpoint]) for i in order[:at]),
                            earlier_overlap=len(union(order[:at], members) & members[endpoint]),
                            gates_if_positive_first_among_ties=len(union(strict + [endpoint], members)),
                            gates_if_only_first_blocker_removed=(len(union([i for i in order[:at+1] if i != blocker], members))
                                                                 if blocker and blocker != endpoint else None),
                            blocker_shares_max_with_positive=bool(blocker and winners[blocker] & winners[endpoint]),
                            blocker_rank_other=states['NC' if arm == 'N' else 'N'][2].index(blocker)+1 if blocker else None,
                            positive_max_nodes=sorted(winners[endpoint]),
                            blocker_max_nodes=sorted(winners[blocker]) if blocker else [])
        rows.append(row)
    return rows, gained


def main():
    previous = read(OUT / 'SUMMARY.json')
    panel = load_module('frozen_panel', P / 'lcone_endpoint_overlap_20261112/audit.py')
    layouts, truth = panel.load()
    assert sha(panel.FROZEN / 'EVIDENCE.json') == previous['truth_sha256']
    with METRICS.open(encoding='utf-8-sig', newline='') as f:
        prior = {(r['fold'], int(r['seed']), r['arm'], r['point'], r['view'], r['kind']): r for r in csv.DictReader(f)}
    aig, aig_rows, nand = [], [], []
    checked = 0
    for recipe in ('aig', 'nand'):
        fold = 'ys_' + recipe
        asset = V4 / f'{fold}_test_map.npz'
        assert sha(asset) == previous['audits'][recipe]['test_map_sha256']
        with np.load(asset) as data:
            test = {k: data[k] for k in ('rows', 'old2new', 'new2old', 'physical')}
        cases, _ = bind(recipe, layouts, truth, test, {})
        audit = {(r['seed'], r['arm'], r['point']): r for r in previous['audits'][recipe]['runs']}
        for seed, point in itertools.product((42, 1, 2) if recipe == 'aig' else (1,), ('best', 'last')):
            margins = {a: saved_margin(fold, seed, a, point, test['rows'], audit[seed, a, point]) for a in ('N', 'NC')}
            for (view, kind), group in cases.items():
                positive = {i for i, (lab, _) in group.items() if lab == 'positive'}
                if not positive:
                    continue
                key = dict(view=view, kind=kind, seed=seed, point=point)
                states = {a: snapshot(group, m) for a, m in margins.items()}
                members = {i: set(arr.tolist()) for i, (_, arr) in group.items()}
                labels = {i: label for i, (label, _) in group.items()}
                replay = {a: validate_snapshot(s, members, labels, positive, prior[recipe, seed, a, point, view, kind])
                          for a, s in states.items()}
                checked += len(replay)
                if recipe == 'aig':
                    summary, changed = aig_change(key, group, states, replay)
                    aig.append(summary)
                    aig_rows.extend(changed)
                else:
                    lost, gained = loss_detail(key, group, states, replay)
                    assert not gained
                    nand.extend(lost)
    assert len(aig) == 54 and len(nand) == 4 and checked == 144
    write_csv(OUT / 'AIG_CHANGED_ENDPOINTS.csv', aig_rows)
    write_json(OUT / 'MECHANISM.json', dict(aig=aig, nand_seed1_lost=nand, verified_replays=checked,
               source_metrics_sha256=sha(METRICS), forward_passes=0, optimizer_steps=0, sat_cec_calls=0,
               labels_modified=False))


if __name__ == '__main__':
    main()
