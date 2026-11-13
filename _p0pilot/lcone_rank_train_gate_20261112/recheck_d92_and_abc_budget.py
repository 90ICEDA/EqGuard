"""Replay an existing Boolean proof and audit training-side endpoint queue costs."""
import argparse
import csv
from collections import Counter
from functools import cache
from pathlib import Path

import numpy as np
import torch

from audit import CACHE, OUT, P, V5, load_module, read, read_panel, sha, write_csv, write_json
from run_pilot import RUNS
from verify_blockers import LogicOnlyPath, panel

VIEW = 's15850t100__injepsilon_d1_s42__ys_abc'
ENDPOINT = 'D:DFF_92_Q_reg'


def replay_ite(expressions, roots, order):
    """Independently check the prior roots using ternary Shannon recurrence."""
    level = {name: i for i, name in enumerate(order)}
    terminal = len(order)
    nodes = [(terminal, 0, 0), (terminal, 1, 1)]

    @cache
    def make(i, lo, hi):
        if lo == hi:
            return lo
        if len(nodes) >= 160_000:
            raise OverflowError('Shannon replay node limit')
        nodes.append((i, lo, hi))
        return len(nodes) - 1

    def branch(node, i, side):
        return nodes[node][side] if nodes[node][0] == i else node

    @cache
    def ite(c, t, f):
        if c == 0 or t == f:
            return f
        if c == 1:
            return t
        if (t, f) == (1, 0):
            return c
        i = min(nodes[c][0], nodes[t][0], nodes[f][0])
        return make(i, ite(*(branch(n, i, 1) for n in (c, t, f))),
                    ite(*(branch(n, i, 2) for n in (c, t, f))))

    @cache
    def check(i):
        op, *a = expressions.nodes[i]
        if op == 'var':
            return make(level[a[0]], 0, 1)
        if op == 'const':
            return a[0]
        args = [check(n) for n in a]
        if op == '~':
            return ite(args[0], 0, 1)
        if op == '&':
            return ite(args[0], args[1], 0)
        if op == '|':
            return ite(args[0], 1, args[1])
        if op == '^':
            return ite(args[0], ite(args[1], 0, 1), args[1])
        if op == '?':
            return ite(*args)
        raise ValueError(op)

    return [check(r) for r in roots], len(nodes)


def proof():
    prior_path = OUT / 'CROSS_HOST_PAIR_AUDIT.json'
    prior, = read(prior_path)['proofs']
    assert prior['view'] == VIEW and prior['cone_id'] == ENDPOINT and len(set(prior['bdd_roots'])) == 1
    spec, = [r for r in read(P / 'lcone_head_prep_20261112/all_eligible/SELECTION.json')['data'] if r['view'] == VIEW]
    assert spec['cec']['cec_status'] == 'PASS' and spec['cec']['unproven'] == '0'
    files = [Path(p) for p in spec['files']]
    assert [sha(p) for p in files] == spec['sha256']
    graphs = [panel.endpoints(LogicOnlyPath(p)) for p in files[:3]]
    _, replacements, _ = panel.bind_lineage(spec['provenance'], *graphs[:2])
    states, restored, _ = panel.binding(*graphs, replacements)
    identity = ENDPOINT[2:]
    assert identity in states
    nets = [dict(g[0]['pins'][identity][1])['D'] for g in graphs]
    expressions = panel.Expressions()
    results = [panel.construct(g, expressions, states)(n) for g, n in zip(graphs, nets)]
    roots = [r[0] for r in results]
    inputs = [sorted(expressions.inputs(root)) for root in roots]
    union = sorted(set().union(*map(set, inputs)))
    assert len(union) == prior['inputs'] == 141
    assert all(v[2:] in states for v in union if v.startswith('Q:'))
    assert all(v[3:] in set().union(*g[1].values()) for v in union if v.startswith('PI:') for g in graphs)
    with CACHE.open(encoding='utf-8-sig', newline='') as f:
        cached, = [r for r in csv.DictReader(f) if r['view'] == VIEW and r['cone_id'] == ENDPOINT and r['split'] == 'train']
    graph = graphs[-1][0]
    assert graph['find'](nets[-1]) == graph['find'](cached['endpoint'])
    assert graph['drivers'][graph['find'](nets[-1])] == {cached['driver']}
    assert list(map(int, cached['phys_rows'].split('|'))) == prior['member_rows']
    assert all(panel.structural_cone(g, n) == (set(r[1]), []) for g, n, r in zip(graphs, nets, results))

    check = panel.Expressions()
    x, y = (check.make('var', v) for v in ('x', 'y'))
    nx = check.make('~', x)
    xor = check.make('^', x, y)
    mux = check.make('?', x, check.make('~', y), y)
    roots_small = [xor, mux, x, nx, check.make('&', x, y), check.make('|', x, y), check.make('~', y)]
    ids, _ = replay_ite(check, roots_small, ['y', 'x'])
    truth = check.evaluator({'x': 0b1010, 'y': 0b1100}, 0b1111)
    assert all((ids[i] == ids[j]) == (truth(a) == truth(b))
               for i, a in enumerate(roots_small) for j, b in enumerate(roots_small))
    complemented = expressions.make('~', roots[-1])
    records = []
    for name, order in (('sorted', union), ('reversed', union[::-1])):
        try:
            ids, count = replay_ite(expressions, roots + [complemented], order)
        except OverflowError:
            records.append(dict(order=name, status='node_limit'))
            continue
        assert len(set(ids[:3])) == 1 and ids[-1] != ids[0]
        records.append(dict(order=name, status='replayed', roots=ids, nodes=count))
    assert any(r['status'] == 'replayed' for r in records)
    output = dict(view=VIEW, endpoint=ENDPOINT, status='functional_negative_free_PI_Q', physical_d_nets=nets,
                  variables=union, per_side_variables=inputs, restored_boundary_q=[r for r in restored if 'Q:'+r['register'] in union],
                  prior_sha256=sha(prior_path), file_hashes=spec['sha256'], replays=records,
                  shared_parser_and_boundaries=True, sat_cec_calls=0, labels_modified=False)
    write_json(OUT / 'D92_PROOF_REPLAY.json', output)
    print(Counter(v.split(':')[0] for v in union), nets, records, flush=True)


def queue():
    fold = 'ys_abc'
    layouts, panel_rows = read_panel(verified=True)
    train = load_module('v5_abc_budget', V5 / 'fold_io.py').load_trans(fold)
    model = load_module('v5_budget_model', P / 'control_best200_20261104/evaluate.py').Model().cuda().eval().requires_grad_(False)
    x, edge = (torch.as_tensor(train[k], device='cuda') for k in ('x', 'edge'))
    results, audits, grouped, hashes = [], [], [], {}
    for ref, path in (('v5_best', V5 / fold / 'N/best.pt'), ('pilot_last', RUNS / fold / 'N/last.pt')):
        model.load_state_dict(torch.load(path, map_location='cpu', weights_only=True), strict=True)
        hashes[ref] = sha(path)
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
            logits = model(x, edge).float()
            margin = (logits[:, 1] - logits[:, 0]).cpu().numpy()
        assert np.isfinite(margin).all()
        for view, group in sorted(panel_rows.items()):
            if view.endswith('__' + fold) or not any(lab == 'positive' for lab, _ in group.values()):
                continue
            layout = layouts[view]
            assert (train['old2new'][layout['start']:layout['stop']] >= 0).all()
            nodes = {c: set(rows.tolist()) for c, (_, rows) in group.items()}
            values = {c: margin[train['old2new'][rows]] for c, (_, rows) in group.items()}
            score = {c: float(v.max()) for c, v in values.items()}
            peaks = {c: set(rows[values[c] == score[c]].tolist()) for c, (_, rows) in group.items()}
            order = sorted(group, key=lambda c: (-score[c], c))
            seen, prefix, exposure = set(), [], Counter()
            for i, positive in enumerate(order):
                additions = len(nodes[positive] - seen)
                prefix.append((positive, additions))
                seen.update(nodes[positive])
                exposure.update(nodes[positive])
                if group[positive][0] != 'positive':
                    continue
                src = view.rsplit('__ys_', 1)[0]
                status = 'hit' if len(seen) <= 512 else 'alone_over' if len(nodes[positive]) > 512 else 'feasible_miss'
                audits.append(dict(reference=ref, view=view, source=src, positive=positive, rank=i+1,
                                   size=len(nodes[positive]), gates=len(seen), status=status))
                if status != 'feasible_miss':
                    continue
                verified_ahead = {c for c, _ in prefix[:-1] if group[c][0] == 'negative' and score[c] > score[positive]}
                verified_kept = set().union(*(nodes[c] for c, _ in prefix if c not in verified_ahead))
                positive_kept = set().union(*(nodes[c] for c, _ in prefix if group[c][0] == 'positive'))
                grouped.append(dict(reference=ref, view=view, source=src, positive=positive, original=len(seen),
                                    verified_ahead=len(verified_ahead), without_all_verified_strict=len(verified_kept),
                                    positive_only_lower_bound=len(positive_kept)))
                for j, (neg, incremental) in enumerate(prefix[:-1], 1):
                    if not incremental or group[neg][0] == 'positive':
                        continue
                    saved = sum(exposure[n] == 1 for n in nodes[neg])
                    if not saved:
                        continue
                    results.append(dict(reference=ref, view=view, source=src, positive=positive, competitor=neg,
                                        status=group[neg][0], positive_rank=i+1, competitor_rank=j,
                                        gap=score[neg]-score[positive], shared_peak=bool(peaks[positive] & peaks[neg]),
                                        original=len(seen), without=len(seen)-saved, net_saved=saved,
                                        restores_hit=len(seen)-saved <= 512))
    for name, records in [('ENDPOINTS', audits), ('COMPETITORS', results), ('GROUP_REPLAY', grouped)]:
        path = OUT / f'ABC_BUDGET_{name}.csv'
        if path.exists():
            with path.open(encoding='utf-8-sig', newline='') as handle:
                assert list(csv.DictReader(handle)) == [{k: str(v) for k, v in r.items()} for r in records]
        else:
            write_csv(path, records)
    path = OUT / 'ABC_BUDGET_PROVENANCE.json'
    provenance = dict(checkpoints=hashes, training_only=True, sat_cec_calls=0, labels_modified=False, optimizer_steps=0)
    if path.exists():
        assert read(path) == provenance
    else:
        write_json(path, provenance)
    for ref in hashes:
        print(ref, Counter(r['status'] for r in audits if r['reference'] == ref), flush=True)
        for r in results:
            if r['reference'] == ref and r['restores_hit']:
                print(r, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('task', choices=['proof', 'queue'])
    {'proof': proof, 'queue': queue}[parser.parse_args().task]()
