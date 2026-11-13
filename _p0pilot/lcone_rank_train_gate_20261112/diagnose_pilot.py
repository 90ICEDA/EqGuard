"""Replay the pilot queue and trace score, membership and winner changes."""
import itertools
from collections import Counter

import numpy as np

from audit import OUT, P, V5, load_module, read, sha, write_json
from replay import endpoint_metrics
from run_pilot import ARMS

FOLD = 'ys_nand'


def snapshot(group, margin):
    scores = {cid: float(margin[rows].max()) for cid, (_, rows) in group.items()}
    winners = {cid: set(rows[margin[rows] == scores[cid]].tolist()) for cid, (_, rows) in group.items()}
    order = sorted(group, key=lambda cid: (-scores[cid], cid))
    return scores, winners, order


def describe(cid, snap, group):
    scores, winners, order = snap
    preceding = order[:order.index(cid)]
    gates = set().union(*(group[p][1] for p in preceding))
    members = set(group[cid][1])
    higher = [p for p in preceding if scores[p] > scores[cid]]
    return dict(endpoint=cid, label=group[cid][0], rank=len(preceding)+1, score=scores[cid],
                winners=sorted(winners[cid]), size=len(members), before=len(gates), added=len(members-gates),
                after=len(gates|members), higher=len(higher), tied_before=len(preceding)-len(higher),
                sharing_max_before=sum(bool(winners[p] & winners[cid]) for p in preceding),
                gates_if_first_among_ties=len(set().union(members, *(group[p][1] for p in higher))))


def gamma(group, margin):
    snap = snapshot(group, margin)
    metrics = endpoint_metrics(group, margin)
    gates = set()
    for cid in snap[2]:
        enlarged = gates.union(group[cid][1])
        if len(enlarged) > 512:
            blocker = describe(cid, snap, group)
            break
        gates = enlarged
    positive = [describe(cid, snap, group) for cid, (label, _) in group.items() if label == 'positive']
    assert len(positive) == 1 and (positive[0]['after'] <= 512) == bool(metrics['recall_512'])
    return dict(positive=positive[0], first_blocker=blocker, metrics=metrics)


def delta(group, margins):
    snapshots = {a: snapshot(group, margin) for a, margin in margins.items()}
    metrics = {a: endpoint_metrics(group, margin) for a, margin in margins.items()}
    positive = [cid for cid, (label, _) in group.items() if label == 'positive']
    cut, sets = {}, {}
    for a, (scores, _, order) in snapshots.items():
        cutoff = min(scores[c] for c in positive)
        low = next(c for c in reversed(order) if c in positive)
        cut[a] = describe(low, snapshots[a], group)
        sets[a] = {c for c, (lab, _) in group.items() if lab == 'negative' and scores[c] >= cutoff}
        assert len(sets[a]) == metrics[a]['allpos_fp']
    result = {}
    rs, rw, _ = snapshots['NC-Rank']
    for baseline in ('N', 'NC-BCE'):
        bs, _, _ = snapshots[baseline]
        added = sets['NC-Rank'] - sets[baseline]
        removed = sets[baseline] - sets['NC-Rank']
        counts = Counter(w for c in added for w in rw[c])
        cluster = [dict(row=w, count=n, endpoints=sorted(c for c in added if w in rw[c]))
                   for w, n in counts.most_common()]
        result[baseline] = dict(added=len(added), removed=len(removed),
             added_before_or_equal_old_cut=sum(rs[c] >= cut[baseline]['score'] for c in added),
             added_score_increases=sum(rs[c] > bs[c] for c in added),
             added_sharing_lowest_positive_max=sum(bool(rw[c] & set(cut['NC-Rank']['winners'])) for c in added),
             added_sharing_other_added_max=sum(any(counts[w] > 1 for w in rw[c]) for c in added),
             max_clusters=cluster, added_endpoints=[dict(endpoint=c, before_score=bs[c], after_score=rs[c],
                 winners=sorted(rw[c])) for c in sorted(added)], removed_endpoints=sorted(removed))
    return dict(lowest_positive=cut, metrics=metrics, comparison=result)


def load_cases():
    panel = load_module('endpoint_panel', P / 'lcone_endpoint_overlap_20261112/audit.py')
    layouts, truth = panel.load()
    prior = load_module('endpoint_v5', P / 'heldout_v5_endpoint_replay_20261112/evaluate.py')
    io = load_module('pilot_io', V5 / 'fold_io.py')
    test = io.load_trans(FOLD, 'test')
    cases, _ = prior.bind('nand', layouts, truth, test, {})
    return io, test, {v.split('__')[1]: group for (v, kind), group in cases.items() if kind == 'D'}


def main():
    _, _, cases = load_cases()
    path = OUT / 'PILOT_TEST_MARGINS.npz'
    with np.load(path) as data:
        result = {}
        for point in ('best', 'last'):
            margins = {arm: data[f'{FOLD}_{arm}_{point}'] for arm in ARMS}
            result[point] = dict(gamma={a: gamma(cases['injgamma_d1_s42'], m) for a, m in margins.items()},
                                 delta=delta(cases['injdelta_d1_s42'], margins))
    write_json(OUT / 'PILOT_MECHANISM.json', dict(points=result, margins_sha256=sha(path),
                                                optimizer_steps=0, sat_cec_calls=0, labels_modified=False))


if __name__ == '__main__':
    main()
