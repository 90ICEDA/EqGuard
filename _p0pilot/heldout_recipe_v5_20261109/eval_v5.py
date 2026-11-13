"""Evaluate saved v5 predictions: per-view/source AP, Top-k, D/PO MIL, A/B recall, normal FPR."""
import csv, json, sys
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_recipe_v5_20261109'
V4 = R / '_p0pilot/heldout_recipe_v4_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'
OLD = R / '_p0pilot/seed42_nc_ablation_20261109'
RECIPES = ('ys_abc', 'ys_aig', 'ys_nand')


def views(split):
    c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    return {v['view']: v for v in c['shared_inputs'][f'trans_{split}']['views']}


def per_view(s, rows, y, t, split, source=False):
    out = {}
    for v, lay in views(split).items():
        a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
        if b - a < 2:
            continue
        yy, tt, ss = y[a:b], t[a:b], s[a:b]
        if len(np.unique(yy[tt])) < 2:
            continue
        key = v.split('__ys_')[0] if source else v
        out.setdefault(key, []).append(average_precision_score(yy[tt], ss[tt]))
    return {k: float(np.mean(v)) for k, v in out.items()}


def top1(s, rows, y, t, split):
    vals = []
    for v, lay in views(split).items():
        a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
        tt = t[a:b]; yy = y[a:b]; ss = s[a:b]
        if tt.sum() < 2:
            continue
        order = np.lexsort((np.arange(b - a)[tt], -ss[tt]))
        pos = (yy[tt] == 1)[order]
        k = max(1, int(tt.sum() * 0.01))
        if pos.sum():
            vals.append(float(pos[:k].sum() / pos.sum()))
    return float(np.mean(vals)) if vals else None


def cones(s, rows, y, t, p, split, path):
    out = {}
    loc = {r: i for i, r in enumerate(rows.tolist())}
    for kind in ('D', 'PO'):
        lab, sc = [], []
        with path.open(encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r['split'] != split or r['kind'] != kind or int(r['label']) < 0:
                    continue
                mem = [loc[x] for x in (int(q) for q in r['phys_rows'].split('|') if q) if x in loc]
                mem = [x for x in mem if bool(t[x]) and bool(p[x])]
                if len(mem) < 2:
                    continue
                lab.append(int(r['label'])); sc.append(float(max(s[x] for x in mem)))
        lab = np.array(lab); sc = np.array(sc)
        out[kind] = dict(pos=int(lab.sum()), neg=int((lab == 0).sum()),
                         ap=(float(average_precision_score(lab, sc)) if len(np.unique(lab)) > 1 else None))
    return out


def main():
    res = {}
    for rec in RECIPES:
        for arm in ('N', 'NC'):
            d = json.loads((OUT / rec / arm / 'LOG.json').read_text(encoding='utf-8'))
            for tag in ('best', 'last'):
                z = np.load(OUT / rec / arm / f'{tag}_pred.npz')
                dv = np.load(V4 / f'{rec}_val_map.npz'); dt = np.load(V4 / f'{rec}_test_map.npz')
                yv, tv, pv = np.asarray(dv['y']), np.asarray(dv['trusted']), np.asarray(dv['physical'])
                yt, tt, pt = np.asarray(dt['y']), np.asarray(dt['trusted']), np.asarray(dt['physical'])
                rv, rt = z['val_rows'], z['test_rows']
                sv, st = z['val'], z['test']
                entry = dict(arm=arm, tag=tag, best_step=d['best_step'],
                             val_ap=per_view(sv, rv, yv, tv, 'val'),
                             val_top1=top1(sv, rv, yv, tv, 'val'),
                             test_ap=per_view(st, rt, yt, tt, 'test'),
                             test_top1=top1(st, rt, yt, tt, 'test'),
                             cones_val=cones(sv, rv, yv, tv, pv, 'val', PREP / 'CONE_CACHE_V2.csv'),
                             cones_test=cones(st, rt, yt, tt, pt, 'test', OLD / 'CONE_CACHE_TEST.csv'))
                # A/B recall on trusted physical
                p = tv & pv & (yv == 1); n = tv & pv & (yv == 0)
                tp = tt & pt & (yt == 1); tn = tt & pt & (yt == 0)
                entry['AB'] = {}
                for tgt in (0.8, 0.9, 0.95):
                    k = str(tgt)
                    nv = int(np.ceil(tgt * p.sum())); nt_ = int(np.ceil(tgt * tp.sum()))
                    if nv <= 0 or nt_ <= 0:
                        entry['AB'][k] = None; continue
                    thr = float(np.sort(sv[p])[::-1][nv - 1])
                    thr2 = float(np.sort(st[tp])[::-1][nt_ - 1])
                    entry['AB'][k] = dict(
                        A=dict(test_recall=float((st[tp] >= thr).sum() / tp.sum()),
                               test_fpr=float((st[tn] >= thr).sum() / max(1, tn.sum()))),
                        B=dict(test_recall=float((st[tp] >= thr2).sum() / tp.sum()),
                               test_fpr=float((st[tn] >= thr2).sum() / max(1, tn.sum()))))
                res[f'{rec}_{arm}_{tag}'] = entry
    (OUT / 'RESULTS_EVAL_V5.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    for k, v in res.items():
        va = np.mean(list(v['val_ap'].values())); ta = np.mean(list(v['test_ap'].values()))
        print(k, 'val', round(float(va), 4), 'test', round(float(ta), 4), 'top1', v['test_top1'])


if __name__ == '__main__':
    main()
