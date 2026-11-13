"""Replay existing C2 checkpoints against the frozen functional endpoint panel."""
import csv
import hashlib
import importlib.util
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score

OUT = Path(__file__).resolve().parent
P = OUT.parent
C2 = P / 'c2_heldout_20261111'
BOUNDARY = P / 'control_boundary_v3_20261104'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_csv(path, rows):
    with path.open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def bind_test(fold, test, layouts, panel, original):
    build = read(C2 / f'{fold}_build.json')
    for key in ('mean', 'std'):
        assert np.array_equal(test[key], np.array(build[key], dtype=test[key].dtype))
        with np.load(C2 / f'{fold}_train.npz') as train:
            assert np.array_equal(test[key], train[key])
    assert np.all(test['std'] > 0)
    row_map = np.full(len(original['y']), -1, dtype=np.int64)
    cases = {}
    for view, start, stop in zip(test['view'], test['start'], test['stop']):
        layout = layouts[view]
        assert view.endswith('__' + fold) and stop - start == layout['stop'] - layout['start']
        global_rows = slice(layout['start'], layout['stop'])
        row_map[global_rows] = np.arange(start, stop)
        for key in ('x', 'y', 'physical', 'trusted'):
            assert np.array_equal(test[key][start:stop], original[key][global_rows]), (view, key)
        for kind in ('D', 'PO'):
            bound = {}
            for name, (label, members) in panel[view, kind].items():
                local = row_map[members]
                assert len(local) and np.all((local >= start) & (local < stop))
                assert test['physical'][local].all()
                bound[name] = label, local
            assert bound, (view, kind)
            cases[str(view), kind] = bound
    assert np.array_equal(np.sort(row_map[row_map >= 0]), np.arange(len(test['y'])))
    edge = original['edge']
    selected = (row_map[edge[0]] >= 0) & (row_map[edge[1]] >= 0)
    assert np.array_equal(test['edge'], row_map[edge[:, selected]])
    return cases


def endpoint_metrics(cases, margin):
    values = {name: float(margin[members].max()) for name, (_, members) in cases.items()}
    rank = sorted(cases, key=lambda name: (-values[name], name))
    support = Counter(label for label, _ in cases.values())
    pos = support['positive']
    top = {f'top_{k}': (sum(cases[n][0] == 'positive' for n in rank[:k]) / pos if pos else None)
           for k in (1, 5, 10)}
    covered, found = set(), 0
    for name in rank:
        new_gates = set(cases[name][1]) - covered
        if len(covered) + len(new_gates) > 512:
            break
        covered.update(new_gates)
        found += cases[name][0] == 'positive'
    selected = []
    cutoff = None
    if pos:
        cutoff = min(values[n] for n, (label, _) in cases.items() if label == 'positive')
        selected = [n for n in rank if values[n] >= cutoff]
    checks = Counter(cases[n][0] for n in selected)
    assert checks['positive'] == pos
    gate_count = len(set().union(*(cases[n][1] for n in selected)))
    if pos:
        assert gate_count == len(np.unique(np.concatenate([cases[n][1] for n in selected])))
        assert sum(checks.values()) == len(selected)
    return dict(positive=pos, negative=support['negative'], unknown=support['unknown'], **top,
                recall_512=found / pos if pos else None, gates_512=len(covered),
                allpos_threshold=cutoff, allpos_fp=checks['negative'] if pos else None,
                allpos_unknown=checks['unknown'] if pos else None,
                allpos_endpoints=len(selected) if pos else None, allpos_gates=gate_count if pos else None)


FIELDS = ('top_1', 'top_5', 'top_10', 'recall_512', 'allpos_fp', 'allpos_unknown',
          'allpos_endpoints', 'allpos_gates')


def summarize(rows):
    pairs = defaultdict(dict)
    for r in rows:
        if r['positive']:
            key = tuple(r[k] for k in ('variant', 'fold', 'kind', 'point', 'seed', 'source'))
            assert r['arm'] not in pairs[key]
            pairs[key][r['arm']] = r
    groups = defaultdict(list)
    paired = []
    for key, arms in sorted(pairs.items()):
        n, nc = arms['N'], arms['NC']
        assert all(n[k] == nc[k] for k in ('view', 'positive', 'negative', 'unknown'))
        row = dict(zip(('variant', 'fold', 'kind', 'point', 'seed', 'source'), key))
        row.update({f'{arm}_{metric}': arms[arm][metric] for arm in arms for metric in FIELDS})
        row.update({f'delta_{metric}': nc[metric] - n[metric] for metric in FIELDS})
        paired.append(row)
        groups[key[:4]].append(row)
    result = []
    for key, items in sorted(groups.items()):
        seeds = sorted({r['seed'] for r in items})
        sources = sorted({r['source'] for r in items})
        assert len(items) == len(seeds) * len(sources) and len(seeds) == 3
        row = dict(zip(('variant', 'fold', 'kind', 'point'), key), sources=sources)
        row['metrics'] = {}
        for metric in FIELDS:
            by_seed = [{k: statistics.mean(r[f'{k}_{metric}'] for r in items if r['seed'] == seed)
                        for k in ('N', 'NC', 'delta')} for seed in seeds]
            row['metrics'][metric] = {k: statistics.mean(s[k] for s in by_seed) for k in by_seed[0]}
            row['metrics'][metric]['seed_delta'] = {seed: s['delta'] for seed, s in zip(seeds, by_seed)}
        result.append(row)
    return paired, result


def main():
    assert torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    model_module = load_module('frozen_c2_model', P / 'control_best200_20261104/evaluate.py')
    endpoint_panel = load_module('frozen_endpoint_panel', P / 'lcone_endpoint_overlap_20261112/audit.py')
    layouts, panel = endpoint_panel.load()
    input_dir = BOUNDARY / 'inputs/trans_test'
    files = dict(x='x39', y='y', physical='physical', trusted='trusted', edge='edge_index')
    original = {k: np.load(input_dir / f'{v}.npy', mmap_mode='r') for k, v in files.items()}
    model = model_module.Model().cuda().eval()
    assert sum(p.numel() for p in model.parameters()) == 46620
    model.requires_grad_(False)
    rows, assets, verification = [], {}, []
    for recipe in ('abc', 'aig', 'nand'):
        fold = 'ys_' + recipe
        test_path = C2 / f'{fold}_test.npz'
        with np.load(test_path) as data:
            test = {key: data[key] for key in data.files}
        cases = bind_test(fold, test, layouts, panel, original)
        assets[recipe] = dict(sha256=sha(test_path), views=test['view'].tolist(),
                              cone_view_fields=Counter(np.load(C2 / f'{fold}_cones.npz')['view'].tolist()))
        x = test['x'].copy()
        x[:, 25:] = np.clip((x[:, 25:] - test['mean']) / test['std'], -10, 10)
        x = torch.as_tensor(x, device='cuda')
        edge = torch.as_tensor(test['edge'], device='cuda')
        for variant, directory in (('max', 'runs'), ('p90', 'runs_p90')):
            for seed in (42, 1, 2):
                for arm in ('N', 'NC'):
                    run = C2 / directory / f'{fold}_{arm}_s{seed}'
                    reference = read(run / 'EVAL.json')
                    for point in ('best', 'last'):
                        path = run / f'{point}_resume.pt'
                        checkpoint = torch.load(path, map_location='cpu', weights_only=True)
                        assert (checkpoint['fold'], checkpoint['arm'], checkpoint['seed'], checkpoint['completed']) == (fold, arm, seed, 200)
                        assert checkpoint['best_step'] == reference[point]['best_step']
                        model.load_state_dict(checkpoint['model'], strict=True)
                        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                            logits = model(x, edge).float()
                            margin = (logits[:, 1] - logits[:, 0]).cpu().numpy()
                        assert np.isfinite(margin).all() and not model.training
                        assert all(torch.equal(value.cpu(), checkpoint['model'][key]) for key, value in model.state_dict().items())
                        aps = []
                        for a, b in zip(test['start'], test['stop']):
                            trust = test['trusted'][a:b]
                            y = test['y'][a:b][trust]
                            if np.unique(y).size > 1:
                                aps.append(average_precision_score(y, margin[a:b][trust]))
                        ap, ref_ap = float(np.mean(aps)), reference[point]['test_node_ap']
                        assert abs(ap - ref_ap) < 0.02, (path, ap, ref_ap)
                        verification.append(dict(checkpoint=str(path.relative_to(P)), sha256=sha(path),
                                                 ap=ap, historical_ap=ref_ap, ap_delta=ap-ref_ap,
                                                 state_unchanged=True))
                        for (view, kind), group in sorted(cases.items()):
                            rows.append(dict(variant=variant, fold=recipe, view=view, source=view.rsplit('__ys_', 1)[0],
                                             kind=kind, arm=arm, seed=seed, point=point,
                                             step=checkpoint['best_step'] if point == 'best' else 200,
                                             **endpoint_metrics(group, margin)))
        print(f'{recipe}: 24 checkpoint replays verified', flush=True)
    paired, aggregate = summarize(rows)
    assert len(verification) == 72 and len(rows) == 720 and len(aggregate) == 24
    write_csv(OUT / 'BY_VIEW.csv', rows)
    write_csv(OUT / 'PAIRED_BY_SOURCE.csv', paired)
    write_json(OUT / 'SUMMARY.json', dict(assets=assets, checkpoints=verification, aggregate=aggregate,
                                         optimizer_steps=0, sat_cec_calls=0, labels_modified=False))


if __name__ == '__main__':
    main()
