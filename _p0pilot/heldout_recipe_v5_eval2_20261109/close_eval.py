"""Minimal offline closure for held-out v5: all test recipes (incl id/opt), source-matched comparisons,
normal-FPR at frozen val thresholds, saved predictions and per-source deltas. No training."""
import csv, json, sys
from pathlib import Path
import numpy as np, torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
V5 = R / '_p0pilot/heldout_recipe_v5_20261109'
OUT = R / '_p0pilot/heldout_recipe_v5_eval2_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
OLD = R / '_p0pilot/seed42_nc_ablation_20261109'
sys.path.insert(0, str(V5)); sys.path.insert(0, str(R / '_p0pilot/control_loader_po_20261105'))
sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
import fold_io as F
from evaluate import Model, T
from sklearn.metrics import average_precision_score

RECIPES = ('ys_abc', 'ys_aig', 'ys_nand')
ALL = ('ys_abc', 'ys_aig', 'ys_nand', 'ys_id', 'ys_opt')


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


def per_view_ap(s, g, recipes):
    out = {}
    for v, lay in g['views'].items():
        if rec_of(v) not in recipes:
            continue
        a, b = np.searchsorted(g['rows'], [lay['start'], lay['stop']])
        if b - a < 2:
            continue
        yy, tt, ss = g['y'][a:b], g['trusted'][a:b], s[a:b]
        if len(np.unique(yy[tt])) > 1:
            out[v] = average_precision_score(yy[tt], ss[tt])
    return out


def source_macro(view_aps):
    by_src = {}
    for v, ap in view_aps.items():
        by_src.setdefault(src_of(v), []).append(ap)
    src_ap = {k: float(np.mean(v)) for k, v in by_src.items()}
    return src_ap, (float(np.mean(list(src_ap.values()))) if src_ap else None)


def topk_recipe(s, g, recipe, frac):
    vals = []
    for v, lay in g['views'].items():
        if rec_of(v) != recipe:
            continue
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


def normal_fpr(s, g, thr):
    ctl = [v for v in g['views'] if 'ctl' in v]
    node_fpr = node_num = node_den = 0
    all_fpr = all_num = all_den = 0
    alarm = []
    for v in ctl:
        lay = g['views'][v]
        a, b = np.searchsorted(g['rows'], [lay['start'], lay['stop']])
        tt = g['trusted'][a:b] & g['physical'][a:b]; yy = g['y'][a:b]; ss = s[a:b]
        if not tt.any():
            continue
        alarm.append(float(ss[tt].max() >= thr))
        neg = tt & (yy == 0); node_num += int((ss[neg] >= thr).sum()); node_den += int(neg.sum())
        phys = g['physical'][a:b]; pneg = phys & (yy == 0)
        all_num += int((ss[pneg] >= thr).sum()); all_den += int(pneg.sum())
    return dict(ctl_views=len(ctl), alarm_views=len(alarm),
                view_alarm=(float(np.mean(alarm)) if alarm else None),
                trusted_node_fpr=(float(node_num / node_den) if node_den else None), trusted_den=node_den,
                all_physical_fpr=(float(all_num / all_den) if all_den else None), all_den=all_den)


def main():
    OUT.mkdir(exist_ok=True)
    res = {}
    for rec in RECIPES:
        mean, std = F.fold_stats(rec)
        g = test_graph(mean, std)
        tg = dict(x=torch.as_tensor(g['x'], device='cuda'), edge=torch.as_tensor(g['edge'], device='cuda'))
        seen = tuple(r for r in ALL if r != rec)
        for arm in ('N', 'NC'):
            for tag in ('best', 'last'):
                model = Model().cuda(); model.load_state_dict(torch.load(V5 / rec / arm / f'{tag}.pt', map_location='cuda', weights_only=True)); model.eval()
                with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                    s = (model(tg['x'], tg['edge']).float()[:, 1] - model(tg['x'], tg['edge']).float()[:, 0]).cpu().numpy()
                np.savez_compressed(OUT / f'{rec}_{arm}_{tag}_testpred.npz', scores=s, rows=g['rows'],
                                    y=g['y'], trusted=g['trusted'], physical=g['physical'])
                # val thresholds from saved val preds
                zv = np.load(V5 / rec / arm / f'{tag}_pred.npz'); dv = np.load(F.V4 / f'{rec}_val_map.npz')
                yv, tv = np.asarray(dv['y']), np.asarray(dv['trusted'])
                p = tv & (yv == 1); thresholds = {}
                for tgt in (0.8, 0.9, 0.95):
                    need = int(np.ceil(tgt * p.sum()))
                    thresholds[str(tgt)] = float(np.sort(zv['val'][p])[::-1][need - 1]) if need else None
                ho = per_view_ap(s, g, (rec,)); seen_aps = per_view_ap(s, g, seen)
                ho_src, ho_macro = source_macro(ho); se_src, se_macro = source_macro(seen_aps)
                common = sorted(set(ho_src) & set(se_src))
                entry = dict(heldout_recipe=rec, seen_recipes=list(seen),
                             heldout_source_ap=ho_src, heldout_macro=ho_macro,
                             seen_source_ap=se_src, seen_macro=se_macro,
                             matched_sources=common,
                             matched_heldout_macro=(float(np.mean([ho_src[x] for x in common])) if common else None),
                             matched_seen_macro=(float(np.mean([se_src[x] for x in common])) if common else None),
                             missing_in_seen=sorted(set(ho_src) - set(se_src)),
                             top1={r: topk_recipe(s, g, r, 1) for r in ALL},
                             top5={r: topk_recipe(s, g, r, 5) for r in ALL},
                             normal={k: (normal_fpr(s, g, t) if t else None) for k, t in thresholds.items()},
                             thresholds=thresholds)
                # A/B on heldout recipe only
                hold = np.concatenate([np.arange(g['views'][v]['start'], g['views'][v]['stop'])
                                       for v in g['views'] if rec_of(v) == rec])
                hp = np.zeros(len(g['y']), bool); hn = np.zeros(len(g['y']), bool)
                hp[hold] = g['trusted'][hold] & (g['y'][hold] == 1)
                hn[hold] = g['trusted'][hold] & (g['y'][hold] == 0)
                AB = {}
                for tgt in (0.8, 0.9, 0.95):
                    t = thresholds[str(tgt)]
                    if t is None:
                        AB[str(tgt)] = None; continue
                    need_t = int(np.ceil(tgt * hp.sum())); tt_ = float(np.sort(s[hp])[::-1][need_t - 1])
                    AB[str(tgt)] = dict(A=dict(test_recall=float((s[hp] >= t).sum() / hp.sum()), test_fpr=float((s[hn] >= t).sum() / max(1, hn.sum()))),
                                        B=dict(need=need_t, test_recall=float((s[hp] >= tt_).sum() / hp.sum()), test_fpr=float((s[hn] >= tt_).sum() / max(1, hn.sum()))))
                entry['AB_heldout'] = AB
                res[f'{rec}_{arm}_{tag}'] = entry
                print('DONE', rec, arm, tag, 'ho', round(ho_macro or 0, 4), 'seen', round(se_macro or 0, 4), flush=True)
    (OUT / 'CLOSURE.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    # per-source N/NC delta table (best/last)
    rows = []
    for rec in RECIPES:
        for tag in ('best', 'last'):
            n = res[f'{rec}_N_{tag}']['heldout_source_ap']; c = res[f'{rec}_NC_{tag}']['heldout_source_ap']
            for src in sorted(set(n) & set(c)):
                rows.append(dict(fold=rec, tag=tag, source=src, N=n[src], NC=c[src], delta=c[src] - n[src]))
    with (OUT / 'PER_SOURCE_DELTA.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['fold', 'tag', 'source', 'N', 'NC', 'delta']); w.writeheader(); w.writerows(rows)
    print('CLOSURE_DONE', len(res))


if __name__ == '__main__':
    main()
