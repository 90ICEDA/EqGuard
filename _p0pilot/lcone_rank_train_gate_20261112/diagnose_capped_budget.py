"""Trace the nand capped-BCE budget results using only saved scores."""
import csv
import itertools

import numpy as np

from audit import OUT, read, sha, write_csv, write_json
from diagnose_pilot import FOLD, describe, load_cases, snapshot

CAP = 512
ARMS = ('N', 'NC-BCE', 'NC-BCE-Cap')


def trace(group, margin):
    scores, winners, order = snap = snapshot(group, margin)
    gates = set()
    blocker = None
    for cid in order:
        total = gates.union(group[cid][1])
        if len(total) > CAP:
            blocker = describe(cid, snap, group)
            break
        gates = total
    positives = []
    for cid, (label, members) in sorted(group.items()):
        if label != 'positive':
            continue
        d = describe(cid, snap, group)
        d['hit'] = d['after'] <= CAP
        if d['hit']:
            reason = 'hit'
        elif d['size'] > CAP:
            reason = 'positive_alone_over_budget'
        elif d['gates_if_first_among_ties'] > CAP:
            reason = 'strictly_higher_prefix_over_budget'
        else:
            reason = 'same_score_order_blocks'
        d['reason'] = reason
        prefix = order[:d['rank']-1]
        if blocker and blocker['endpoint'] in prefix:
            d['gates_without_first_blocker'] = len(set(members).union(
                *(group[p][1] for p in prefix if p != blocker['endpoint'])))
        else:
            d['gates_without_first_blocker'] = None
        positives.append(d)
    return positives, blocker


def structural_ceiling(group):
    pos = [set(a.tolist()) for label, a in group.values() if label == 'positive']
    assert len(pos) <= 5
    for n in range(len(pos), -1, -1):
        costs = [len(set().union(*items)) for items in itertools.combinations(pos, n)]
        if min(costs) <= CAP:
            return dict(positive=len(pos), maximum_hits=n, minimum_gates=min(costs))


def main():
    _, _, cases = load_cases()
    paths = {'baseline': OUT / 'PILOT_TEST_MARGINS.npz', 'candidate': OUT / 'PILOT_CAPPED_TEST_MARGINS.npz'}
    summary = read(OUT / 'PILOT_CAPPED_FROZEN_RESULTS.json')
    assert summary['frozen_score_hashes'] == {k: sha(p) for k, p in paths.items()}
    with (OUT / 'PILOT_CAPPED_FROZEN_ENDPOINTS.csv').open(encoding='utf-8-sig', newline='') as f:
        old = {(r['view'].split('__')[1], r['arm'], r['point']): r for r in csv.DictReader(f)
               if r['fold'] == FOLD and r['kind'] == 'D'}
    scores = {}
    for key, path in paths.items():
        with np.load(path) as z:
            for name in z.files:
                if name.startswith(FOLD) and (('NC-BCE-Cap' in name) == (key == 'candidate')):
                    scores[name] = z[name]
    rows, blockers = [], []
    for source, group in sorted(cases.items()):
        for arm, point in itertools.product(ARMS, ('best', 'last')):
            positives, blocker = trace(group, scores[f'{FOLD}_{arm}_{point}'])
            if not positives:
                continue
            assert sum(r['hit'] for r in positives) / len(positives) == float(old[source, arm, point]['recall_512'])
            base = dict(source=source, arm=arm, point=point)
            rows.extend(dict(base, **r) for r in positives)
            blockers.append(dict(base, **blocker))
    assert len(rows) == 60 and len(blockers) == 24
    keyed = {(r['source'], r['endpoint'], r['arm'], r['point']): r for r in rows}
    changes = []
    for r in rows:
        if r['arm'] != 'NC-BCE-Cap':
            continue
        for baseline in ARMS[:2]:
            b = keyed[r['source'], r['endpoint'], baseline, r['point']]
            changes.append(dict(source=r['source'], endpoint=r['endpoint'], point=r['point'], baseline=baseline,
                                baseline_hit=b['hit'], capped_hit=r['hit'], rank_delta=r['rank']-b['rank'],
                                added_gate_delta=r['added']-b['added'], total_gate_delta=r['after']-b['after']))
    write_csv(OUT / 'CAPPED_NAND_POSITIVE_TRACE.csv', rows)
    write_csv(OUT / 'CAPPED_NAND_FIRST_BLOCKERS.csv', blockers)
    write_csv(OUT / 'CAPPED_NAND_POSITIVE_CHANGES.csv', changes)
    write_json(OUT / 'CAPPED_NAND_BUDGET_DIAGNOSIS.json', dict(source_ceiling={s: structural_ceiling(g) for s, g in cases.items()},
               positive_records=len(rows), paired_records=len(changes), predictions_sha256=summary['frozen_score_hashes'],
               optimizer_steps=0, forward_passes=0, sat_cec_calls=0, labels_modified=False))


if __name__ == '__main__':
    main()
