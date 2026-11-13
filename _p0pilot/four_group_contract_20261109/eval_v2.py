"""Corrected three-seed evaluation: val_common thresholds only, full best/last metrics, saved predictions."""
import csv, json, sys
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
ADD = ('ys_aig', 'ys_nand')
SEEN = ('ys_aig', 'ys_nand', 'ys_id', 'ys_opt')


def main():
    c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
    folder = B / 'inputs/trans_test'
    x = np.load(folder / 'x39.npy'); edge = np.load(folder / 'edge_index.npy')
    y = np.load(folder / 'y.npy'); tr = np.load(folder / 'trusted.npy'); ph = np.load(folder / 'physical.npy')
    rows = np.concatenate([np.arange(vs[v]['start'], vs[v]['stop']) for v in vs])
    o2n = np.full(len(y), -1, np.int64); o2n[rows] = np.arange(len(rows))
    m = (o2n[edge[0]] >= 0) & (o2n[edge[1]] >= 0)
    A = np.load(OUT / 'group_A.npz'); mean, std = A['mean'], A['std']
    xx = np.array(x[rows], np.float32, copy=True); xx[:, 25:] = np.clip((xx[:, 25:] - mean) / std, -10, 10)
    gt = dict(x=xx, edge=np.stack([o2n[edge[0][m]], o2n[edge[1][m]]]), y=y[rows], trusted=tr[rows], physical=ph[rows], rows=rows, views=vs)
    vv = np.load(OUT / 'val_common.npz')
    res = {}
    for seed in (42, 1, 2):
        for tag in ('A', 'B'):
            for arm in ('N', 'NC'):
                base = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')
                for point in ('best', 'last'):
                    f = base / f'{point}_resume.pt'
                    if not f.exists(): continue
                    ck = torch.load(f, map_location='cuda', weights_only=False)
                    model = Model().cuda(); model.load_state_dict(ck['model']); model.eval()
                    tx = torch.as_tensor(gt['x'], device='cuda'); te = torch.as_tensor(gt['edge'], device='cuda')
                    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                        lg = model(tx, te).float(); s = (lg[:, 1] - lg[:, 0]).cpu().numpy()
                    np.savez_compressed(base / f'{point}_testpred.npz', scores=s, rows=gt['rows'], y=gt['y'],
                                        trusted=gt['trusted'], physical=gt['physical'])
                    sv = np.load(base / f'{point}_pred.npz')['val']
                    p = vv['trusted'] & (vv['y'] == 1)
                    th = {}
                    for t in (0.8, 0.9, 0.95):
                        need = int(np.ceil(t * p.sum()))
                        th[str(t)] = float(np.sort(sv[p])[::-1][need - 1]) if need else None
                    # per recipe/source AP
                    ap_rec, ap_src, top = {}, {}, {}
                    for v, lay in gt['views'].items():
                        a, b = np.searchsorted(gt['rows'], [lay['start'], lay['stop']])
                        yy, tt, ss = gt['y'][a:b], gt['trusted'][a:b], s[a:b]
                        if len(np.unique(yy[tt])) < 2: continue
                        apv = average_precision_score(yy[tt], ss[tt])
                        ap_rec.setdefault(v.split('__')[-1], []).append(apv)
                        ap_src.setdefault(v.split('__ys_')[0], []).append(apv)
                        order = np.lexsort((np.arange(b - a)[tt], -ss[tt])); pos = (yy[tt] == 1)[order]
                        for frac in (1, 5):
                            k = max(1, int(tt.sum() * frac / 100))
                            if pos.sum(): top.setdefault(f'top{frac}', {}).setdefault(v.split('__')[-1], []).append(float(pos[:k].sum() / pos.sum()))
                    ap_rec = {k: float(np.mean(v)) for k, v in ap_rec.items()}
                    ap_src = {k: float(np.mean(v)) for k, v in ap_src.items()}
                    top = {k: {r: float(np.mean(v)) for r, v in vv_.items()} for k, vv_ in top.items()}
                    # strict source intersection over 4 seen recipes on heldout test host
                    seen_sources = None
                    for rec in SEEN:
                        sset = {v.split('__ys_')[0] for v in gt['views'] if v.split('__')[-1] == rec}
                        seen_sources = sset if seen_sources is None else (seen_sources & sset)
                    strict = sorted(seen_sources & set(ap_src))
                    strict_ap = float(np.mean([ap_src[x] for x in strict])) if strict else None
                    # normal metrics
                    def nrm(thr):
                        ctl = [v for v in gt['views'] if 'ctl' in v]
                        tn = td = an = ad = 0; alarm = []
                        for v in ctl:
                            lay = gt['views'][v]; a, b = np.searchsorted(gt['rows'], [lay['start'], lay['stop']])
                            tt = gt['trusted'][a:b] & gt['physical'][a:b]; yy = gt['y'][a:b]; ss = s[a:b]
                            if tt.any():
                                alarm.append(float(ss[tt].max() >= thr)); neg = tt & (yy == 0)
                                tn += int((ss[neg] >= thr).sum()); td += int(neg.sum())
                            pn = gt['physical'][a:b] & (yy == 0)
                            an += int((ss[pn] >= thr).sum()); ad += int(pn.sum())
                        return dict(trusted_fpr=tn / max(1, td), all_phys_fpr=an / max(1, ad),
                                    view_alarm=float(np.mean(alarm)) if alarm else None, ctl=len(ctl), supports=[td, ad])
                    normals = {k: nrm(v) for k, v in th.items() if v is not None}
                    tp = gt['trusted'] & (gt['y'] == 1); tn2 = gt['trusted'] & (gt['y'] == 0)
                    Bdiag = {}
                    for t in (0.8, 0.9, 0.95):
                        need = int(np.ceil(t * tp.sum()))
                        thr = float(np.sort(s[tp])[::-1][need - 1]) if need else None
                        Bdiag[str(t)] = dict(threshold=thr, recall=float((s[tp] >= thr).sum() / tp.sum()),
                                             fpr=float((s[tn2] >= thr).sum() / max(1, tn2.sum()))) if thr else None
                    res[f'{seed}_{tag}_{arm}_{point}'] = dict(ap_recipe=ap_rec, ap_source=ap_src, top=top,
                                                             base_ap=float(np.mean([ap_rec[r] for r in BASE if r in ap_rec])),
                                                             add_ap=float(np.mean([ap_rec[r] for r in ADD if r in ap_rec])),
                                                             strict_sources=strict, strict_ap=strict_ap,
                                                             thresholds=th, normal=normals, B=Bdiag,
                                                             supports=dict(val_pos=int(p.sum()), test_pos=int(tp.sum())))
                    print('EVAL', seed, tag, arm, point, round(res[f'{seed}_{tag}_{arm}_{point}']['base_ap'], 4), flush=True)
    (OUT / 'FOUR_EVAL_V2.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    print('done', len(res))


if __name__ == '__main__':
    main()
