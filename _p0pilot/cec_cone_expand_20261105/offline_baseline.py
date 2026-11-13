"""Describe final cones and replay saved v3/H predictions, without model imports."""
from pathlib import Path
import collections
import csv
import json
import sys
import numpy as np
from final_pair_adapter import FinalCECConePairs, read, digest

O = Path(__file__).resolve().parent
R = O.parents[1]

def table(name, records):
    path = O / name
    assert not path.exists()
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)

def main():
    assert not (O / 'OFFLINE_BASELINE_COMPLETE.json').exists()
    cpath = R / '_p0pilot/control_boundary_v3_20261104/input_contract.json'
    contract = read(cpath)
    final = read(O / 'FINAL_CONTRACT.json')
    byid = {p['pair_id']: p for p in read(O / 'final_pairs.json')}
    cones = {c['cone_id']: c for c in read(O / 'final_cones.json')}
    raw = {}
    features = {}
    for split in ('train', 'val'):
        features[split] = np.load(R / contract['shared_inputs']['trans_' + split]['folder'] / 'x39.npy', mmap_mode='r')
    signature = []
    details = []
    inputs = {}
    for split in ('train', 'val'):
        for p in FinalCECConePairs(split):
            a, b = [cones[byid[p['pair_id']][k]] for k in ('left_cone', 'right_cone')]
            histograms = []
            for z in (a, b):
                if z['view'] not in raw:
                    raw[z['view']] = next(iter(read(R / z['raw_path'])['modules'].values()))
                histograms.append(collections.Counter(raw[z['view']]['cells'][n]['type'] for n in z['members']))
            x, y = [features[split][z['root_row']] for z in (a, b)]
            signature.append(dict(pair_id=p['pair_id'], split=split, source=p['source_object'],
                                  label=byid[p['pair_id']]['root_endpoints'][0]['label'],
                                  left_view=a['view'], right_view=b['view'],
                                  left_cells=len(a['members']), right_cells=len(b['members']),
                                  root39_equal=bool(np.array_equal(x, y)),
                                  root25_equal=bool(np.array_equal(x[:25], y[:25])),
                                  root14_equal=bool(np.array_equal(x[25:], y[25:])),
                                  cell_histogram_equal=histograms[0] == histograms[1],
                                  root39_raw_L1=float(np.abs(x-y).sum()),
                                  weight=p['weight']))
    modelroot = R / '_p0pilot/control_v3_eligible_20261104'
    for seed in (42, 1, 2):
        run = modelroot / ('seed' + str(seed)) / 'H'
        ev = read(run / 'EVALUATED.json')
        binding = read(run / 'binding.json')
        assert binding['feature_contract_sha'] == digest(cpath) == final['input_contract_sha']
        assert digest(run / 'best.pt') == ev['checkpoint_sha']
        assert digest(R / '_p0pilot/control_boundary_v3_20261104/normalization.npz') == binding['normalization_sha']
        inputs[str((run / 'EVALUATED.json').relative_to(R))] = digest(run / 'EVALUATED.json')
        threshold = ev['thresholds']['val_recall80']
        for split in ('train', 'val'):
            scores_path = run / ('trans_' + split + '_scores.npy')
            assert digest(scores_path) == ev['prediction_sha']['trans_' + split]
            inputs[str(scores_path.relative_to(R))] = digest(scores_path)
            scores = np.load(scores_path, mmap_mode='r')
            assert np.isfinite(scores).all() and ((scores >= 0) & (scores <= 1)).all()
            for z in FinalCECConePairs(split):
                p = byid[z['pair_id']]
                a, b = [float(scores[z[k]['root_row']]) for k in ('left', 'right')]
                label = p['root_endpoints'][0]['label']
                assert p['detection_stability_diagnostic_eligible']
                pa, pb = a >= threshold, b >= threshold
                details.append(dict(seed=seed, arm='saved_v3_H', split=split,
                                    source=z['source_object'], pair_id=z['pair_id'], label=label,
                                    weight=z['weight'], probability_a=a, probability_b=b,
                                    absolute_drift=abs(a-b), flip=int(pa != pb),
                                    both_correct=int(pa == label and pb == label),
                                    both_wrong=int(pa != label and pb != label), threshold=threshold))
    # Conditional class summaries retain equal source weights; fewer eligible sources
    # in positive-only strata are reported rather than silently treated as all sources.
    source_rows = []
    for seed in (42, 1, 2):
        for split in ('train', 'val'):
            for label in ('all', 0, 1):
                rr = [x for x in details if x['seed'] == seed and x['split'] == split and (label == 'all' or x['label'] == label)]
                for source in sorted({x['source'] for x in rr}):
                    xx = [x for x in rr if x['source'] == source]
                    weights = np.array([x['weight'] for x in xx]); weights /= weights.sum()
                    row = dict(seed=seed, split=split, stratum=str(label), source=source,
                               pairs=len(xx), positive_pairs=sum(x['label'] == 1 for x in xx))
                    for k in ('absolute_drift', 'flip', 'both_correct', 'both_wrong'):
                        row[k] = float(np.dot(weights, [x[k] for x in xx]))
                    source_rows.append(row)
    summaries = []
    for split in ('train', 'val'):
        for label in ('all', '0', '1'):
            per_seed = []
            for seed in (42, 1, 2):
                rr = [x for x in source_rows if x['seed'] == seed and x['split'] == split and x['stratum'] == label]
                assert rr
                per_seed.append({k: float(np.mean([x[k] for x in rr])) for k in ('absolute_drift', 'flip', 'both_correct', 'both_wrong')})
            row = dict(split=split, stratum=label, sources=len(rr), pairs=sum(x['pairs'] for x in rr), seeds=3)
            for k in ('absolute_drift', 'flip', 'both_correct', 'both_wrong'):
                vals = [x[k] for x in per_seed]
                row[k + '_mean'] = float(np.mean(vals))
                row[k + '_seed_sd'] = float(np.std(vals, ddof=1))
            summaries.append(row)
    features_summary = []
    for split in ('train', 'val'):
        rr = [x for x in signature if x['split'] == split]
        features_summary.append(dict(split=split, pairs=len(rr), sources=len({x['source'] for x in rr}),
                                     root39_equal=sum(x['root39_equal'] for x in rr),
                                     root25_equal=sum(x['root25_equal'] for x in rr),
                                     root14_equal=sum(x['root14_equal'] for x in rr),
                                     same_cell_histogram=sum(x['cell_histogram_equal'] for x in rr),
                                     different_cell_count=sum(x['left_cells'] != x['right_cells'] for x in rr)))
    table('OFFLINE_feature_differences.csv', signature)
    table('OFFLINE_feature_summary.csv', features_summary)
    table('OFFLINE_saved_prediction_pairs.csv', details)
    table('OFFLINE_saved_prediction_sources.csv', source_rows)
    table('OFFLINE_saved_prediction_summary.csv', summaries)
    report = dict(training=0, model_forward=0, new_SAT_queries=0, test_loaded=False,
                  diagnostic_only=True, model='existing improved dual-branch 39v3/H, 200 updates; no added CEC loss',
                  threshold='each seed frozen validation-recall80 threshold from existing EVALUATED.json',
                  weights='equal source then component then edge; class strata condition within source',
                  metrics=summaries, features=features_summary,
                  limitations=['train diagnostics are in-sample', 'only one validation positive pair in one source',
                               'three seeds are not three independent validation hosts',
                               'same gate histograms do not prove graph isomorphism',
                               'probability stability is descriptive; no security-role transfer'],
                  inputs=inputs)
    (O / 'OFFLINE_BASELINE_COMPLETE.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
