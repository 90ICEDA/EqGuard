"""Replay circuit alarms and endpoint-size drift from frozen predictions."""
import csv
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

import numpy as np

OUT = Path(__file__).resolve().parent
P = OUT.parent
sys.path.insert(0, str(P / 'lcone_endpoint_overlap_20261112'))
from audit import load


def write(name, rows):
    with (OUT / name).open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def source_macro(rows, threshold):
    groups = defaultdict(list)
    for view, score in rows:
        groups[view['source']].append(score >= threshold)
    return mean(mean(x) for x in groups.values())


def circuit_score(values, k):
    assert values.ndim == 1 and len(values) >= k and np.isfinite(values).all()
    return float(np.sort(np.partition(values, -k)[-k:]).mean(dtype=np.float64))


def alarms():
    with (P / 'control_loader_po_20261105/view_dictionary.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    layouts = {s: [r for r in rows if r['key'] == f'trans_{s}'] for s in ('val', 'test')}
    with np.load(P / 'control_loader_po_20261105/PO_membership_trans_test.npz') as masks:
        added = masks['normal_primary_added']
    results, details, equality = [], [], []
    for seed in (42, 1, 2):
        suffix = '' if seed == 42 else f'_s{seed}'
        for point in ('best', 'last'):
            saved = {}
            for arm in ('N', 'NC'):
                with np.load(P / f'seed42_nc_ablation_20261109/{arm}{suffix}_scores.npz') as z:
                    saved[arm] = {s: z[f'{s}_{point}'] for s in layouts}
            for arm in ('G0', 'GB', 'GM', 'GBM', 'GAll'):
                base = P / (f'control_five_seed{seed}_20261107' if point == 'best'
                            else f'control_last200_20261107/seed{seed}')
                saved[arm] = {s: np.load(base / arm / f'trans_{s}_scores.npy') for s in layouts}
            if seed == 42:
                for arm in ('N_GM', 'NC_GM'):
                    path = OUT / arm / f"{arm.split('_')[0]}_s42_scores.npz"
                    if path.exists():
                        with np.load(path) as z:
                            saved[arm] = {s: z[f'{s}_{point}'] for s in layouts}
            for s, views in layouts.items():
                n, g0 = saved['N'][s].ravel(), saved['G0'][s].ravel()
                phys = np.concatenate([np.arange(int(v['start']), int(v['physical_stop'])) for v in views])
                probability = 1 / (1 + np.exp(-n[phys].astype(np.float64)))
                delta = np.abs(probability - g0[phys])
                equality.append(dict(seed=seed, point=point, split=s,
                                     equivalent=bool(np.all(delta < 1e-6)),
                                     max_abs=float(delta.max())))
            for arm, arrays in saved.items():
                for s, a in arrays.items():
                    assert a.ravel().size == max(int(r['stop']) for r in layouts[s])
                for k in (1, 5):
                    split = {s: [(v, circuit_score(arrays[s].ravel()[int(v['start']):int(v['physical_stop'])], k))
                                 for v in vs] for s, vs in layouts.items()}
                    vp = [r for r in split['val'] if r[0]['kind'] == 'trojan']
                    ordered = sorted({score for _, score in vp}, reverse=True)
                    cut = next(c for c in ordered if source_macro(vp, c) >= .90)
                    idx = ordered.index(cut)
                    assert idx == 0 or source_macro(vp, ordered[idx - 1]) < .90
                    vn = [score for v, score in split['val'] if v['kind'] == 'control']
                    zero_fpr_cut = float(np.nextafter(max(vn), np.inf))
                    normal_without_added = []
                    for v, _ in split['test']:
                        if v['kind'] == 'control':
                            lo, hi = int(v['start']), int(v['physical_stop'])
                            normal_without_added.append((v, circuit_score(
                                arrays['test'].ravel()[lo:hi][~added[lo:hi]], k)))
                    rec = dict(arm=arm, seed=seed, point=point, k=k, threshold=cut,
                               zero_val_fpr_threshold=zero_fpr_cut,
                               test_fpr_excluding_added_diagnostic=source_macro(normal_without_added, cut))
                    for s, view_scores in split.items():
                        for kind, metric in (('trojan', 'tpr'), ('control', 'fpr')):
                            subset = [(v, score) for v, score in view_scores if v['kind'] == kind]
                            rec[f'{s}_{metric}'] = source_macro(subset, cut)
                            rec[f'{s}_{metric}_zero_val_fpr'] = source_macro(subset, zero_fpr_cut)
                            rec[f'{s}_{metric}_count'] = sum(score >= cut for _, score in subset)
                        details.extend(dict(arm=arm, seed=seed, point=point, k=k, split=s,
                                            view=v['view'], source=v['source'], kind=v['kind'],
                                            recipe=v['recipe'], score=score, threshold=cut,
                                            alarm=int(score >= cut)) for v, score in view_scores)
                    results.append(rec)
    write('ALARM.csv', results)
    write('ALARM_BY_VIEW.csv', details)
    write('G0_N_SCORE_CHECK.csv', equality)
    for point in ('best', 'last'):
        for k in (1, 5):
            for arm in dict.fromkeys(r['arm'] for r in results):
                rr = [r for r in results if (r['point'], r['k'], r['arm']) == (point, k, arm)]
                print(point, k, arm, *(round(100 * mean(r[x] for r in rr), 2)
                                       for x in ('val_tpr', 'val_fpr', 'test_tpr', 'test_fpr')))
    print('N/G0 equivalent', sum(r['equivalent'] for r in equality), '/', len(equality),
          'max probability error', max(r['max_abs'] for r in equality))


def drift():
    _, panel = load()
    views = {(view.rsplit('__ys_', 1)[0], view.rsplit('__ys_', 1)[1], kind): group
             for (view, kind), group in panel.items() if '__ys_' in view}
    rows = []
    for (source, recipe, kind), group in sorted(views.items()):
        ref = views.get((source, 'abc', kind))
        if recipe not in ('aig', 'nand') or not ref:
            continue
        matched = set(ref) & set(group)
        for cid in sorted(matched):
            la, ma = ref[cid]
            lb, mb = group[cid]
            assert len(ma) > 0 and len(mb) > 0
            rows.append(dict(source=source, recipe=recipe, kind=kind, endpoint=cid,
                             abc_label=la, recipe_label=lb, abc_gates=len(ma),
                             recipe_gates=len(mb), ratio=len(mb) / len(ma)))
    write('ENDPOINT_SIZE_DRIFT.csv', rows)
    for recipe in ('aig', 'nand'):
        for kind in ('D', 'PO'):
            rr = [r for r in rows if r['recipe'] == recipe and r['kind'] == kind]
            pp = [r for r in rr if r['abc_label'] == r['recipe_label'] == 'positive']
            print(recipe, kind, len(rr), round(median(r['ratio'] for r in rr), 2),
                  len(pp), round(median(r['ratio'] for r in pp), 2) if pp else None)


def joint_metrics():
    from sklearn.metrics import average_precision_score
    sys.path.insert(0, str(P / 'c2_endpoint_replay_20261112'))
    from replay import endpoint_metrics

    layouts, panel = load()
    folder = P / 'control_boundary_v3_20261104/inputs'
    loader = P / 'control_loader_po_20261105'
    with (loader / 'view_dictionary.csv').open(encoding='utf-8-sig', newline='') as f:
        views = [v for v in csv.DictReader(f) if v['key'] == 'trans_test']
    with (P / 'control_five_seed42_20261107/frozen_role_assignments.csv').open(
            encoding='utf-8-sig', newline='') as f:
        roles = defaultdict(list)
        for row in csv.DictReader(f):
            if row['key'] == 'trans_test':
                roles[row['role_class']].append(int(row['row']))
    def labels(split):
        d = folder / f'trans_{split}'
        return [np.load(d / f'{k}.npy') for k in ('y', 'trusted', 'physical')]

    y, trusted, physical = labels('test')
    vy, vt, vp = labels('val')
    all_test_pos = (y == 1) & trusted & physical
    with np.load(loader / 'PO_membership_trans_test.npz') as membership:
        region = {k: membership[k] for k in ('normal_primary_added', 'normal_M')}
    metrics, endpoints, matched = [], [], []
    for arm in ('N', 'NC', 'N_GM', 'NC_GM'):
        base = P / 'seed42_nc_ablation_20261109' if '_' not in arm else OUT / arm
        file = base / (f'{arm}_scores.npz' if '_' not in arm else f"{arm.split('_')[0]}_s42_scores.npz")
        if not file.exists():
            continue
        with np.load(file) as scores:
            assert np.array_equal(scores['y_test'], y) and np.array_equal(scores['trust_test'], trusted)
            for point in ('best', 'last'):
                test, val = scores[f'test_{point}'], scores[f'val_{point}']
                threshold = float(np.quantile(val[(vy == 1) & vt & vp], .10, method='lower'))
                for target in (.80, .95):
                    pos_scores = np.sort(test[all_test_pos])[::-1]
                    cut = pos_scores[int(np.ceil(target * len(pos_scores))) - 1]
                    actual = float((pos_scores >= cut).mean())
                    for v in views:
                        if v['kind'] != 'control':
                            continue
                        lo, hi = int(v['start']), int(v['physical_stop'])
                        negative = trusted[lo:hi] & physical[lo:hi] & (y[lo:hi] == 0)
                        added = negative & region['normal_primary_added'][lo:hi]
                        assert not (region['normal_primary_added'][lo:hi] & ~negative).any()
                        matched.append(dict(arm=arm, point=point, view=v['view'], source=v['source'],
                                            recipe=v['recipe'], target=target, actual=actual,
                                            neg=int(negative.sum()), added=int(added.sum()),
                                            fp=int((test[lo:hi][negative] >= cut).sum()),
                                            added_fp=int((test[lo:hi][added] >= cut).sum())))
                for v in views:
                    start, stop = int(v['start']), int(v['physical_stop'])
                    idx = np.arange(start, stop)
                    ids = idx[trusted[idx] & physical[idx]]
                    observed = test[ids] >= threshold
                    lab = y[ids]
                    result = dict(arm=arm, point=point, view=v['view'], source=v['source'],
                                  recipe=v['recipe'], kind=v['kind'], threshold=threshold,
                                  node_ap=average_precision_score(lab, test[ids]) if (lab == 1).any() else '',
                                  positives=int((lab == 1).sum()),
                                  positive_hits=int((observed & (lab == 1)).sum()),
                                  negatives=int((lab == 0).sum()),
                                  negative_hits=int((observed & (lab == 0)).sum()))
                    for role in ('trigger', 'payload', 'payload_select'):
                        subset = np.intersect1d(ids, roles[role])
                        result[f'{role}_positive'] = len(subset)
                        result[f'{role}_hits'] = int((test[subset] >= threshold).sum())
                    for cat in ('normal_primary_added', 'normal_M'):
                        subset = ids[region[cat][ids]]
                        result[f'{cat}_n'] = len(subset)
                        result[f'{cat}_hits'] = int((test[subset] >= threshold).sum())
                    metrics.append(result)
                for (view, kind), group in panel.items():
                    if view in layouts:
                        endpoints.append(dict(arm=arm, point=point, view=view, kind=kind,
                                              **endpoint_metrics(group, test)))
    write('JOINT_BY_VIEW.csv', metrics)
    write('JOINT_ENDPOINTS.csv', endpoints)
    write('JOINT_MATCHED_NODE_RECALL.csv', matched)


if __name__ == '__main__':
    alarms()
    drift()
    joint_metrics()
