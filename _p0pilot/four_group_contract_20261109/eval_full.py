"""Full four-group evaluation (3 seeds, best/last): AP/Top-k/normal FPR/A-B and interaction."""
import json, sys
from pathlib import Path
import numpy as np, torch

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
sys.path.insert(0, str(R / '_p0pilot/control_best200_20261104'))
from evaluate import Model
from sklearn.metrics import average_precision_score

ALL = ('ys_abc', 'ys_aig', 'ys_nand', 'ys_id', 'ys_opt')
BASE = ('ys_abc', 'ys_id', 'ys_opt')
STRICT = ('s38584t100__injalpha_d1_s42', 's38584t100__injepsilon_d1_s42',
          's38584t100__injgamma_d1_s42', 's38584t100__injzeta_d1_s42')


def graph(folder, split, mean, std, view_key):
    c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    vs = {v['view']: v for v in c['shared_inputs'][f'trans_{split}']['views']}
    x = np.load(B / 'inputs' / f'trans_{split}/x39.npy'); edge = np.load(B / 'inputs' / f'trans_{split}/edge_index.npy')
    y = np.load(B / 'inputs' / f'trans_{split}/y.npy'); tr = np.load(B / 'inputs' / f'trans_{split}/trusted.npy'); ph = np.load(B / 'inputs' / f'trans_{split}/physical.npy')
    rows = np.concatenate([np.arange(vs[v]['start'], vs[v]['stop']) for v in vs])
    o2n = np.full(len(y), -1, np.int64); o2n[rows] = np.arange(len(rows))
    m = (o2n[edge[0]] >= 0) & (o2n[edge[1]] >= 0)
    xx = np.array(x[rows], np.float32, copy=True); xx[:, 25:] = np.clip((xx[:, 25:] - mean) / std, -10, 10)
    return dict(x=xx, edge=np.stack([o2n[edge[0][m]], o2n[edge[1][m]]]), y=y[rows], trusted=tr[rows], physical=ph[rows], rows=rows, views=vs)


def metrics(s, g):
    by_rec, by_src = {}, {}
    for v, lay in g['views'].items():
        a, b = np.searchsorted(g['rows'], [lay['start'], lay['stop']])
        yy, tt, ss = g['y'][a:b], g['trusted'][a:b], s[a:b]
        if len(np.unique(yy[tt])) > 1:
            by_rec.setdefault(v.split('__')[-1], []).append(average_precision_score(yy[tt], ss[tt]))
            by_src.setdefault(v.split('__ys_')[0], []).append(average_precision_score(yy[tt], ss[tt]))
    ap = {r: float(np.mean(v)) for r, v in by_rec.items()}
    src = {k: float(np.mean(v)) for k, v in by_src.items()}
    top = {}
    for r in ALL:
        vals = []
        for v, lay in g['views'].items():
            if v.split('__')[-1] != r: continue
            a, b = np.searchsorted(g['rows'], [lay['start'], lay['stop']])
            tt = g['trusted'][a:b]; yy = g['y'][a:b]; ss = s[a:b]
            if tt.sum() < 2: continue
            order = np.lexsort((np.arange(b - a)[tt], -ss[tt])); pos = (yy[tt] == 1)[order]
            for frac in (1, 5):
                k = max(1, int(tt.sum() * frac / 100))
                if pos.sum(): top.setdefault(f'top{frac}', {}).setdefault(r, []).append(float(pos[:k].sum() / pos.sum()))
    top = {k: {r: float(np.mean(v)) for r, v in vv.items()} for k, vv in top.items()}
    return ap, src, top


def normal(s, g, thr):
    ctl = [v for v in g['views'] if 'ctl' in v]
    tn = td = an = ad = 0; alarm = []
    for v in ctl:
        lay = g['views'][v]; a, b = np.searchsorted(g['rows'], [lay['start'], lay['stop']])
        tt = g['trusted'][a:b] & g['physical'][a:b]; yy = g['y'][a:b]; ss = s[a:b]
        if tt.any():
            alarm.append(float(ss[tt].max() >= thr))
            neg = tt & (yy == 0); tn += int((ss[neg] >= thr).sum()); td += int(neg.sum())
        ph = g['physical'][a:b]; pn = ph & (yy == 0); an += int((ss[pn] >= thr).sum()); ad += int(pn.sum())
    return dict(trusted_fpr=tn / max(1, td), all_phys_fpr=an / max(1, ad),
                view_alarm=float(np.mean(alarm)) if alarm else None, ctl=len(ctl))


def main():
    mean, std = np.load(OUT / 'group_A.npz')['mean'], np.load(OUT / 'group_A.npz')['std']
    gv = graph('', 'val', mean, std, None); gt = graph('', 'test', mean, std, None)
    vx = torch.as_tensor(gv['x'], device='cuda'); ve = torch.as_tensor(gv['edge'], device='cuda')
    tx = torch.as_tensor(gt['x'], device='cuda'); te = torch.as_tensor(gt['edge'], device='cuda')
    res = {}
    for seed in (42, 1, 2):
        for tag in ('A', 'B'):
            for arm in ('N', 'NC'):
                base = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')
                for point in ('best', 'last'):
                    f = base / f'{point}_resume.pt'
                    if not f.exists():
                        continue
                    ck = torch.load(f, map_location='cuda', weights_only=False)
                    model = Model().cuda(); model.load_state_dict(ck['model']); model.eval()
                    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                        lv = model(vx, ve).float(); sv = (lv[:, 1] - lv[:, 0]).cpu().numpy()
                        lt = model(tx, te).float(); st = (lt[:, 1] - lt[:, 0]).cpu().numpy()
                    ap, src, top = metrics(st, gt)
                    p = (gv['trusted'] & (gv['y'] == 1)); need = int(np.ceil(0.95 * p.sum()))
                    thr = float(np.sort(sv[p])[::-1][need - 1])
                    nrm = normal(st, gt, thr)
                    # B: test-positive need
                    tp = gt['trusted'] & (gt['y'] == 1); tn = gt['trusted'] & (gt['y'] == 0)
                    nt = int(np.ceil(0.95 * tp.sum())); thr2 = float(np.sort(st[tp])[::-1][nt - 1])
                    res[f'{seed}_{tag}_{arm}_{point}'] = dict(
                        ap=ap, source_ap=src, top=top, base_ap=float(np.mean([ap[r] for r in BASE if r in ap])),
                        add_ap=float(np.mean([ap[r] for r in ('ys_aig', 'ys_nand') if r in ap])),
                        normal=nrm,
                        A=dict(test_recall=float((st[tp] >= thr).sum() / tp.sum()), test_fpr=float((st[tn] >= thr).sum() / tn.sum())),
                        B=dict(test_recall=float((st[tp] >= thr2).sum() / tp.sum()), test_fpr=float((st[tn] >= thr2).sum() / tn.sum())))
                    print('EVAL', seed, tag, arm, point, round(res[f'{seed}_{tag}_{arm}_{point}']['base_ap'], 4), flush=True)
    (OUT / 'FOUR_EVAL_ALL.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    # interaction per seed/point
    print('--- interaction base / add ---')
    for seed in (42, 1, 2):
        for point in ('best', 'last'):
            try:
                b0 = res[f'{seed}_B_N_{point}']['base_ap']; b1 = res[f'{seed}_B_NC_{point}']['base_ap']
                a0 = res[f'{seed}_A_N_{point}']['base_ap']; a1 = res[f'{seed}_A_NC_{point}']['base_ap']
                print(seed, point, 'base', round((b1 - b0) - (a1 - a0), 4),
                      'add', round((res[f'{seed}_B_NC_{point}']['add_ap'] - res[f'{seed}_B_N_{point}']['add_ap']) -
                                   (res[f'{seed}_A_NC_{point}']['add_ap'] - res[f'{seed}_A_N_{point}']['add_ap']), 4))
            except KeyError:
                pass


if __name__ == '__main__':
    main()
