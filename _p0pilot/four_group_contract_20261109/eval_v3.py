"""Evaluation closure v3 from saved predictions: A fields, two view-alarm scopes,
source x recipe matrix, per-source base/add interactions, strict sets; plus self-audit."""
import json, csv
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
ALL = ('ys_abc', 'ys_aig', 'ys_nand', 'ys_id', 'ys_opt')
BASE = ('ys_abc', 'ys_id', 'ys_opt')
ADD = ('ys_aig', 'ys_nand')


def main():
    vv = np.load(OUT / 'val_common.npz')
    vp = vv['trusted'] & (vv['y'] == 1)
    res = {}
    for seed in (42, 1, 2):
        for tag in ('A', 'B'):
            for arm in ('N', 'NC'):
                base = OUT / (f'run_{tag}_{arm}' if seed == 42 else f'run_{tag}_{arm}_s{seed}')
                for point in ('best', 'last'):
                    z = np.load(base / f'{point}_testpred.npz')
                    s, rows, y, t, ph = z['scores'], z['rows'], z['y'], z['trusted'], z['physical']
                    sv = np.load(base / f'{point}_pred.npz')['val']
                    th = {}
                    for q in (0.8, 0.9, 0.95):
                        need = int(np.ceil(q * vp.sum()))
                        th[str(q)] = float(np.sort(sv[vp])[::-1][need - 1])
                    # A transfer
                    tp = t & (y == 1); tn = t & (y == 0)
                    A = {}
                    for q, thr in th.items():
                        A[q] = dict(threshold=thr, val_recall=float(q), val_pos=int(vp.sum()),
                                    test_recall=float((s[tp] >= thr).sum() / tp.sum()),
                                    test_fpr=float((s[tn] >= thr).sum() / max(1, tn.sum())),
                                    test_pos=int(tp.sum()))
                    # B test same recall
                    B = {}
                    for q in ('0.8', '0.9', '0.95'):
                        need = int(np.ceil(float(q) * tp.sum()))
                        thr = float(np.sort(s[tp])[::-1][need - 1])
                        B[q] = dict(threshold=thr, need=need, test_recall=float((s[tp] >= thr).sum() / tp.sum()),
                                    test_fpr=float((s[tn] >= thr).sum() / max(1, tn.sum())), test_pos=int(tp.sum()))
                    # per view AP + alarms
                    ap, mat = {}, {}
                    alarm_t, alarm_p = [], []
                    for v, lay in z['views'].items() if 'views' in z.files else []:
                        pass
                    import json as _j
                    c = _j.loads((R / '_p0pilot/control_boundary_v3_20261104/input_contract.json').read_text(encoding='utf-8'))
                    vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
                    for v, lay in vs.items():
                        a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                        yy, tt, pp, ss = y[a:b], t[a:b], ph[a:b], s[a:b]
                        if len(np.unique(yy[tt])) > 1:
                            apv = average_precision_score(yy[tt], ss[tt])
                            ap.setdefault(v.split('__')[-1], []).append(apv)
                            mat.setdefault(v.split('__ys_')[0], {}).setdefault(v.split('__')[-1], []).append(apv)
                        if 'ctl' in v and tt.any():
                            alarm_t.append(float(ss[tt].max() >= th['0.95']))
                            alarm_p.append(float(ss[pp].max() >= th['0.95']) if pp.any() else 0.0)
                    ap = {k: float(np.mean(v_)) for k, v_ in ap.items()}
                    mat = {k: {r: float(np.mean(v_)) for r, v_ in d.items()} for k, d in mat.items()}
                    base_ap = float(np.mean([ap[r] for r in BASE if r in ap]))
                    add_ap = float(np.mean([ap[r] for r in ADD if r in ap]))
                    # strict source intersection per recipe-family
                    def strict(fam):
                        sets = [{v.split('__ys_')[0] for v in vs if v.split('__')[-1] == r} for r in fam]
                        inter = set.intersection(*sets)
                        return sorted(inter)
                    sb, sa = strict(BASE), strict(ADD)
                    def mac(srcs, fam):
                        vals = [mat[x][r] for x in srcs for r in fam if r in mat.get(x, {})]
                        return float(np.mean(vals)) if vals else None
                    res[f'{seed}_{tag}_{arm}_{point}'] = dict(A=A, B=B, ap_recipe=ap, source_recipe=mat,
                                                             base_ap=base_ap, add_ap=add_ap,
                                                             strict_base=sb, strict_add=sa,
                                                             strict_base_macro=mac(sb, BASE), strict_add_macro=mac(sa, ADD),
                                                             alarm_trusted=float(np.mean(alarm_t)) if alarm_t else None,
                                                             alarm_allphys=float(np.mean(alarm_p)) if alarm_p else None,
                                                             normal_views=len(alarm_t),
                                                             base_ap_no_recipe=base_ap, add_ap_no_recipe=add_ap)
    (OUT / 'FOUR_EVAL_V3.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    print('done', len(res))


if __name__ == '__main__':
    main()
