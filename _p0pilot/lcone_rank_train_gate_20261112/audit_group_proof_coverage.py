"""Count repeated optimum movements and join frozen functional endpoint evidence."""
import csv
from collections import Counter, defaultdict

from audit import EVIDENCE, OUT, P, read, read_panel, sha, write_csv, write_json
from audit_s35932_group_minimum import CAP, union


def records(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def movement_frequency(groups, fixed, kept):
    gates = {g: i for i, g in enumerate(sorted(union(groups) - fixed))}
    masks = [sum(1 << gates[g] for g in group - fixed) for group in groups]
    room = CAP - len(fixed)
    count, retained = 0, Counter()

    def visit(start, remaining, mask, selected):
        nonlocal count
        if remaining == 0:
            count += 1
            retained.update(selected)
            return
        for i in range(start, len(groups) - remaining + 1):
            added = mask | masks[i]
            if added.bit_count() <= room:
                visit(i+1, remaining-1, added, (*selected, i))

    visit(0, kept, 0, ())
    return count, [count - retained[i] for i in range(len(groups))]


def main():
    minima_path = OUT / 'S35932_MIN_GROUP_MOVES_VERIFIED.csv'
    groups_path = OUT / 'ABC_SHARED_GROUPS.csv'
    minima = records(minima_path)
    groups_file = records(groups_path)
    _, panel = read_panel(verified=True)
    existing = {(r['view'], r['cone_id']): r['evidence'] for r in read(EVIDENCE)
                if r['kind'] == 'D' and r['label'] == 0}
    for r in read(OUT / 'BLOCKER_PROOFS_VERIFIED.json')['records']:
        if r['status'] == 'negative':
            existing[r['view'], r['cone_id']] = 'BDD_and_independent_exhaustive'
    replay = read(OUT / 'D92_PROOF_REPLAY.json')
    assert replay['status'] == 'functional_negative_free_PI_Q' and any(r['status']=='replayed' for r in replay['replays'])
    existing[replay['view'], replay['endpoint']] = 'BDD_and_independent_ITE'

    # Prior panel is an alternate saved inventory. Only identical members can re-use its negative evidence.
    earlier = read(P / 'lcone_head_prep_20261112/TRAIN_ENDPOINTS.json')
    extras = []
    for r in earlier:
        v, c = r['view'], r['cone_id']
        if r['kind'] != 'D' or r['label'] != 0 or c not in panel.get(v, {}):
            continue
        label, members = panel[v][c]
        if r['member_rows'] == members.tolist() and label == 'unknown':
            existing[v, c] = r['evidence']
            extras.append((v, c))

    table, verified_keys, cohorts = [], set(), defaultdict(list)
    for r in minima:
        v, target, ref = (r[k] for k in ('view', 'target', 'reference'))
        groups = [x for x in groups_file if (x['view'], x['target'], x['reference']) == (v, target, ref)]
        view = panel[v]
        fixed = union(set(a.tolist()) for cid, (lab, a) in view.items() if lab == 'positive')
        # The groups CSV has no positive members. Reconstruct the exact prior positive prefix from saved scores.
        cohorts[ref, v].append((r, groups, fixed))
    score_cache = read(OUT / 'ABC_SHARED_SCORE_CACHE.json')
    score = {(r['reference'], r['view'], r['cone']): r['score'] for r in score_cache['rows']}
    for (ref, v), items in cohorts.items():
        view = panel[v]
        for r, groups, _ in items:
            target = r['target']
            order_key = lambda c: (-score[ref, v, c], c)
            fixed = union(set(a.tolist()) for c, (lab, a) in view.items()
                          if lab == 'positive' and order_key(c) <= order_key(target))
            assert len(fixed) == int(r['fixed_positive_gates'])
            cone_groups = [tuple(sorted(x['cones'].split('|'))) for x in groups]
            nodes = [union(set(view[c][1].tolist()) for c in group) for group in cone_groups]
            count, frequency = movement_frequency(nodes, fixed, len(groups)-int(r['min_moves']))
            assert count == int(r['optimum_count']) and sum(frequency) == count*int(r['min_moves'])
            for x, cones, moved in zip(groups, cone_groups, frequency):
                known = {c: existing[v, c] for c in cones if (v, c) in existing}
                status = 'full_negative' if len(known) == len(cones) else 'partial_negative' if known else 'unknown'
                result = dict(reference=ref, view=v, source=r['source'], target=target, group=x['representative'],
                              cones='|'.join(cones), proof_status=status, proofs='|'.join(f'{c}={known[c]}' for c in sorted(known)),
                              optimum_count=count, moved_count=moved, always=moved==count, at_least_90pct=moved*10>=count*9)
                table.append(result)
                if ref == 'v5_best':
                    verified_keys.add((r['source'], cones))

    other = []
    for x in groups_file:
        if x['reference'] != 'v5_best' or not x['source'].startswith('s15850'):
            continue
        v, cones = x['view'], x['cones'].split('|')
        known = sum((v,c) in existing for c in cones)
        assert not known
        other.append(dict(fold='ys_abc', source=x['source'], view=v, target=x['target'], cones=x['cones'],
                          proof_status='unknown', group_moves_restore=False, reason='positive_prefix_alone_over_budget'))
    for r in records(OUT / 'CROSS_HOST_COMPETITORS.csv'):
        if r['fold'] != 'ys_nand' or r['reference'] != 'v5_best' or (r['view'],r['negative']) != (replay['view'],replay['endpoint']) or r['eligible'] != 'True':
            continue
        assert r['negative_rank'] == '1' and float(r['gap']) > 0
        other.append(dict(fold='ys_nand', source=r['source'], view=r['view'], target=r['positive'], cones=r['negative'],
                          proof_status='full_negative', group_moves_restore=True, reason='D92_proof_replay_and_cost_replay'))

    support = defaultdict(Counter)
    for v, view in panel.items():
        for lab, _ in view.values():
            support[v.rsplit('__ys_',1)[0]][lab] += 1
    source_only = read(P / 'lcone_head_protocol_20261112/SOURCE_ONLY_EVIDENCE.json')['results']
    source_only_positive = sorted({x['source'] for x in source_only if any(e['kind']=='D' and e['status']=='positive' for e in x['endpoints'])})
    assert not source_only_positive
    for ref in ('v5_best', 'pilot_last'):
        assert len([r for r in table if r['reference'] == ref]) == 224
    compare = defaultdict(list)
    for row in table:
        compare[row['view'], row['target'], row['group']].append({k:v for k,v in row.items() if k!='reference'})
    assert all(len(items)==2 and items[0]==items[1] for items in compare.values())
    write_csv(OUT / 'GROUP_PROOF_FREQUENCY.csv', table)
    write_csv(OUT / 'GROUP_PROOF_OTHER_SOURCES.csv', other)
    write_json(OUT / 'GROUP_PROOF_COVERAGE.json', dict(source_panel_support=support, exact_member_new_negatives=extras,
               source_only_checked=sorted({r['source'] for r in source_only}), source_only_d_positive=source_only_positive,
               unique_s35932_source_cone_tuples=len(verified_keys), hashes={p.name:sha(p) for p in (minima_path,groups_path,EVIDENCE)},
               forward_passes=0, optimizer_steps=0, sat_cec_calls=0, labels_modified=False))
    for k in sorted({(r['view'],r['target']) for r in table}):
        g = [r for r in table if r['reference']=='v5_best' and (r['view'],r['target'])==k]
        print(k, {tag:dict(Counter(r['proof_status'] for r in g if r[tag])) for tag in ('always','at_least_90pct')}, flush=True)
    print('sources with D positive', [k for k,v in support.items() if v['positive']], 'new joined negatives', extras, 'other records', len(other), flush=True)


if __name__ == '__main__':
    main()
