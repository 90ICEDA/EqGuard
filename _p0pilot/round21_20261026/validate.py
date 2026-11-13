"""Recompute every Round 21A summary metric from saved probabilities."""
import csv
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_round21'
RUNS = ROOT / 'results_sat_r21'


def metrics(y, p, thr):
    pos = y == 1
    neg = y == 0
    pred = p > thr
    tp = int((pred & pos).sum())
    fp = int((pred & neg).sum())
    fn = int((~pred & pos).sum())
    tn = int((~pred & neg).sum())
    both = bool(pos.any() and neg.any())
    return dict(AP=float(average_precision_score(y, p)) if both else None,
                ROC_AUC=float(roc_auc_score(y, p)) if both else None,
                recall=float(tp / (tp + fn)) if tp + fn else None,
                FPR=float(fp / (fp + tn)) if fp + tn else None,
                positives=int(pos.sum()), prevalence=float(pos.mean()),
                TP=tp, FP=fp, FN=fn, TN=tn)


def main():
    rows = list(csv.DictReader((T / 'runs.csv').open(encoding='utf-8')))
    assert len(rows) == 36
    keys = {(r['fold'], r['arm'], r['seed']) for r in rows}
    folds = ['test_alpha', 'test_beta', 'test_epsilon', 'test_zeta']
    arms = ['metadata', 'real', 'permuted']
    seeds = ['42', '1', '2']
    assert keys == {(f, a, s) for f in folds for a in arms for s in seeds}
    assert len({r['init_sha'] for r in rows if r['seed'] == '42'}) == 1
    assert len({r['init_sha'] for r in rows if r['seed'] == '1'}) == 1
    assert len({r['init_sha'] for r in rows if r['seed'] == '2'}) == 1
    checks = []
    for r in rows:
        d = RUNS / r['fold'] / f"{r['arm']}_seed{r['seed']}"
        assert (RUNS / r['fold'] / 'selection_complete.json').exists()
        assert (RUNS / r['fold'] / 'test_complete.json').exists()
        vp = np.load(d / 'val_predictions.npz')
        tp = np.load(d / 'test_predictions.npz')
        import torch
        ck = torch.load(d / 'final.pt', map_location='cpu', weights_only=False)
        thr = float(ck['threshold'])
        v = metrics(vp['labels'].astype(int), vp['final'].astype(np.float64), thr)
        t = metrics(tp['labels'].astype(int), tp['probability'].astype(np.float64), thr)
        for prefix, got, expect in (
            ('test', t, dict(AP=float(r['test_AP']), ROC_AUC=float(r['test_ROC_AUC']),
                             recall=float(r['test_recall']), FPR=float(r['test_FPR']))),
            ('val', v, dict(AP=float(r['val_final_AP']), ROC_AUC=float(r['val_final_ROC_AUC']),
                            recall=float(r['val_final_recall']), FPR=float(r['val_final_FPR']))),
        ):
            for k, val in expect.items():
                assert abs(float(got[k]) - val) <= 1e-6, (r['fold'], r['arm'], r['seed'], prefix, k, got[k], val)
        checks.append(dict(fold=r['fold'], arm=r['arm'], seed=int(r['seed']),
                           test_AP=t['AP'], test_positives=t['positives'],
                           test_prevalence=t['prevalence'], threshold=thr,
                           repeat_ckpt_sha=r['ckpt_sha']))
    summary = json.loads((T / 'summary.json').read_text(encoding='utf-8'))
    decision = json.loads((T / 'step2_decision.json').read_text(encoding='utf-8'))
    assert summary['summary']['acceptance']['pass_21a'] is False
    assert decision['triggered'] is False and decision['new_sat_queries'] == 0
    assert summary['test_evaluated'] is True
    out = dict(status='validated', rows=36, recomputed=36,
               unique_fold_arm_seed=len(keys), init_hashes_per_seed=3,
               no_nan_or_inf=True, max_abs_metric_error_le_1e_6=True,
               test_evaluated=summary['test_evaluated'],
               step2_triggered=decision['triggered'],
               step2_new_sat_queries=decision['new_sat_queries'],
               checks=checks)
    (T / 'validation.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in out.items() if k != 'checks'}, indent=2))


if __name__ == '__main__':
    main()
