"""V4 evaluation: actual val/test recall & FPR, 4 normal fields (NA on zero support),
per-recipe strict source intersections, per-source NC-N and interaction."""
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import average_precision_score

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/four_group_contract_20261109'
ALL = ('ys_abc', 'ys_aig', 'ys_nand', 'ys_id', 'ys_opt')
BASE = ('ys_abc', 'ys_id', 'ys_opt'); ADD = ('ys_aig', 'ys_nand')
c = json.loads((R / '_p0pilot/control_boundary_v3_20261104/input_contract.json').read_text(encoding='utf-8'))
vs = {v['view']: v for v in c['shared_inputs']['trans_test']['views']}
vv = np.load(OUT / 'val_common.npz'); vp = vv['trusted'] & (vv['y'] == 1); vn = vv['trusted'] & (vv['y'] == 0)


def ratios(score, pos, neg, thr):
    return (None if pos.sum() == 0 else float((score[pos] >= thr).sum() / pos.sum()),
            None if neg.sum() == 0 else float((score[neg] >= thr).sum() / neg.sum()),
            int(pos.sum()), int(neg.sum()))


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
                        vr, vf, vpos, vneg = ratios(sv, vp, vn, thr)
                        tr_, tf, tpos, tneg = ratios(s, tp, tn, thr)
                        A[str(q)] = dict(threshold=thr, val_recall=vr, val_fpr=vf, val_pos=vpos, val_neg=vneg,
                                         test_recall=tr_, test_fpr=tf, test_pos=tpos, test_neg=tneg)
                    # normal: node FPR + view alarm, trusted and all-physical separately
                    def normal(thr):
                        ct = [v for v in vs if 'ctl' in v]
                        tnum = tden = anum = aden = 0
                        at, ap = [], []
                        for v in ct:
                            lay = vs[v]; a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                            tt = t[a:b] & ph[a:b]; yy = y[a:b]; ss = s[a:b]
                            if tt.any():
                                at.append(float(ss[tt].max() >= thr))
                                neg = tt & (yy == 0); tnum += int((ss[neg] >= thr).sum()); tden += int(neg.sum())
                            pn = ph[a:b] & (yy == 0)
                            if pn.any(): ap.append(float(ss[pn].max() >= thr))
                            anum += int((ss[pn] >= thr).sum()); aden += int(pn.sum())
                        return dict(trusted_node_fpr=(None if tden == 0 else tnum / tden), trusted_den=tden,
                                    allphys_node_fpr=(None if aden == 0 else anum / aden), allphys_den=aden,
                                    trusted_view_alarm=(None if not at else float(np.mean(at))), trusted_views=len(at),
                                    allphys_view_alarm=(None if not ap else float(np.mean(ap))), allphys_views=len(ap))
                    normals = {q: normal(A[q]['threshold']) for q in A}
                    # per recipe/source AP
                    apv, src_rec = {}, {}
                    for v, lay in vs.items():
                        a, b = np.searchsorted(rows, [lay['start'], lay['stop']])
                        yy, tt, ss = y[a:b], t[a:b], s[a:b]
                        if len(np.unique(yy[tt])) > 1:
                            val = average_precision_score(yy[tt], ss[tt])
                            apv.setdefault(v.split('__')[-1], []).append(val)
                            src_rec.setdefault(v.split('__ys_')[0], {}).setdefault(v.split('__')[-1], []).append(val)
                    ap = {r: float(np.mean(v)) for r, v in apv.items()}
                    src = {k: {r: float(np.mean(v)) for r, v in d.items()} for k, d in src_rec.items()}
                    def strict(fam):
                        sets = [{v.split('__ys_')[0] for v in vs if v.split('__')[-1] == r} for r in fam]
                        inter = sorted(set.intersection(*sets)) if sets else []
                        per = {}
                        for x in inter:
                            vals = [src[x][r] for r in fam if r in src.get(x, {})]
                            if vals:
                                per[x] = float(np.mean(vals))
                        macro = float(np.mean(list(per.values()))) if per else None
                        miss = sorted(set().union(*sets) - set(inter)) if sets else []
                        return dict(sources=sorted(per), n=len(per), per_source=per, macro=macro, missing=miss)
                    res[f'{seed}_{tag}_{arm}_{point}'] = dict(A=A, normal=normals, ap_recipe=ap, source_recipe=src,
                                                             base_ap=float(np.mean([ap[r] for r in BASE if r in ap])),
                                                             add_ap=float(np.mean([ap[r] for r in ADD if r in ap])),
                                                             strict_base=strict(BASE), strict_add=strict(ADD))
    # per-source interaction (best/last), per family
    inter = {}
    for point in ('best', 'last'):
        rows_i = []
        for x in sorted({k for k in (res[f'42_A_N_{point}']['source_recipe'] if False else [])} or
                        set(res[f'42_A_N_{point}']['source_recipe'])):
            for fam, recs in (('base', BASE), ('add', ADD)):
                a0 = res[f'42_A_N_{point}']['source_recipe'].get(x, {}); a1 = res[f'42_A_NC_{point}']['source_recipe'].get(x, {})
                b0 = res[f'42_B_N_{point}']['source_recipe'].get(x, {}); b1 = res[f'42_B_NC_{point}']['source_recipe'].get(x, {})
                if not (a0 and a1 and b0 and b1): continue
                va0 = float(np.mean([a0[r] for r in recs if r in a0])); va1 = float(np.mean([a1[r] for r in recs if r in a1]))
                vb0 = float(np.mean([b0[r] for r in recs if r in b0])); vb1 = float(np.mean([b1[r] for r in recs if r in b1]))
                rows_i.append(dict(source=x, family=fam, point=point, A_d=va1 - va0, B_d=vb1 - vb0, I=(vb1 - vb0) - (va1 - va0)))
        inter[point] = rows_i
    (OUT / 'FOUR_EVAL_V4.json').write_text(json.dumps(dict(runs=res, source_interaction=inter), indent=2), encoding='utf-8')
    print('done', len(res))


if __name__ == '__main__':
    main()
