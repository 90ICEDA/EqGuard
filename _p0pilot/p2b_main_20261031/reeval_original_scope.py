"""Re-evaluate the new A/B checkpoints on the ORIGINAL trusted mask (P2-A comparable scope).

AP depends on the negative population; the new taint mask adds ~250k trusted negatives,
so AP values are not comparable to P2-A unless the evaluation scope is held fixed.
AUC / R@k are less affected but still recomputed here on the original scope.
"""
import os, sys, json, gc
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
from pathlib import Path
import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
H = Path(__file__).resolve().parent
P2 = ROOT / '_p0pilot/round32_20261029'
sys.path.insert(0, str(ROOT))
from models.gin_net import GINNodeClassifier, GINDual

CONTRACT = json.loads((P2 / 'input_contract.json').read_text(encoding='utf-8'))
NORM = np.load(P2 / 'normalization.npz')
DEVICE = 'cuda'
SEEDS = tuple(int(x) for x in os.environ.get('P2B_SEEDS', '42,1,2').split(','))
RUNDIR = os.environ.get('P2B_RUNDIR', 'runs')


def arrays(split):
    folder = ROOT / CONTRACT['shared_inputs'][f'trans_{split}']['folder']
    return {n: np.load(folder / (n + '.npy'), mmap_mode='r') for n in ('x39', 'edge_index', 'y', 'trusted', 'physical')}


def load(split):
    a = arrays(split)
    x = torch.tensor(np.asarray(a['x39']), device=DEVICE)
    structural = ((x[:, 25:] - torch.tensor(NORM['mean'][25:], device=DEVICE)) / torch.tensor(NORM['std'][25:], device=DEVICE)).clamp(-10, 10)
    return dict(x=torch.cat((x[:, :25], structural), 1), edge=torch.tensor(np.asarray(a['edge_index']), device=DEVICE)), a


def model_for(arm, s):
    torch.manual_seed(s)
    return (GINNodeClassifier(39, 64, 2, 4) if arm == 'A' else GINDual(39, 64, 2, num_layers=2, split=29, fusion='gate')).cuda()


def predict(model, split):
    d, _ = load(split); model.eval()
    with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
        p = model(d['x'], d['edge'])
    s = torch.softmax(p.float(), 1)[:, 1].cpu().numpy()
    del p, d; gc.collect(); torch.cuda.empty_cache()
    return s


def metrics(scores, split, threshold):
    a = arrays(split); yy = a['y']; rows = []
    for view in CONTRACT['shared_inputs'][f'trans_{split}']['views']:
        lo, hi = view['start'], view['stop']
        for scope, mask in [('trusted', a['trusted'][lo:hi]), ('legacy', a['physical'][lo:hi])]:
            y = yy[lo:hi][mask]; p = scores[lo:hi][mask]; pos = int(y.sum()); neg = len(y) - pos
            row = dict(view=view['view'], scope=scope, n=len(y), positive=pos, negative=neg,
                       ap=float(average_precision_score(y, p)) if pos else None,
                       auc=float(roc_auc_score(y, p)) if pos and neg else None,
                       fpr=float((p[y == 0] >= threshold).mean()) if neg else None,
                       recall=float((p[y == 1] >= threshold).mean()) if pos else None)
            for budget in (.01, .05):
                k = max(1, int(len(y) * budget)); order = np.argsort(-p, kind='stable')
                row['r' + str(int(budget * 100))] = float(y[order[:k]].sum() / pos) if pos else None
            rows.append(row)
    out = {}
    for scope in ('trusted', 'legacy'):
        inj = [r for r in rows if r['scope'] == scope and '__inj' in r['view'] and r['positive']]
        out[scope] = {k: float(np.mean([r[k] for r in inj if r[k] is not None])) for k in ('ap', 'auc', 'r1', 'r5', 'recall')}
        out[scope]['views'] = len(inj)
        ctl = [r for r in rows if r['scope'] == scope and '__inj' not in r['view'] and r['negative']]
        out[scope]['control_fpr'] = float(np.mean([r['fpr'] for r in ctl])) if ctl else None
    return out


def main():
    res = {}
    for s in SEEDS:
        for arm in ('A', 'B'):
            out = H / RUNDIR / f'seed{s}' / arm
            sel = json.loads((out / 'SELECTED.json').read_text())
            m = model_for(arm, s); m.load_state_dict(torch.load(ROOT / sel['path'], map_location=DEVICE, weights_only=True))
            v = predict(m, 'val'); va = arrays('val')
            neg = v[va['trusted'] & (va['y'] == 0)]
            th = float(np.nextafter(np.quantile(neg, .95), np.inf))
            r = dict(arm=arm, seed=s, threshold=th, selected=sel)
            r['val'] = metrics(v, 'val', th)
            r['test'] = metrics(predict(m, 'test'), 'test', th)
            res[f'{arm}_{s}'] = r
            del m; gc.collect(); torch.cuda.empty_cache()
    (H / ('reeval_original_scope.json' if RUNDIR == 'runs' else f'reeval_original_scope_{RUNDIR}.json')).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
    for s in SEEDS:
        for arm in ('A', 'B'):
            r = res[f'{arm}_{s}']; t = r['test']['trusted']; l = r['test']['legacy']
            print(f"SEED {s} {arm}: AP={t['ap']:.4f} AUC={t['auc']:.4f} R1={t['r1']:.4f} R5={t['r5']:.4f} FPR={t['control_fpr']:.4f} | legacy AP={l['ap']:.4f}")
    for arm in ('A', 'B'):
        aps = [res[f'{arm}_{s}']['test']['trusted']['ap'] for s in SEEDS]
        print(arm, 'mean', round(float(np.mean(aps)), 4), 'std', round(float(np.std(aps, ddof=1)), 4))


if __name__ == '__main__':
    main()
