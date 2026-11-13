"""Round 21A: leave-one-family-out full-table diagnostic.

36 runs = 4 folds x 3 arms x 3 seeds, fixed 250 updates. Primary checkpoint is
the final update. Test labels are read only after all fold arms/seeds finish.
"""
import csv
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_round21'
R18 = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_small_round18'
RUNS = ROOT / 'results_sat_r21'
sys.path.insert(0, str(ROOT))
from models.gin_net import GINNodeClassifier

ARMS = ['metadata', 'real', 'permuted']


def write_json(p, x):
    Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2), encoding='utf-8')


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def state_sha(state):
    h = hashlib.sha256()
    for key, value in sorted(state.items()):
        h.update(key.encode())
        h.update(value.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def set_seed(n):
    random.seed(n)
    np.random.seed(n)
    torch.manual_seed(n)
    torch.cuda.manual_seed_all(n)


def threshold(y, p):
    neg = p[y == 0]
    if len(neg) == 0:
        raise RuntimeError('No validation negatives')
    return float(np.quantile(neg, 0.95, method='higher'))


def metrics(y, p, thr):
    pos = y == 1
    neg = y == 0
    pred = p > thr
    tp = int((pred & pos).sum())
    fp = int((pred & neg).sum())
    fn = int((~pred & pos).sum())
    tn = int((~pred & neg).sum())
    both = bool(pos.any() and neg.any())
    return dict(n=len(y), positives=int(pos.sum()), prevalence=float(pos.mean()),
                AP=float(average_precision_score(y, p)) if both else None,
                ROC_AUC=float(roc_auc_score(y, p)) if both else None,
                TP=tp, FP=fp, FN=fn, TN=tn,
                recall=float(tp / (tp + fn)) if tp + fn else None,
                FPR=float(fp / (fp + tn)) if fp + tn else None,
                precision=float(tp / (tp + fp)) if tp + fp else None,
                threshold=float(thr))


def make_graph(indices, base, features, arm, edge_index):
    idx = np.asarray(indices, dtype=np.int64)
    rev = np.full(len(base), -1, np.int64)
    rev[idx] = np.arange(len(idx))
    keep = np.isin(edge_index[0], idx) & np.isin(edge_index[1], idx)
    e = torch.tensor(rev[edge_index[:, keep]], dtype=torch.long, device='cuda')
    xin = np.concatenate([base[idx], features[arm][idx]], axis=1)
    return idx, torch.tensor(xin, dtype=torch.float32, device='cuda'), e


def eval_scores(model, xt, e):
    model.eval()
    with torch.no_grad():
        return torch.softmax(model(xt, e).float(), dim=1)[:, 1].cpu().numpy()


def run_fold(fold, features, base_x, edge_index, ids, y_all, protocol):
    train_ix = np.asarray(fold['train_indices'], dtype=np.int64)
    val_ix = np.asarray(fold['val_indices'], dtype=np.int64)
    test_ix = np.asarray(fold['test_indices'], dtype=np.int64)
    # Train/val labels only; test labels are deferred until all arms/seeds are committed.
    ytr = y_all[torch.tensor(ids[train_ix])].numpy().astype(np.int64)
    yva = y_all[torch.tensor(ids[val_ix])].numpy().astype(np.int64)
    assert ytr.sum() > 0 and yva.sum() > 0
    mu = base_x[train_ix].mean(0, keepdims=True)
    sd = base_x[train_ix].std(0, keepdims=True, ddof=1).clip(1e-6)
    base = np.nan_to_num((base_x - mu) / sd).clip(-10, 10).astype(np.float32)
    weight = torch.tensor([1.0, float((ytr == 0).sum()) / float((ytr == 1).sum())],
                          dtype=torch.float32, device='cuda')
    graphs = {}
    for arm in ARMS:
        graphs[arm] = {}
        for split, ix in (('train', train_ix), ('val', val_ix), ('test', test_ix)):
            _, xt, e = make_graph(ix, base, features, arm, edge_index)
            graphs[arm][split] = (xt, e)
    ytr_t = torch.tensor(ytr, dtype=torch.long, device='cuda')
    rows = []
    fold_start = time.perf_counter()
    for seed in protocol['seeds']:
        for arm in ARMS:
            set_seed(seed)
            folder = RUNS / fold['fold'] / f'{arm}_seed{seed}'
            folder.mkdir(parents=True, exist_ok=True)
            model = GINNodeClassifier(39 + 114, 64, 2, num_layers=4).cuda()
            init = state_sha(model.state_dict())
            opt = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=0.001)
            xtr, etr = graphs[arm]['train']
            xva, eva = graphs[arm]['val']
            best = -1.0
            best_epoch = -1
            best_state = None
            best_p = None
            logs = []
            wall = time.perf_counter()
            for epoch in range(1, 251):
                model.train()
                opt.zero_grad(set_to_none=True)
                logits = model(xtr, etr)
                loss = F.cross_entropy(logits, ytr_t, weight=weight)
                if not torch.isfinite(loss):
                    raise RuntimeError('Nonfinite loss')
                loss.backward()
                grad = float(torch.nn.utils.clip_grad_norm_(model.parameters(), float('inf')))
                if not np.isfinite(grad):
                    raise RuntimeError('Nonfinite gradient')
                opt.step()
                row = dict(epoch=epoch, train_loss=float(loss.detach()), grad_norm=grad)
                if epoch % 10 == 0:
                    p = eval_scores(model, xva, eva)
                    ap = float(average_precision_score(yva, p))
                    row['val_AP'] = ap
                    if ap > best:
                        best = ap
                        best_epoch = epoch
                        best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
                        best_p = p.copy()
                logs.append(row)
            final_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            final_p = eval_scores(model, xva, eva)
            train_p = eval_scores(model, xtr, etr)
            final_thr = threshold(yva, final_p)
            best_thr = threshold(yva, best_p)
            torch.save(dict(state_dict=final_state, threshold=final_thr, epoch=250,
                            arm=arm, seed=seed, fold=fold['fold'], init_sha=init), folder / 'final.pt')
            torch.save(dict(state_dict=best_state, threshold=best_thr, epoch=best_epoch,
                            arm=arm, seed=seed, fold=fold['fold'], init_sha=init), folder / 'best.pt')
            np.savez_compressed(folder / 'val_predictions.npz',
                                global_ids=ids[val_ix], labels=yva,
                                final=final_p, best=best_p)
            with (folder / 'train_log.csv').open('w', newline='', encoding='utf-8') as fh:
                w = csv.DictWriter(fh, fieldnames=['epoch', 'train_loss', 'grad_norm', 'val_AP'])
                w.writeheader()
                w.writerows(logs)
            row = dict(fold=fold['fold'], test_family=fold['test_families'][0],
                       val_family=fold['val_families'][0], arm=arm, seed=seed,
                       init_sha=init, best_epoch=best_epoch, updates=250,
                       val_final=metrics(yva, final_p, final_thr),
                       val_best=metrics(yva, best_p, best_thr),
                       train_final=metrics(ytr, train_p, final_thr),
                       wall_s=time.perf_counter() - wall,
                       final_loss=logs[-1]['train_loss'],
                       ckpt_sha=sha_file(folder / 'final.pt'))
            rows.append(row)
            print(f"[TRAIN] {fold['fold']} {arm} seed={seed} "
                  f"valAP_final={row['val_final']['AP']:.5f} "
                  f"valAP_best={row['val_best']['AP']:.5f}", flush=True)
            del model, opt, xtr, xva, etr, eva
    # Commit all choices before reading test labels or running test inference.
    write_json(RUNS / fold['fold'] / 'selection_complete.json',
               dict(fold=fold['fold'], rows=rows, test_labels_read=False,
                    primary_checkpoint='final at 250 updates',
                    elapsed_s=time.perf_counter() - fold_start))
    test_y = y_all[torch.tensor(ids[test_ix])].numpy().astype(np.int64)
    for row in rows:
        arm, seed = row['arm'], row['seed']
        folder = RUNS / fold['fold'] / f'{arm}_seed{seed}'
        ck = torch.load(folder / 'final.pt', map_location='cpu', weights_only=False)
        model = GINNodeClassifier(39 + 114, 64, 2, num_layers=4).cuda()
        model.load_state_dict(ck['state_dict'])
        xt, et = graphs[arm]['test']
        p = eval_scores(model, xt, et)
        row['test'] = metrics(test_y, p, ck['threshold'])
        np.savez_compressed(folder / 'test_predictions.npz',
                            global_ids=ids[test_ix], labels=test_y, probability=p)
        write_json(folder / 'summary.json', row)
        del model, xt, et
    write_json(RUNS / fold['fold'] / 'test_complete.json',
               dict(fold=fold['fold'], test_family=fold['test_families'][0],
                    test_labels_read=True, test_nodes=len(test_ix),
                    test_positives=int(test_y.sum())))
    print(f"[TEST] {fold['fold']} test_pos={int(test_y.sum())}", flush=True)
    return rows



def mean_sd(values):
    a = np.asarray(values, dtype=np.float64)
    return float(a.mean()), float(a.std(ddof=1)) if len(a) > 1 else 0.0


def flat_row(r):
    out = {k: r[k] for k in ('fold', 'test_family', 'val_family', 'arm', 'seed',
                             'init_sha', 'best_epoch', 'updates', 'wall_s',
                             'final_loss', 'ckpt_sha')}
    for prefix in ('val_final', 'val_best', 'train_final', 'test'):
        for k, v in r[prefix].items():
            out[f'{prefix}_{k}'] = v
    return out


def aggregate(rows, protocol):
    out = dict(arms={}, paired={}, acceptance={})
    for arm in protocol['arms']:
        rr = [r for r in rows if r['arm'] == arm]
        out['arms'][arm] = {}
        for split in ('val_final', 'val_best', 'test'):
            out['arms'][arm][split] = {}
            for metric in ('AP', 'ROC_AUC', 'recall', 'FPR'):
                vals = [r[split][metric] for r in rr if r[split][metric] is not None]
                m, s = mean_sd(vals)
                out['arms'][arm][split][metric] = dict(mean=m, std=s, values=vals)
        out['arms'][arm]['test_prevalence'] = mean_sd(
            [r['test']['prevalence'] for r in rr])
        out['arms'][arm]['per_fold_test_AP'] = {
            f: mean_sd([r['test']['AP'] for r in rr if r['fold'] == f])[0]
            for f in protocol['folds']}
    for a, b in (('real', 'metadata'), ('real', 'permuted'), ('permuted', 'metadata')):
        key = f'{a}_minus_{b}'
        lookup = {(r['fold'], r['seed'], r['arm']): r for r in rows}
        deltas = []
        for fold in protocol['folds']:
            for seed in protocol['seeds']:
                deltas.append(lookup[(fold, seed, a)]['test']['AP'] -
                              lookup[(fold, seed, b)]['test']['AP'])
        fold_means = {}
        for fold in protocol['folds']:
            vals = [lookup[(fold, seed, a)]['test']['AP'] -
                    lookup[(fold, seed, b)]['test']['AP'] for seed in protocol['seeds']]
            fold_means[fold] = float(np.mean(vals))
        m, s = mean_sd(deltas)
        out['paired'][key] = dict(deltas=deltas, mean=m, std=s,
                                  fold_means=fold_means,
                                  positive_folds=int(sum(v > 0 for v in fold_means.values())),
                                  positive_runs=int(sum(v > 0 for v in deltas)))
    rp = out['paired']['real_minus_permuted']
    rm = out['paired']['real_minus_metadata']
    passed = (rp['positive_folds'] >= 3 and rm['positive_folds'] >= 3 and
              rp['mean'] > 0 and rm['mean'] > 0)
    out['acceptance'] = dict(
        pass_21a=bool(passed),
        real_minus_permuted=dict(fold_positive=rp['positive_folds'],
                                 overall_mean=rp['mean'], fold_means=rp['fold_means']),
        real_minus_metadata=dict(fold_positive=rm['positive_folds'],
                                  overall_mean=rm['mean'], fold_means=rm['fold_means']),
        rule=protocol['go_no_go'],
        posthoc=True, confirmatory=False,
        if_fail='Do not trigger 21B. SAT remains unproven as a dense feature.')
    return out

def main():
    torch.set_num_threads(4)
    if not torch.cuda.is_available():
        raise RuntimeError('GPU required; no CPU fallback')
    protocol = json.loads((T / 'protocol.json').read_text(encoding='utf-8'))
    folds = json.loads((T / 'folds.json').read_text(encoding='utf-8'))
    pf = json.loads((T / 'preflight.json').read_text(encoding='utf-8'))
    assert pf['status'] == 'preflight_passed'
    fz = np.load(T / 'features.npz')
    base = np.load(R18 / 'base_inputs.npz')
    ids = base['global_ids']
    assert sha_file(T / 'features.npz') == protocol['hashes']['features']
    assert sha_file(T / 'folds.json') == protocol['hashes']['folds']
    features = {a: fz[a] for a in protocol['arms']}
    g = torch.load(ROOT / 'generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt',
                   map_location='cpu', weights_only=False, mmap=True)
    y_all = g.y
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    if RUNS.exists():
        raise RuntimeError(f'Fresh results directory required: {RUNS}')
    RUNS.mkdir(parents=True)
    all_rows = []
    start = time.perf_counter()
    for fold in folds['folds']:
        print(f'[FOLD] {fold["fold"]}', flush=True)
        all_rows.extend(run_fold(fold, features, base['x'].astype(np.float32),
                                 base['edge_index'], ids, y_all, protocol))
    summary = aggregate(all_rows, protocol)
    rows_flat = [flat_row(r) for r in all_rows]
    with (T / 'runs.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_flat[0]))
        w.writeheader()
        w.writerows(rows_flat)
    with (T / 'summary.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['arm', 'fold', 'seed', 'test_AP', 'test_ROC_AUC', 'recall', 'FPR',
                    'val_AP', 'prevalence'])
        for r in all_rows:
            w.writerow([r['arm'], r['fold'], r['seed'], r['test']['AP'],
                        r['test']['ROC_AUC'], r['test']['recall'], r['test']['FPR'],
                        r['val_final']['AP'], r['test']['prevalence']])
    write_json(T / 'summary.json', dict(
        round=21, step='21A', status='completed_posthoc_diagnostic',
        protocol_sha=sha_file(T / 'protocol.json'), preflight_sha=sha_file(T / 'preflight.json'),
        features_sha=sha_file(T / 'features.npz'), folds_sha=sha_file(T / 'folds.json'),
        summary=summary, runtime_s=time.perf_counter() - start,
        test_evaluated=True, test_labels_read_after_selection=True,
        confirmatory=False,
        limitations='4 families only; test families already observed in Round18; '
                    '6-13 positives per test family; not a new independent test.'))
    write_json(T / 'step2_decision.json', dict(
        step='21B', triggered=bool(summary['acceptance']['pass_21a']),
        decision='triggered' if summary['acceptance']['pass_21a'] else 'not_triggered',
        reason='21A go/no-go criteria evaluated',
        criteria=protocol['go_no_go'],
        evidence=summary['acceptance'],
        new_sat_queries=0 if not summary['acceptance']['pass_21a'] else None,
        new_training_runs=0))
    print(json.dumps(dict(acceptance=summary['acceptance'],
                          arms={a: summary['arms'][a]['test']['AP'] for a in protocol['arms']},
                          runtime_s=time.perf_counter() - start), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
