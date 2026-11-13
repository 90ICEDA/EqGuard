"""Attribute the cost of the frozen abc-fold training endpoint queues."""
import csv
from collections import Counter, defaultdict
from itertools import combinations

import numpy as np
import torch

from audit import OUT, P, V5, load_module, read, read_panel, sha, write_csv, write_json
from run_pilot import RUNS

CAP = 512


def union(members, cones):
    return set().union(*(members[c] for c in cones))


def describe_queue(view, reference, group, scores):
    members = {c: set(rows.tolist()) for c, (_, rows) in group.items()}
    labels = {c: lab for c, (lab, _) in group.items()}
    order = sorted(group, key=lambda c: (-scores[c]['score'], c))
    source = view.rsplit('__ys_', 1)[0]
    positives = [c for c in order if labels[c] == 'positive']
    feasible = [c for c in positives if len(members[c]) <= CAP]
    max_positive_hits = max(k for k in range(len(feasible) + 1)
                            if any(len(union(members, seq)) <= CAP for seq in combinations(feasible, k)))

    used, skip_hits = set(), set()
    for c in order:
        additions = members[c] - used
        if len(used) + len(additions) <= CAP:
            used.update(additions)
            if c in positives:
                skip_hits.add(c)
    rows, blocks = [], []
    for p in positives:
        prior = order[:order.index(p)]
        full = union(members, prior + [p])
        if not len(members[p]) <= CAP < len(full):
            continue
        pos_first = union(members, [c for c in prior if labels[c] == 'positive'])
        pos_union = pos_first | members[p]
        neg = [c for c in prior if labels[c] == 'negative']
        unk = [c for c in prior if labels[c] == 'unknown']
        neg_only = union(members, neg) - pos_union
        unk_only = union(members, unk) - pos_union
        assert len(full) == len(pos_union) + len(neg_only | unk_only)
        # A deterministic max-node representative defines groups of competing cones.
        groups = defaultdict(list)
        for c in neg + unk:
            groups[min(scores[c]['peaks'])].append(c)
        exposure = Counter(pos_union)
        group_nodes = {peak: union(members, cs) for peak, cs in groups.items()}
        for nodes in group_nodes.values():
            exposure.update(nodes)
        for peak, cs in groups.items():
            nodes = group_nodes[peak]
            saved = sum(exposure[n] == 1 for n in nodes)
            blocks.append(dict(reference=reference, view=view, source=source, target=p, representative=peak,
                               cone_count=len(cs), known_negative=sum(labels[c] == 'negative' for c in cs),
                               unknown=sum(labels[c] == 'unknown' for c in cs), member_gates=len(nodes),
                               shared_with_positive=len(nodes & pos_union), shared_other_groups=len(nodes - pos_union) - saved,
                               saved_if_moved=saved, restores_hit=len(full)-saved <= CAP,
                               also_target_max=peak in scores[p]['peaks'], cones='|'.join(sorted(cs))))
        rows.append(dict(reference=reference, view=view, source=source, target=p, rank=len(prior)+1,
                         prefix=len(full), target_gates=len(members[p]), earlier_positive_gates=len(pos_first),
                         shared_with_earlier_positive=len(pos_first & members[p]), positive_union=len(pos_union),
                         negative_exclusive=len(neg_only - unk_only), unknown_exclusive=len(unk_only - neg_only),
                         negative_unknown_shared=len(neg_only & unk_only),
                         nonpositive_group_count=len(groups), multi_cone_group_count=sum(len(cs)>1 for cs in groups.values()),
                         all_prefix_shared_gates=sum(v>1 for v in Counter(n for c in prior+[p] for n in members[c]).values()),
                         needs_saved=len(full)-CAP, skip_oversize_hits=p in skip_hits,
                         max_positives_only_under_cap=max_positive_hits, view_positive_count=len(positives),
                         view_feasible_positive_count=len(feasible)))
    return rows, blocks


def main():
    frozen = read(OUT / 'ABC_BUDGET_PROVENANCE.json')['checkpoints']
    fold = 'ys_abc'
    layouts, all_views = read_panel(verified=True)
    with (OUT / 'ABC_BUDGET_GROUP_REPLAY.csv').open(encoding='utf-8-sig', newline='') as file:
        previous = {(r['reference'], r['view'], r['positive']): r for r in csv.DictReader(file)}
    views = {v: all_views[v] for _, v, _ in previous}
    train = load_module('abc_shared_io', V5 / 'fold_io.py').load_trans(fold)
    model = load_module('abc_shared_model', P / 'control_best200_20261104/evaluate.py').Model().cuda().eval().requires_grad_(False)
    x, edge = (torch.as_tensor(train[k], device='cuda') for k in ('x', 'edge'))
    rows, blocks, score_rows = [], [], []
    for ref, path in (('v5_best', V5 / fold / 'N/best.pt'), ('pilot_last', RUNS / fold / 'N/last.pt')):
        assert sha(path) == frozen[ref]
        model.load_state_dict(torch.load(path, map_location='cpu', weights_only=True), strict=True)
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            logits = model(x, edge).float()
            margin = (logits[:, 1] - logits[:, 0]).cpu().numpy()
        assert np.isfinite(margin).all()
        for view, group in sorted(views.items()):
            assert not view.endswith('__' + fold)
            start, stop = (layouts[view][k] for k in ('start', 'stop'))
            assert (train['old2new'][start:stop] >= 0).all()
            scores = {}
            for cone, (_, physical) in group.items():
                values = margin[train['old2new'][physical]]
                scores[cone] = dict(score=float(values.max()), peaks=physical[values == values.max()].tolist())
                score_rows.append(dict(reference=ref, view=view, cone=cone, **scores[cone]))
            endpoints, groups = describe_queue(view, ref, group, scores)
            rows.extend(endpoints)
            blocks.extend(groups)
    assert len(rows) == len(previous)
    for r in rows:
        old = previous[r['reference'], r['view'], r['target']]
        assert r['prefix'] == int(old['original']) and r['positive_union'] == int(old['positive_only_lower_bound'])
    write_csv(OUT / 'ABC_SHARED_BUDGET.csv', rows)
    write_csv(OUT / 'ABC_SHARED_GROUPS.csv', blocks)
    write_json(OUT / 'ABC_SHARED_SCORE_CACHE.json', dict(checkpoints=frozen, rows=score_rows,
               inference_only=True, labels_modified=False, sat_cec_calls=0))
    print(len(rows), len(blocks), Counter(r['restores_hit'] for r in blocks), flush=True)


if __name__ == '__main__':
    main()
