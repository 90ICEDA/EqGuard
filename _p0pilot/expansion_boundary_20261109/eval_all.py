"""Seed1/2 full-test inference (all recipes) + per-recipe/source metrics; expansion stats.
No training."""
import json, sys
from pathlib import Path
import numpy as np, torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
V5 = R / '_p0pilot/heldout_recipe_v5_20261109'
OUT = R / '_p0pilot/expansion_boundary_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0, str(V5)); sys.path.insert(0, str(R / '_p0pilot/control_loader_po_20261105'))
sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
import fold_io as F
from evaluate import Model, T
from sklearn.metrics import average_precision_score

ALL = ('ys_abc', 'ys_aig', 'ys_nand', 'ys_id', 'ys_opt')
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


def rec_of(v): return v.split('__')[-1]
def src_of(v): return v.split('__ys_')[0]


def per_view(s, g):
    out = {}
    for v, lay in g['views'].items():
        a, b = np.searchsorted(g['rows'], [lay['start'], lay['stop']])
        if b - a < 2: continue
        yy, tt, ss = g['y'][a:b], g['trusted'][a:b], s[a:b]
        if len(np.unique(yy[tt])) > 1:
            out[v] = average_precision_score(yy[tt], ss[tt])
    return out


def main():
    OUT.mkdir(exist_ok=True)
    res = {}
    for rec in RECIPES:
        mean, std = F.fold_stats(rec); g = test_graph(mean, std)
        tg = dict(x=torch.as_tensor(g['x'], device='cuda'), edge=torch.as_tensor(g['edge'], device='cuda'))
        for arm in ('N', 'NC'):
            for seed in (1, 2):
                for tag in ('best', 'last'):
                    ck = torch.load(V5 / rec / arm / f'seed{seed}' / f'{tag}_resume.pt', map_location='cuda', weights_only=False)
                    model = Model().cuda(); model.load_state_dict(ck['model']); model.eval()
                    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                        lg = model(tg['x'], tg['edge']).float(); s = (lg[:, 1] - lg[:, 0]).cpu().numpy()
                    np.savez_compressed(OUT / f'{rec}_{arm}_s{seed}_{tag}_alltest.npz', scores=s, rows=g['rows'], y=g['y'], trusted=g['trusted'], physical=g['physical'])
                    va = per_view(s, g)
                    by_rec = {r: float(np.mean([v for k, v in va.items() if rec_of(k) == r])) if any(rec_of(k) == r for k in va) else None for r in ALL}
                    by_src = {}
                    for k, v in va.items():
                        by_src.setdefault(src_of(k), []).append(v)
                    src_ap = {k: float(np.mean(v)) for k, v in by_src.items()}
                    ho = {}
                    for k, v in va.items():
                        if rec_of(k) == rec:
                            ho.setdefault(src_of(k), []).append(v)
                    ho_src = {k: float(np.mean(v)) for k, v in ho.items()}
                    res[f'{rec}_{arm}_{seed}_{tag}'] = dict(by_recipe=by_rec, source_ap=src_ap, heldout_src=ho_src,
                                                            heldout_macro=float(np.mean(list(ho_src.values()))) if ho_src else None,
                                                            model_opt_step=ck.get('completed'))
    (OUT / 'SEEDS12_ALLRECIPE.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    print('done', len(res))


if __name__ == '__main__':
    main()
