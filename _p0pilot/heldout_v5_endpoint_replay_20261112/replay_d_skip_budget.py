"""Compare stop and skip inspection policies on saved D endpoint predictions."""
import csv
import sys
from collections import Counter, defaultdict

import numpy as np

from evaluate import BOUNDARY, OUT, P, SEEDS, V4, V5, bind, load_module, read, sha, write_csv, write_json

CAP = 512
TRAIN_AUDIT = P / 'lcone_rank_train_gate_20261112'


def replay(group, order, skip):
    covered, selected, oversized = set(), [], []
    for c in order:
        incremental = group[c][1] - covered
        if len(covered) + len(incremental) > CAP:
            oversized.append(c)
            if not skip:
                break
            continue
        covered.update(incremental)
        selected.append(c)
    counts = Counter(group[c][0] for c in selected)
    assert len(covered) <= CAP and sum(counts.values()) == len(selected)
    return selected, oversized, counts, len(covered)


def compare(group, scores):
    order = sorted(group, key=lambda c: (-scores[c], c))
    support = Counter(label for label, _ in group.values())
    stop, stop_over, a, ga = replay(group, order, False)
    skip, skip_over, b, gb = replay(group, order, True)
    assert skip[:len(stop)] == stop and stop_over == skip_over[:len(stop_over)]
    gained = skip[len(stop):]
    assert ga <= gb and all(a[k] <= b[k] for k in support)
    row = dict(support_positive=support['positive'], support_negative=support['negative'], support_unknown=support['unknown'],
               stop_hit=a['positive'], skip_hit=b['positive'],
               stop_recall=a['positive']/support['positive'] if support['positive'] else None,
               skip_recall=b['positive']/support['positive'] if support['positive'] else None,
               stop_fp=a['negative'], skip_fp=b['negative'], stop_unknown=a['unknown'], skip_unknown=b['unknown'],
               stop_gates=ga, skip_gates=gb, stop_checks=len(stop), skip_checks=len(skip),
               first_over=stop_over[0] if stop_over else '',
               first_over_status=group[stop_over[0]][0] if stop_over else '',
               first_over_size=len(group[stop_over[0]][1]) if stop_over else None,
               added_pos='|'.join(c for c in gained if group[c][0] == 'positive'),
               added_fp='|'.join(c for c in gained if group[c][0] == 'negative'),
               added_unknown='|'.join(c for c in gained if group[c][0] == 'unknown'))
    return row


def main():
    panel = load_module('skip_panel', P / 'lcone_endpoint_overlap_20261112/audit.py')
    layouts, truth = panel.load()
    reference = read(OUT / 'SUMMARY.json')
    assert reference['truth_sha256'] == sha(panel.FROZEN / 'EVIDENCE.json')
    with (OUT / 'BY_VIEW.csv').open(encoding='utf-8-sig', newline='') as f:
        previous = {(r['fold'], int(r['seed']), r['arm'], r['point'], r['view']): r for r in csv.DictReader(f) if r['kind']=='D'}
    original = {k: np.load(BOUNDARY / f'inputs/trans_test/{k}.npy', mmap_mode='r') for k in ('y', 'trusted', 'physical')}
    test_rows, prediction_hashes = [], {}
    for recipe in ('abc', 'nand'):
        fold = 'ys_' + recipe
        map_path = V4 / f'{fold}_test_map.npz'
        assert sha(map_path) == reference['audits'][recipe]['test_map_sha256']
        with np.load(map_path) as data:
            test = {k: data[k] for k in ('rows', 'old2new', 'new2old', 'y', 'trusted', 'physical')}
        cases, _ = bind(recipe, layouts, truth, test, original)
        views = {v: ({c: (lab, set(a.tolist())) for c, (lab, a) in g.items()}, g)
                 for (v, kind), g in cases.items() if kind == 'D'}
        for rec in reference['audits'][recipe]['runs']:
            seed, arm, point = (rec[k] for k in ('seed', 'arm', 'point'))
            if seed == 42:
                path = P / 'heldout_recipe_v5_eval2_20261109' / f'{fold}_{arm}_{point}_testpred.npz'
            else:
                path = V5 / fold / arm / f'seed{seed}' / f'{point}_pred.npz'
            key = f'{fold}/{seed}/{arm}/{point}'
            prediction_hashes[key] = sha(path)
            assert prediction_hashes[key] == rec['scored_prediction_sha256']
            with np.load(path) as data:
                if seed == 42:
                    full = data['rows']
                    ids = np.searchsorted(full, test['rows'])
                    assert np.array_equal(full[ids], test['rows'])
                    margin = data['scores'][ids]
                else:
                    assert np.array_equal(data['test_rows'], test['rows'])
                    margin = data['test']
            assert margin.shape == test['rows'].shape and np.isfinite(margin).all()
            for view, (group, original_group) in sorted(views.items()):
                scores = {c: float(margin[a].max()) for c, (_, a) in original_group.items()}
                result = compare(group, scores)
                old = previous[recipe, seed, arm, point, view]
                assert (None if old['recall_512'] == '' else float(old['recall_512'])) == result['stop_recall']
                assert int(old['gates_512']) == result['stop_gates']
                assert all(int(old[k]) == result['support_' + k] for k in ('positive', 'negative', 'unknown'))
                test_rows.append(dict(fold=recipe, seed=seed, arm=arm, point=point,
                                      source=view.rsplit('__ys_', 1)[0], view=view, **result))
    assert len(test_rows) == 120 and {r['seed'] for r in test_rows} == set(SEEDS)

    sys.path.insert(0, str(TRAIN_AUDIT))
    train_panel = load_module('skip_train_panel', TRAIN_AUDIT / 'audit.py')
    _, training_views = train_panel.read_panel(verified=True)
    cache_path = TRAIN_AUDIT / 'ABC_SHARED_SCORE_CACHE.json'
    cache = read(cache_path)
    assert cache['checkpoints'] == read(TRAIN_AUDIT / 'ABC_BUDGET_PROVENANCE.json')['checkpoints']
    scored_views = defaultdict(dict)
    for r in cache['rows']:
        scored_views[r['reference'], r['view']][r['cone']] = r['score']
    train_rows = []
    for (point, view), scores in sorted(scored_views.items()):
        group = {c: (lab, set(a.tolist())) for c, (lab, a) in training_views[view].items()}
        assert group.keys() == scores.keys() and not view.endswith('__ys_abc')
        train_rows.append(dict(fold='abc', reference=point, source=view.rsplit('__ys_', 1)[0], view=view, **compare(group, scores)))
    assert len(train_rows) == 10
    write_csv(OUT / 'D_SKIP512_TEST_BY_SOURCE.csv', test_rows)
    write_csv(OUT / 'D_SKIP512_TRAIN_DIAGNOSTIC.csv', train_rows)
    write_json(OUT / 'D_SKIP512_PROVENANCE.json', dict(test_scores=prediction_hashes, training_cache_sha256=sha(cache_path),
               truth_sha256=reference['truth_sha256'], baseline_reproduced=len(test_rows), forward_passes=0,
               optimizer_steps=0, sat_cec_calls=0, labels_modified=False))
    for rows in (test_rows, train_rows):
        groups = defaultdict(list)
        for r in rows:
            groups[r['fold'], r['source']].append(r)
        for key, items in sorted(groups.items()):
            print(key, len(items), {field: sum(r['skip_'+field]-r['stop_'+field] for r in items)
                  for field in ('hit', 'fp', 'unknown', 'gates')}, flush=True)


if __name__ == '__main__':
    main()
