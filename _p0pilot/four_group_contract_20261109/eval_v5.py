"""V5: reproducible evaluation from saved scores, all 66 sources, full-source vs trojan-only strict."""
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
TROJAN = ('s38584t100__injalpha_d1_s42', 's38584t100__injdelta_d1_s42', 's38584t100__injepsilon_d1_s42',
          's38584t100__injgamma_d1_s42', 's38584t100__injzeta_d1_s42')
c = json.loads((R / '_p0pilot/control_boundary_v3_20261104/input_contract.json').read_text(encoding='utf-8'))
vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
vv = np.load(OUT / 'val_common.npz'); vp = vv['trusted'] & (vv['y'] == 1); vn = vv['trusted'] & (vv['y'] == 0)


def strict(fam, src, trojan_only):
    sets = []
    for r in fam:
        s = {v.split('__ys_')[0] for v in vs if v.split('__')[-1] == r and (not trojan_only or v.split('__ys_')[0] in TROJAN)}
        sets.append(s)
    inter = sorted(set.intersection(*sets)) if sets else []
    per = {x: float(np.mean([src[x][r] for r in fam if r in src.get(x, {})])) for x in inter if any(r in src.get(x, {}) for r in fam)}
    miss = sorted(set().union(*sets) - set(inter)) if sets else []
    return dict(sources=sorted(per), n=len(per), per_source=per,
                macro=(float(np.mean(list(per.values()))) if per else None), missing=miss)


def main():
    res = {}
    for seed in (42, 1, 2):
        for tag in ('A', 'B'):
            for arm in ('N', 'NC'):
                base = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')
                for point in ('best', 'last'):
                    z = np.load(base / f'{point}_testpred.npz')
                    s, rows, y, t, ph = z['scores'], z['rows'], z['y'], z['trusted'], z['physical']
                    sv = np.load(base / f'{point}_pred.npz')['val']
                    tp = t & (y == 1); tn = t & (y == 0)
                    A = {}
                    for q in (0.8, 0.9, 0.95):
                        need = int(np.ceil(q * vp.sum())); thr = float(np.sort(sv[vp])[::-1][need - 1])
                        A[str(q)] = dict(threshold=thr,
                                         val_recall=float((sv[vp] >= thr).sum() / vp.sum()),
                                         val_fpr=float((sv[vn] >= thr).sum() / vn.sum()),
                                         test_recall=float((s[tp] >= thr).sum() / tp.sum()),
                                         test_fpr=float((s[tn] >= thr).sum() / tn.sum()),
                                         val_pos=int(vp.sum()), val_neg=int(vn.sum()),
                                         test_pos=int(tp.sum()), test_neg=int(tn.sum()))
                    def normal(thr):
                        ct = [v for v in vs if 'ctl' in v]
                        tnum = tden = anum = aden = 0; at, ap = [], []
                        for v in ct:
                            lay = vs[v]; a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                            tt = t[a:b] & ph[a:b]; yy = y[a:b]; ss = s[a:b]
                            if tt.any():
                                at.append(float(ss[tt].max() >= thr)); neg = tt & (yy == 0)
                                tnum += int((ss[neg] >= thr).sum()); tden += int(neg.sum())
                            pn = ph[a:b] & (yy == 0)
                            if pn.any(): ap.append(float(ss[pn].max() >= thr))
                            anum += int((ss[pn] >= thr).sum()); aden += int(pn.sum())
                        return dict(trusted_node_fpr=(None if tden == 0 else tnum / tden), trusted_den=int(tden),
                                    allphys_node_fpr=(None if aden == 0 else anum / aden), allphys_den=int(aden),
                                    trusted_view_alarm=(None if not at else float(np.mean(at))), trusted_views=len(at),
                                    allphys_view_alarm=(None if not ap else float(np.mean(ap))), allphys_views=len(ap))
                    normals = {q: normal(A[q]['threshold']) for q in A}
                    apv, src = {}, {}
                    for v, lay in vs.items():
                        a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                        yy, tt, ss = y[a:b], t[a:b], s[a:b]
                        if len(np.unique(yy[tt])) > 1:
                            apv = apv  # keep
                            src.setdefault(v.split('__ys_')[0], {}).setdefault(v.split('__')[-1], []).append(
                                average_precision_score(yy[tt], ss[tt]))
                    src = {k: {r: float(np.mean(v)) for r, v in d.items()} for k, d in src.items()}
                    ap = {}
                    for r in BASE + ADD:
                        vals = [src[k][r] for k in src if r in src[k]]
                        if vals: ap[r] = float(np.mean(vals))
                    # all 66 sources: fill NA for non-evaluable
                    all_src = sorted({v.split('__ys_')[0] for v in vs})
                    src_full = {k: {r: src.get(k, {}).get(r) for r in BASE + ADD} for k in all_src}
                    res[f'{seed}_{tag}_{arm}_{point}'] = dict(
                        A=A, normal=normals, source_recipe=src_full,
                        base_ap=float(np.mean([ap[r] for r in BASE if r in ap])),
                        add_ap=float(np.mean([ap[r] for r in ADD if r in ap])),
                        strict_full_base=strict(BASE, src, False), strict_full_add=strict(ADD, src, False),
                        strict_trojan_base=strict(BASE, src, True), strict_trojan_add=strict(ADD, src, True))
    # source interaction all 66 per family/point
    inter = {}
    all_src = sorted({v.split('__ys_')[0] for v in vs})
    for point in ('best', 'last'):
        rows_i = []
        for x in all_src:
            for fam, recs in (('base', BASE), ('add', ADD)):
                def m(key):
                    d = res[key]['source_recipe'].get(x, {})
                    vals = [d[r] for r in recs if d.get(r) is not None]
                    return float(np.mean(vals)) if vals else None
                a0, a1 = m(f'42_A_N_{point}'), m(f'42_A_NC_{point}')
                b0, b1 = m(f'42_B_N_{point}'), m(f'42_B_NC_{point}')
                rows_i.append(dict(source=x, family=fam, point=point, A_d=(None if a0 is None or a1 is None else a1 - a0),
                                   B_d=(None if b0 is None or b1 is None else b1 - b0),
                                   I=(None if None in (a0, a1, b0, b1) else (b1 - b0) - (a1 - a0))))
        inter[point] = rows_i
    (OUT / 'FOUR_EVAL_V5.json').write_text(json.dumps(dict(runs=res, source_interaction=inter), indent=2), encoding='utf-8')
    print('done', len(res))


if __name__ == '__main__':
    main()
