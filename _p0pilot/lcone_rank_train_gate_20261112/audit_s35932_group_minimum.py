"""Find exact group movements under the frozen 512-gate stop policy."""
import csv
from collections import Counter, defaultdict

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

from audit import OUT, read, read_panel, sha, write_csv, write_json

CAP = 512


def union(items):
    return set().union(*items)


def exact_minimum(groups, fixed, certified):
    """Maximize kept groups. Gates with identical group incidence share a variable."""
    incidence = defaultdict(list)
    for i, gates in enumerate(groups):
        for gate in gates - fixed:
            incidence[gate].append(i)
    signatures = Counter(tuple(x) for x in incidence.values())
    n = len(groups)
    columns = n + len(signatures)
    matrix = lil_matrix((sum(map(len, signatures)) + 1, columns))
    row = 0
    for col, (owners, weight) in enumerate(signatures.items(), n):
        for i in owners:
            matrix[row, i] = 1
            matrix[row, col] = -1
            row += 1
        matrix[-1, col] = weight
    upper = np.zeros(row + 1)
    upper[-1] = CAP - len(fixed)
    constraints = LinearConstraint(matrix.tocsr(), -np.inf, upper)
    kept_indicator = np.r_[np.ones(n), np.zeros(columns - n)]
    cert_indicator = np.r_[np.asarray(certified, dtype=float), np.zeros(columns - n)]

    def solve(objective, extra=None):
        restrictions = [constraints] if extra is None else [constraints, extra]
        result = milp(objective, integrality=np.ones(columns), bounds=Bounds(0, 1),
                      constraints=restrictions, options={'mip_rel_gap': 0.0, 'time_limit': 45.0})
        assert result.success and abs(result.fun - result.mip_dual_bound) < 1e-6, result.message
        kept = {i for i, value in enumerate(result.x[:n]) if value > 0.5}
        assert len(fixed | union(groups[i] for i in kept)) <= CAP
        return kept, dict(objective=result.fun, dual_bound=result.mip_dual_bound)

    kept, primary = solve(-kept_indicator)
    exact = LinearConstraint(kept_indicator, len(kept), len(kept))
    keep_most_cert, least_move = solve(-cert_indicator, exact)
    keep_fewest_cert, most_move = solve(cert_indicator, exact)
    return keep_most_cert, keep_fewest_cert, dict(cardinality=primary, min_certified_moves=least_move,
                                                 max_certified_moves=most_move)


def stop_at(order, members):
    checked, covered = [], set()
    for c in order:
        updated = covered | members[c]
        if len(updated) > CAP:
            break
        covered = updated
        checked.append(c)
    return checked


def enumerate_optima(groups, fixed, kept_count, certified, mixed):
    """Cross-check the cardinality bound directly on gate unions."""
    variables = sorted(union(groups) - fixed)
    positions = {g: i for i, g in enumerate(variables)}
    masks = [sum(1 << positions[g] for g in group - fixed) for group in groups]
    room = CAP - len(fixed)

    def search(start, needed, mask, selected):
        if not needed:
            yield selected
            return
        for i in range(start, len(groups) - needed + 1):
            updated = mask | masks[i]
            if updated.bit_count() <= room:
                yield from search(i+1, needed-1, updated, (*selected, i))

    assert next(search(0, kept_count+1, 0, ()), None) is None
    ranges = [(sum(certified)-sum(certified[i] for i in kept),
               sum(mixed)-sum(mixed[i] for i in kept)) for kept in search(0, kept_count, 0, ())]
    assert ranges
    cert_counts, mixed_counts = zip(*ranges)
    return min(cert_counts), max(cert_counts), min(mixed_counts), max(mixed_counts), len(ranges)


def main():
    score_path = OUT / 'ABC_SHARED_SCORE_CACHE.json'
    proof_path = OUT / 'ABC_SHARED_GROUPS.csv'
    cache = read(score_path)
    assert cache['checkpoints'] == read(OUT / 'ABC_BUDGET_PROVENANCE.json')['checkpoints']
    _, panel = read_panel(verified=True)
    by_view = defaultdict(dict)
    for r in cache['rows']:
        if r['view'].startswith('s35932'):
            by_view[r['reference'], r['view']][r['cone']] = r
    prior = defaultdict(dict)
    with proof_path.open(encoding='utf-8-sig', newline='') as handle:
        for r in csv.DictReader(handle):
            if r['view'].startswith('s35932'):
                prior[r['reference'], r['view'], r['target']][int(r['representative'])] = r
    rows, witnesses = [], []
    for (reference, view), scores in sorted(by_view.items()):
        group = panel[view]
        assert scores.keys() == group.keys() and not view.endswith('__ys_abc')
        labels = {c: lab for c, (lab, _) in group.items()}
        members = {c: set(a.tolist()) for c, (_, a) in group.items()}
        order = sorted(group, key=lambda c: (-scores[c]['score'], c))
        original = stop_at(order, members)
        for target in (c for c in order if labels[c] == 'positive'):
            preceding = order[:order.index(target)]
            fixed = members[target] | union(members[c] for c in preceding if labels[c] == 'positive')
            by_peak = defaultdict(list)
            for c in preceding:
                if labels[c] != 'positive':
                    by_peak[min(scores[c]['peaks'])].append(c)
            peaks = sorted(by_peak)
            old = prior[reference, view, target]
            assert old.keys() == by_peak.keys() and all(set(old[k]['cones'].split('|')) == set(by_peak[k]) for k in peaks)
            assert target not in original and len(fixed) <= CAP
            groups = [union(members[c] for c in by_peak[k]) for k in peaks]
            certified = [all(labels[c] == 'negative' for c in by_peak[k]) for k in peaks]
            mixed = [not ok and any(labels[c] == 'negative' for c in by_peak[k]) for k, ok in zip(peaks, certified)]
            most_kept_cert, least_kept_cert, solver = exact_minimum(groups, fixed, certified)
            cert_counts, witness, costs = [], [], []
            for keep in (most_kept_cert, least_kept_cert):
                moved = [i for i in range(len(peaks)) if i not in keep]
                moved_cones = {c for i in moved for c in by_peak[peaks[i]]}
                reranked = [c for c in preceding if c not in moved_cones] + [target]
                reranked += [c for c in preceding if c in moved_cones] + order[order.index(target)+1:]
                assert set(reranked) == set(order) and target in stop_at(reranked, members)
                costs.append(len(union(members[c] for c in reranked[:reranked.index(target)+1])))
                cert_counts.append(sum(certified[i] for i in moved))
                witness.append(dict(moved_groups=[dict(peak=peaks[i], cones=by_peak[peaks[i]],
                                   certified=certified[i], mixed=mixed[i]) for i in moved], prefix_gates=costs[-1]))
            assert len(most_kept_cert) == len(least_kept_cert) and cert_counts[0] <= cert_counts[1]
            n = len(peaks)
            min_moves = n - len(most_kept_cert)
            cert_min, cert_max, mixed_min, mixed_max, optima = enumerate_optima(
                groups, fixed, len(most_kept_cert), certified, mixed)
            assert (cert_min, cert_max) == tuple(cert_counts)
            source = view.rsplit('__ys_', 1)[0]
            rows.append(dict(reference=reference, view=view, source=source, target=target, rank=len(preceding)+1,
                             fixed_positive_gates=len(fixed), prefix_gates=len(fixed | union(groups)),
                             groups=n, certified_groups=sum(certified), mixed_groups=sum(mixed),
                             unknown_only_groups=n-sum(certified)-sum(mixed), min_moves=min_moves,
                             min_certified_moved=cert_counts[0], max_certified_moved=cert_counts[1],
                             min_mixed_moved=mixed_min, max_mixed_moved=mixed_max, optimum_count=optima,
                             min_not_fully_certified_moved=min_moves-cert_counts[1],
                             only_certified_moved_gates=len(fixed | union(g for g, c in zip(groups, certified) if not c))))
            witnesses.append(dict(reference=reference, view=view, target=target, solver=solver, witnesses=witness))
    assert len(rows) == 14
    write_csv(OUT / 'S35932_MIN_GROUP_MOVES_VERIFIED.csv', rows)
    write_json(OUT / 'S35932_MIN_GROUP_WITNESSES_VERIFIED.json', dict(results=witnesses, score_sha256=sha(score_path),
               group_sha256=sha(proof_path), forward_passes=0, optimizer_steps=0, sat_cec_calls=0, labels_modified=False))
    for r in rows:
        if r['reference'] == 'v5_best':
            print(r, flush=True)


if __name__ == '__main__':
    main()
