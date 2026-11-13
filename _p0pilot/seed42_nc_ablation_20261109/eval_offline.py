"""Offline evaluation of saved N/NC checkpoints on orig and trans sides, val and test.

Reports per-view node AP, per-view top-k (trusted physical nodes, stable ties), role recall,
normal-view alarm FPR, normal D/PO cone FPR, val-threshold transfer and same-recall diagnostic.
Test labels are never used for tuning; the same-recall test diagnostic is explicitly labeled.
"""
import os
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '1'
os.environ['P2B_MASK'] = 'old'
import json
import sys
from pathlib import Path

import numpy as np
import torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/seed42_nc_ablation_20261109'
L = R / '_p0pilot/control_loader_po_20261105'
V = R / '_p0pilot/control_v3_eligible_20261104'
sys.path.insert(0, str(L)); sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
from supervision_loader import FiveGroupLoader  # noqa: E402
from evaluate import Model, T  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

BOUND = json.loads((R / '_p0pilot/control_boundary_v3_20261104/input_contract.json').read_text(encoding='utf-8'))
LINEAGE = R / '_p0pilot/control_role_pattern_20261107/NODE_LINEAGE.csv'


def views_of(split, domain='trans'):
    return {v['view']: v for v in BOUND['shared_inputs'][f'{domain}_{split}']['views']}


def view_metrics(margin, y, trust, views, k_fracs=(1, 5)):
    aps, t1, t5 = [], [], []
    for v, lay in views.items():
        lo = lay['start']; hi = lo + (lay['old_stop'] - lay['old_start'])
        yy = y[lo:hi]; tt = trust[lo:hi]; ss = margin[lo:hi]
        m = tt
        if m.sum() < 2 or len(np.unique(yy[m])) < 2:
            continue
        aps.append(average_precision_score(yy[m], ss[m]))
        order = np.lexsort((np.arange(len(ss))[m], -ss[m]))
        idx = np.arange(len(ss))[m][order]
        pos = (yy[m] == 1)[order]
        for frac, acc in ((1, t1), (5, t5)):
            k = max(1, int(len(idx) * frac / 100))
            acc.append(float(pos[:k].sum() / max(1, pos.sum())))
    return dict(ap_view=float(np.mean(aps)) if aps else float('nan'),
                top1=float(np.mean(t1)) if t1 else float('nan'),
                top5=float(np.mean(t5)) if t5 else float('nan'),
                support=len(aps))


def thresholds(margin, y, trust, targets=(0.8, 0.9, 0.95)):
    p = trust & (y == 1); n = trust & (y == 0)
    out = {}
    for t in targets:
        need = int(np.ceil(t * p.sum()))
        if need <= 0 or need > p.sum():
            out[str(t)] = None; continue
        thr = float(np.sort(margin[p])[::-1][need - 1])
        out[str(t)] = dict(thr=thr, val_recall=float((margin[p] >= thr).sum() / p.sum()),
                           val_fpr=float((margin[n] >= thr).sum() / max(1, n.sum())))
    return out


def apply_thr(margin, y, trust, thr):
    p = trust & (y == 1); n = trust & (y == 0)
    return dict(recall=float((margin[p] >= thr).sum() / max(1, p.sum())),
                fpr=float((margin[n] >= thr).sum() / max(1, n.sum())))


def cone_metrics(margin, split, thr=None):
    import csv
    rows = []
    path = OUT / 'CONE_CACHE_TEST.csv' if split == 'test' else R / '_p0pilot/seed42_supervised_prep_20261109/CONE_CACHE_V2.csv'
    with path.open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['split'] != split or r['kind'] not in ('D', 'PO') or int(r['label']) < 0:
                continue
            mem = [int(x) for x in r['phys_rows'].split('|') if x]
            if not mem:
                continue
            rows.append((int(r['label']), float(max(margin[x] for x in mem))))
    out = {}
    for kind in ('D', 'PO'):
        pass
    if not rows:
        return dict(ap_NA=True)
    lab = np.array([x[0] for x in rows]); sc = np.array([x[1] for x in rows])
    res = dict(cones=len(rows), pos=int(lab.sum()), neg=int((lab == 0).sum()),
               ap=(float(average_precision_score(lab, sc)) if len(np.unique(lab)) > 1 else None))
    if thr is not None:
        neg = sc[lab == 0]
        res['fpr_at_thr'] = float((neg >= thr).sum() / max(1, len(neg)))
    return res


def normal_view_fpr(margin, y, trust, views, thr):
    alarm = []
    for v, lay in views.items():
        lo = lay['start']; hi = lo + (lay['old_stop'] - lay['old_start'])
        yy = y[lo:hi]; tt = trust[lo:hi]; ss = margin[lo:hi]
        if (yy[tt] == 1).any():
            continue
        alarm.append(float(ss[tt].max() >= thr) if tt.any() else 0.0)
    return dict(normal_views=len(alarm), fpr=float(np.mean(alarm)) if alarm else None)


def role_recall(margin, y, trust, split):
    import csv
    roles = {}
    with LINEAGE.open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['key'].startswith('trans') and r['role'] in ('trigger', 'payload', 'output_hijack'):
                roles.setdefault(r['source'], {})[r['node_name']] = r['role']
    _, _, names, views = S.load_snapshot(split)
    k = max(1, int(trust.sum() * 0.01))
    top = set(np.lexsort((np.arange(len(margin)), -margin))[:k].tolist())
    out = {}
    for src, mp in roles.items():
        for node, role in mp.items():
            for v in views:
                if not v.startswith(src + '__'):
                    continue
                vr = S.view_rows(views, names, v)
                row = vr.get(node)
                if row is not None and y[row] == 1 and trust[row]:
                    out.setdefault(role, []).append(row)
    return {r: dict(support=len(rows), recall=float(len([x for x in rows if x in top]) / len(rows)))
            for r, rows in out.items()}


def main():
    sys.path.insert(0, str(R / '_p0pilot/control_signed_carrier_20261109_v3'))
    global S
    import Signed_common as S
    assert 'ginvenv_gpu' in sys.executable and torch.cuda.is_available()
    torch.set_num_threads(2)
    loader = FiveGroupLoader()
    T.CONTRACT = loader.feature_contract; T.NORM = loader.normalization; T.arrays = loader.arrays
    ckpt, arm, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
    model = Model().cuda()
    model.load_state_dict(torch.load(ckpt, map_location='cuda', weights_only=True))
    model.eval()
    res = {}
    margins = {}
    for split in ('val', 'test'):
        for dm in ('trans', 'orig'):
            d = loader.torch_graph(dm, split, 'cuda')
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                lg = model(d['x'], d['edge']).float()
            mg = (lg[:, 1] - lg[:, 0]).cpu().numpy()
            arr = loader.arrays(dm, split)
            y = np.asarray(arr['y']); tr = np.asarray(arr['trusted'])
            margins[(dm, split)] = mg
            v = views_of(split, dm)
            m = view_metrics(mg, y, tr, v)
            m['auc'] = float(roc_auc_score(y[tr], mg[tr])) if tr.sum() and len(np.unique(y[tr])) > 1 else None
            m['pooled_ap'] = float(average_precision_score(y[tr], mg[tr])) if tr.sum() and len(np.unique(y[tr])) > 1 else None
            m['roles'] = role_recall(mg, y, tr, split) if dm == 'trans' else {}
            res[f'{dm}_{split}'] = m
            del d, lg
            torch.cuda.empty_cache()
    # thresholds from val, transfer to test + same-recall diagnostic
    for dm in ('trans', 'orig'):
        yv = np.asarray(loader.arrays(dm, 'val')['y']); tv = np.asarray(loader.arrays(dm, 'val')['trusted'])
        yt = np.asarray(loader.arrays(dm, 'test')['y']); tt = np.asarray(loader.arrays(dm, 'test')['trusted'])
        mv, mt = margins[(dm, 'val')], margins[(dm, 'test')]
        th = thresholds(mv, yv, tv)
        trans = {k: (apply_thr(mt, yt, tt, v['thr']) if v else None) for k, v in th.items()}
        diag = {}
        for k in ('0.8', '0.9', '0.95'):
            need = int(np.ceil(float(k) * (tt & (yt == 1)).sum()))
            if need <= 0:
                diag[k] = None; continue
            thr = float(np.sort(mt[tt & (yt == 1)])[::-1][need - 1])
            diag[k] = apply_thr(mt, yt, tt, thr)
        res[f'{dm}_equal_recall'] = dict(val_thresholds=th, test_transfer=trans, test_diagnostic=diag)
        # normal alarm / cone FPR at the 95% val threshold
        thr95 = th.get('0.95', {}).get('thr') if th.get('0.95') else None
        if thr95 is not None:
            res[f'{dm}_normal'] = dict(
                val=normal_view_fpr(mv, yv, tv, views_of('val', dm), thr95),
                test=normal_view_fpr(mt, yt, tt, views_of('test', dm), thr95))
            if dm == 'trans':
                res['trans_cones_val'] = cone_metrics(mv, 'val', thr95)
                res['trans_cones_test'] = cone_metrics(mt, 'test', thr95)
    res['config'] = dict(ckpt=str(ckpt), arm=arm, seed=seed)
    (OUT / f'OFFLINE_{arm}_s{seed}.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in res.items() if k not in ('config',)}, ensure_ascii=False)[:2000])


if __name__ == '__main__':
    main()
