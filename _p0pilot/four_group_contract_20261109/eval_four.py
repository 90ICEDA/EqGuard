"""Evaluate four groups on all test recipes: AP, top1/5, normal FPR, interaction."""
import json, sys
from pathlib import Path
import numpy as np, torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
from evaluate import Model, T
from sklearn.metrics import average_precision_score

ALL = ('ys_abc', 'ys_aig', 'ys_nand', 'ys_id', 'ys_opt')


def test_graph():
    c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
    folder = B / 'inputs/trans_test'
    x = np.load(folder / 'x39.npy'); edge = np.load(folder / 'edge_index.npy')
    y = np.load(folder / 'y.npy'); tr = np.load(folder / 'trusted.npy'); ph = np.load(folder / 'physical.npy')
    rows = np.concatenate([np.arange(vs[v]['start'], vs[v]['stop']) for v in vs])
    A = np.load(OUT / 'group_A.npz'); mean, std = A['mean'], A['std']
    xx = np.array(x[rows], np.float32, copy=True); xx[:, 25:] = np.clip((xx[:, 25:] - mean) / std, -10, 10)
    o2n = np.full(len(y), -1, np.int64); o2n[rows] = np.arange(len(rows))
    m = (o2n[edge[0]] >= 0) & (o2n[edge[1]] >= 0)
    return dict(x=xx, edge=np.stack([o2n[edge[0][m]], o2n[edge[1][m]]]), y=y[rows], trusted=tr[rows], physical=ph[rows], rows=rows, views=vs)


def main():
    g = test_graph(); tg = dict(x=torch.as_tensor(g['x'], device='cuda'), edge=torch.as_tensor(g['edge'], device='cuda'))
    res = {}
    for tag in ('A', 'B'):
        for arm in ('N', 'NC'):
            ck = torch.load(OUT / f'run_{tag}_{arm}' / 'best_resume.pt', map_location='cuda', weights_only=False)
            model = Model().cuda(); model.load_state_dict(ck['model']); model.eval()
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                lg = model(tg['x'], tg['edge']).float(); s = (lg[:, 1] - lg[:, 0]).cpu().numpy()
            np.savez_compressed(OUT / f'run_{tag}_{arm}' / 'test_pred.npz', scores=s, rows=g['rows'], y=g['y'], trusted=g['trusted'], physical=g['physical'])
            by = {}
            for v, lay in g['views'].items():
                a, b = np.searchsorted(g['rows'], [lay['start'], lay['stop']])
                yy, tt, ss = g['y'][a:b], g['trusted'][a:b], s[a:b]
                if len(np.unique(yy[tt])) > 1:
                    by.setdefault(v.split('__')[-1], []).append(average_precision_score(yy[tt], ss[tt]))
            ap = {r: float(np.mean(by[r])) for r in by}
            # top1 per recipe
            t1 = {}
            for r in ALL:
                vals = []
                for v, lay in g['views'].items():
                    if v.split('__')[-1] != r: continue
                    a, b = np.searchsorted(g['rows'], [lay['start'], lay['stop']])
                    tt = g['trusted'][a:b]; yy = g['y'][a:b]; ss = s[a:b]
                    if tt.sum() < 2: continue
                    order = np.lexsort((np.arange(b - a)[tt], -ss[tt])); pos = (yy[tt] == 1)[order]
                    k = max(1, int(tt.sum() * 1 / 100))
                    if pos.sum(): vals.append(float(pos[:k].sum() / pos.sum()))
                t1[r] = float(np.mean(vals)) if vals else None
            # normal FPR at 95% val threshold
            z = np.load(OUT / f'run_{tag}_{arm}' / 'best_pred.npz'); vv = np.load(OUT / 'val_common.npz')
            p = np.asarray(vv['trusted']) & (np.asarray(vv['y']) == 1); need = int(np.ceil(0.95 * p.sum()))
            thr = float(np.sort(z['val'][p])[::-1][need - 1])
            ctl = [v for v in g['views'] if 'ctl' in v]
            num = den = 0; alarm = []
            for v in ctl:
                lay = g['views'][v]; a, b = np.searchsorted(g['rows'], [lay['start'], lay['stop']])
                tt = g['trusted'][a:b] & g['physical'][a:b]; yy = g['y'][a:b]; ss = s[a:b]
                if not tt.any(): continue
                alarm.append(float(ss[tt].max() >= thr)); neg = tt & (yy == 0)
                num += int((ss[neg] >= thr).sum()); den += int(neg.sum())
            res[f'{tag}_{arm}'] = dict(ap=ap, top1=t1, normal_node_fpr=float(num / max(1, den)),
                                       normal_view_alarm=float(np.mean(alarm)) if alarm else None,
                                       base_ap=float(np.mean([ap[r] for r in ('ys_abc', 'ys_id', 'ys_opt') if r in ap])),
                                       add_ap=float(np.mean([ap[r] for r in ('ys_aig', 'ys_nand') if r in ap])))
    (OUT / 'FOUR_RESULTS.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    for k, v in res.items():
        print(k, 'base', round(v['base_ap'], 4), 'add', round(v['add_ap'], 4), 'normal', round(v['normal_node_fpr'], 4))
    inter = (res['B_NC']['base_ap'] - res['B_N']['base_ap']) - (res['A_NC']['base_ap'] - res['A_N']['base_ap'])
    print('interaction(base)', inter)


if __name__ == '__main__':
    main()
