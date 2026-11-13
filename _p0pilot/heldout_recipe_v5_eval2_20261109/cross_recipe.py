"""Offline cross-recipe diagnostic for the held-out v5 models (no training).
Runs each fold's best/last model on ALL test-host recipes with that fold's normalization."""
import json, sys
from pathlib import Path
import numpy as np, torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
V5 = R / '_p0pilot/heldout_recipe_v5_20261109'
OUT = R / '_p0pilot/heldout_recipe_v5_eval2_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
OLD = R / '_p0pilot/seed42_nc_ablation_20261109'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'
sys.path.insert(0, str(V5)); sys.path.insert(0, str(R / '_p0pilot/control_loader_po_20261105'))
sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
import fold_io as F
from evaluate import Model, T
from sklearn.metrics import average_precision_score

RECIPES = ('ys_abc', 'ys_aig', 'ys_nand')


def test_graph(mean, std):
    c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
    folder = B / 'inputs/trans_test'
    x = np.load(folder / 'x39.npy'); edge = np.load(folder / 'edge_index.npy')
    y = np.load(folder / 'y.npy'); tr = np.load(folder / 'trusted.npy'); ph = np.load(folder / 'physical.npy')
    rows = np.concatenate([np.arange(vs[v]['start'], vs[v]['stop']) for v in vs])
    o2n = np.full(len(y), -1, np.int64); o2n[rows] = np.arange(len(rows))
    m = (o2n[edge[0]] >= 0) & (o2n[edge[1]] >= 0)
    return dict(x=F.norm(x[rows], mean, std), edge=np.stack([o2n[edge[0][m]], o2n[edge[1][m]]]),
                y=y[rows], trusted=tr[rows], physical=ph[rows], rows=rows, views=vs)


def per_view(s, g, recipe=None):
    out = {}
    for v, lay in g['views'].items():
        if recipe and lay['view'].split('__')[-1] != recipe:
            continue
        a, b = np.searchsorted(g['rows'], [lay['start'], lay['stop']])
        if b - a < 2:
            continue
        yy, tt, ss = g['y'][a:b], g['trusted'][a:b], s[a:b]
        if len(np.unique(yy[tt])) > 1:
            key = v.split('__ys_')[0]
            out.setdefault(key, []).append(average_precision_score(yy[tt], ss[tt]))
    return {k: float(np.mean(v)) for k, v in out.items()}


def topk(s, g, frac):
    vals = []
    for v, lay in g['views'].items():
        a, b = np.searchsorted(g['rows'], [lay['start'], lay['stop']])
        tt = g['trusted'][a:b]; yy = g['y'][a:b]; ss = s[a:b]
        if tt.sum() < 2:
            continue
        order = np.lexsort((np.arange(b - a)[tt], -ss[tt]))
        pos = (yy[tt] == 1)[order]
        k = max(1, int(tt.sum() * frac / 100))
        if pos.sum():
            vals.append(float(pos[:k].sum() / pos.sum()))
    return float(np.mean(vals)) if vals else None


def cones(s, g, thr):
    out = {}
    loc = {r: i for i, r in enumerate(g['rows'].tolist())}
    for kind in ('D', 'PO'):
        lab, sc = [], []
        import csv
        with (OLD / 'CONE_CACHE_TEST.csv').open(encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r['split'] != 'test' or r['kind'] != kind or int(r['label']) < 0:
                    continue
                mem = [loc[x] for x in (int(q) for q in r['phys_rows'].split('|') if q) if x in loc]
                mem = [x for x in mem if bool(g['trusted'][x]) and bool(g['physical'][x])]
                if len(mem) < 2:
                    continue
                lab.append(int(r['label'])); sc.append(float(max(s[x] for x in mem)))
        lab = np.array(lab); sc = np.array(sc)
        out[kind] = dict(pos=int(lab.sum()), neg=int((lab == 0).sum()),
                         ap=(float(average_precision_score(lab, sc)) if len(np.unique(lab)) > 1 else None),
                         fpr=(float((sc[lab == 0] >= thr).sum() / max(1, (lab == 0).sum())) if thr else None))
    return out


def main():
    OUT.mkdir(exist_ok=True)
    res = {}
    for rec in RECIPES:
        mean, std = F.fold_stats(rec)
        g = test_graph(mean, std)
        torch_g = dict(x=torch.as_tensor(g['x'], device='cuda'), edge=torch.as_tensor(g['edge'], device='cuda'))
        for arm in ('N', 'NC'):
            for tag in ('best', 'last'):
                model = Model().cuda(); model.load_state_dict(torch.load(V5 / rec / arm / f'{tag}.pt', map_location='cuda', weights_only=True))
                model.eval()
                with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                    s = (model(torch_g['x'], torch_g['edge']).float()[:, 1] - model(torch_g['x'], torch_g['edge']).float()[:, 0]).cpu().numpy()
                z = np.load(V5 / rec / arm / f'{tag}_pred.npz')
                sv = z['val']; yv = np.asarray(np.load(F.V4 / f'{rec}_val_map.npz')['y']); tv = np.asarray(np.load(F.V4 / f'{rec}_val_map.npz')['trusted'])
                p = tv & (yv == 1); need = int(np.ceil(0.95 * p.sum()))
                thr = float(np.sort(sv[p])[::-1][need - 1]) if need else None
                entry = dict(val_thr95=thr,
                             heldout=per_view(s, g, rec),
                             seen={r: per_view(s, g, r) for r in RECIPES if r != rec},
                             all_recipes=per_view(s, g),
                             top1=topk(s, g, 1), top5=topk(s, g, 5),
                             cones=cones(s, g, thr))
                res[f'{rec}_{arm}_{tag}'] = entry
    (OUT / 'CROSS_RECIPE.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    for k, v in res.items():
        ho = np.mean(list(v['heldout'].values())) if v['heldout'] else float('nan')
        se = [np.mean(list(x.values())) for x in v['seen'].values() if x]
        print(k, 'heldout', round(float(ho), 4), 'seen-mean', round(float(np.mean(se)), 4) if se else None)


if __name__ == '__main__':
    main()
