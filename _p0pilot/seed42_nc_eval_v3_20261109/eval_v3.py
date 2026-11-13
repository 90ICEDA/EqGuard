"""Evaluation v3: correct same-recall on test positives, explicit per-split trust/physical masks,
global row numbering for roles, restored test normal identity, and training-definition audit."""
import csv
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OLD = R / '_p0pilot/seed42_nc_ablation_20261109'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'
OUT = R / '_p0pilot/seed42_nc_eval_v3_20261109'
sys.path.insert(0, str(R / '_p0pilot/control_loader_po_20261105'))
sys.path.insert(0, str(R / '_p0pilot/control_signed_carrier_20261109_v3'))
import Signed_common as S  # noqa: E402

BOUND = json.loads((R / '_p0pilot/control_boundary_v3_20261104/input_contract.json').read_text(encoding='utf-8'))
LINEAGE = R / '_p0pilot/control_role_pattern_20261107/NODE_LINEAGE.csv'


def views_of(split):
    return {v['view']: v for v in BOUND['shared_inputs'][f'trans_{split}']['views']}


def roles_by_source():
    out = {}
    with LINEAGE.open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['key'].startswith('trans') and r['role'] in ('trigger', 'payload', 'output_hijack'):
                out.setdefault(r['source'], {})[r['node_name']] = r['role']
    return out


def view_metrics(s, y, t, phys, views, names, roles):
    aps, t1, t5 = [], [], []
    role_counts, role_hits = {}, {}
    role_unmapped = {}
    for v, lay in views.items():
        lo = lay['start']; hi = lo + (lay['old_stop'] - lay['old_start'])
        yy, tt, pp, ss = y[lo:hi], t[lo:hi], phys[lo:hi], s[lo:hi]
        m = tt & pp
        if m.sum() >= 2 and len(np.unique(yy[m])) > 1:
            aps.append(average_precision_score(yy[m], ss[m]))
        idx_local = np.arange(len(ss))[m]
        if len(idx_local) >= 2:
            order = np.lexsort((idx_local, -ss[m]))
            idx_local = idx_local[order]
            pos = (yy[m] == 1)[order]
            for frac, acc in ((1, t1), (5, t5)):
                k = max(1, int(len(idx_local) * frac / 100))
                acc.append(float(pos[:k].sum() / max(1, pos.sum())))
            # role hits at 1% view budget, GLOBAL row numbers
            k = max(1, int(len(idx_local) * 1 / 100))
            hit_rows = set((lo + idx_local[:k]).tolist())
            for src, mp in roles.items():
                if not v.startswith(src + '__'):
                    continue
                vr = S.view_rows(views, names, v)
                for node, role in mp.items():
                    row = vr.get(node)
                    if row is None:
                        role_unmapped[(src, role)] = role_unmapped.get((src, role), 0) + 1
                        continue
                    if not (lo <= row < hi) or not (y[row] == 1 and t[row] and phys[row]):
                        continue
                    key = (src, role)
                    role_counts[key] = role_counts.get(key, 0) + 1
                    if row in hit_rows:
                        role_hits[key] = role_hits.get(key, 0) + 1
    return dict(ap_view=float(np.mean(aps)) if aps else None, views_ap=len(aps),
                top1=float(np.mean(t1)) if t1 else None, top5=float(np.mean(t5)) if t5 else None,
                roles={f'{s}|{r}': dict(mapped=role_counts[(s, r)], hits=role_hits.get((s, r), 0),
                                         recall=role_hits.get((s, r), 0) / role_counts[(s, r)])
                       for (s, r) in role_counts},
                role_unmapped={f'{s}|{r}': n for (s, r), n in role_unmapped.items()})


def recall_curves(mv, yv, tv, pv, mt, yt, tt, pt):
    p = tv & pv & (yv == 1); n = tv & pv & (yv == 0)
    tp = tt & pt & (yt == 1); tn = tt & pt & (yt == 0)
    A, B = {}, {}
    for target in (0.8, 0.9, 0.95):
        k = str(target)
        need_v = int(np.ceil(target * p.sum()))
        if need_v <= 0 or need_v > p.sum():
            A[k] = None
        else:
            thr = float(np.sort(mv[p])[::-1][need_v - 1])
            A[k] = dict(threshold=thr, val_recall=float((mv[p] >= thr).sum() / p.sum()),
                        val_fpr=float((mv[n] >= thr).sum() / max(1, n.sum())),
                        test_recall=float((mt[tp] >= thr).sum() / max(1, tp.sum())),
                        test_fpr=float((mt[tn] >= thr).sum() / max(1, tn.sum())))
        need_t = int(np.ceil(target * tp.sum()))       # test-positive denominator
        if need_t <= 0 or need_t > tp.sum():
            B[k] = None
        else:
            thr2 = float(np.sort(mt[tp])[::-1][need_t - 1])
            B[k] = dict(threshold=thr2, test_positives=int(tp.sum()), need=need_t,
                        test_recall=float((mt[tp] >= thr2).sum() / tp.sum()),
                        test_fpr=float((mt[tn] >= thr2).sum() / max(1, tn.sum())))
    return dict(A_val_transfer=A, B_test_diagnostic=B,
                positives=dict(val=int(p.sum()), test=int(tp.sum())))


def normal_metrics(s, y, t, phys, views, thr):
    alarm, na, conflict = [], 0, 0
    tnodes = tfp = 0
    for v, lay in views.items():
        src = v.split('__ys_')[0]
        if 'ctl' not in src and '__inj' not in src:
            na += 1; continue
        lo = lay['start']; hi = lo + (lay['old_stop'] - lay['old_start'])
        tt = t[lo:hi] & phys[lo:hi]; yy = y[lo:hi]; ss = s[lo:hi]
        if '__inj' in src:
            continue
        if not tt.any():
            na += 1; continue
        if (yy[tt] == 1).any():
            conflict += 1; continue
        alarm.append(float(ss[tt].max() >= thr))
        neg = tt & (yy == 0)
        tnodes += int(neg.sum()); tfp += int((ss[neg] >= thr).sum())
    return dict(identity='manufacture_source(ctl)', normal_views=len(alarm), na_views=na,
                conflicts=conflict, alarm_fpr=float(np.mean(alarm)) if alarm else None,
                trusted_normal_nodes=tnodes,
                trusted_normal_fpr=float(tfp / tnodes) if tnodes else None)


def cone_stats(s, split, trust, phys, thr):
    path = OLD / 'CONE_CACHE_TEST.csv' if split == 'test' else PREP / 'CONE_CACHE_V2.csv'
    out = {}
    for kind in ('D', 'PO'):
        pos = neg = unknown = empty = single = inelig = 0
        lab, sc = [], []
        with path.open(encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r['split'] != split or r['kind'] != kind:
                    continue
                mem = [int(x) for x in r['phys_rows'].split('|') if x]
                if not mem:
                    empty += 1; continue
                if len(mem) == 1:
                    single += 1
                mem = [x for x in mem if bool(trust[x]) and bool(phys[x])]
                if int(r['label']) < 0:
                    unknown += 1; continue
                if len(mem) < 2:
                    inelig += 1; continue
                if int(r['label']) == 1:
                    pos += 1
                else:
                    neg += 1
                lab.append(int(r['label'])); sc.append(float(max(s[x] for x in mem)))
        lab = np.array(lab); sc = np.array(sc)
        ap = float(average_precision_score(lab, sc)) if len(np.unique(lab)) > 1 else None
        fpr = float((sc[lab == 0] >= thr).sum() / max(1, (lab == 0).sum())) if thr is not None and (lab == 0).any() else None
        out[kind] = dict(pos=pos, neg=neg, unknown=unknown, empty=empty, singleton=single,
                         ineligible_lt2=inelig, ap=ap, fpr_at_thr=fpr)
    return out


def hand_check():
    """Hand-built counterexample: val and test have different positive counts."""
    val_scores = np.array([5., 4., 3., 2., 1.]); test_scores = np.array([10., 9., 8., 7., 6., 5., 4., 3., 2., 1.])
    target = 0.8
    need_v = int(np.ceil(target * len(val_scores))); need_t = int(np.ceil(target * len(test_scores)))
    thr_v = float(np.sort(val_scores)[::-1][need_v - 1]); thr_t = float(np.sort(test_scores)[::-1][need_t - 1])
    wrong = float((test_scores >= thr_v).sum() / len(test_scores))
    right = float((test_scores >= thr_t).sum() / len(test_scores))
    assert need_v == 4 and need_t == 8 and thr_v == 2.0 and thr_t == 3.0
    assert abs(right - 0.8) < 1e-9 and wrong != 0.8
    return dict(val_pos=5, test_pos=10, need_val=need_v, need_test=need_t,
                thr_val=thr_v, thr_test=thr_t, recall_using_val_need_on_test=wrong,
                recall_using_test_need=right)


def train_def_check():
    from supervision_loader import FiveGroupLoader
    loader = FiveGroupLoader()
    trust = np.asarray(loader.arrays('trans', 'train')['trusted'])
    phys = np.asarray(loader.arrays('trans', 'train')['physical'])
    pos = neg = members = 0
    with (PREP / 'CONE_CACHE_V2.csv').open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['split'] != 'train' or r['kind'] != 'D' or int(r['label']) < 0 or int(r['n_phys']) < 2:
                continue
            mem = [int(x) for x in r['phys_rows'].split('|') if x]
            mem = [x for x in mem if bool(trust[x]) and bool(phys[x])]
            if len(mem) < 1:
                continue
            if int(r['label']) == 1:
                pos += 1
            else:
                neg += 1
            members += len(mem)
    out = dict(cones=pos + neg, pos=pos, neg=neg, trusted_physical_members=members,
               expected=dict(cones=11834, pos=891, neg=10943, members=202206))
    out['passed'] = (out['cones'] == 11834 and pos == 891 and neg == 10943 and members == 202206)
    (OUT / 'TRAIN_DEF_CHECK.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    return out


def main():
    roles = roles_by_source()
    _, _, names, _ = S.load_snapshot('val')
    from supervision_loader import FiveGroupLoader
    loader = FiveGroupLoader()
    out = {}
    for seed, tag in ((42, ''), (1, '_s1'), (2, '_s2')):
        for arm in ('N', 'NC'):
            z = np.load(OLD / f'{arm}{tag}_scores.npz')
            for point in ('best', 'last'):
                yv, tv = z['y_val'], z['trust_val']; yt, tt = z['y_test'], z['trust_test']
                mv, mt = z[f'val_{point}'], z[f'test_{point}']
                assert len(mv) == len(yv) == len(tv) and len(mt) == len(yt) == len(tt)
                pv = np.asarray(loader.arrays('trans', 'val')['physical'])
                pt = np.asarray(loader.arrays('trans', 'test')['physical'])
                assert len(pv) == len(yv) and len(pt) == len(yt)
                vv = view_metrics(mv, yv, tv, pv, views_of('val'), names, roles)
                tw = view_metrics(mt, yt, tt, pt, views_of('test'), names, roles)
                rc = recall_curves(mv, yv, tv, pv, mt, yt, tt, pt)
                thr95 = rc['A_val_transfer']['0.95']['threshold'] if rc['A_val_transfer']['0.95'] else None
                nv = normal_metrics(mv, yv, tv, pv, views_of('val'), thr95) if thr95 is not None else None
                nt = normal_metrics(mt, yt, tt, pt, views_of('test'), thr95) if thr95 is not None else None
                cv = cone_stats(mv, 'val', tv, pv, thr95) if thr95 is not None else None
                ct = cone_stats(mt, 'test', tt, pt, thr95) if thr95 is not None else None
                out[f'{arm}_s{seed}_{point}'] = dict(seed=seed, arm=arm, point=point, val=vv, test=tw,
                                                     equal_recall=rc, normal_val=nv, normal_test=nt,
                                                     cones_val=cv, cones_test=ct)
    out['_meta'] = dict(hand_check=hand_check(), train_def=train_def_check())
    (OUT / 'EVAL_V3_ALL.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    print('done', len(out))


if __name__ == '__main__':
    main()
