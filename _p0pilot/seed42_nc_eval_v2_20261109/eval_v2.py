"""Evaluation v2: trusted+physical-only cone aggregation, separated A/B recall summaries,
per-view role Top-k, identity-based normal views, contributor analysis.

Offline only: reads saved margins and caches; no model, no training, no tuning.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OLD = R / '_p0pilot/seed42_nc_ablation_20261109'
OUT = R / '_p0pilot/seed42_nc_eval_v2_20261109'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'
sys.path.insert(0, str(R / '_p0pilot/control_signed_carrier_20261109_v3'))
import Signed_common as S  # noqa: E402

BOUND = json.loads((R / '_p0pilot/control_boundary_v3_20261104/input_contract.json').read_text(encoding='utf-8'))
LINEAGE = R / '_p0pilot/control_role_pattern_20261107/NODE_LINEAGE.csv'


def views_of(split):
    return {v['view']: v for v in BOUND['shared_inputs'][f'trans_{split}']['views']}


def role_map():
    out = {}
    with LINEAGE.open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['key'].startswith('trans') and r['role'] in ('trigger', 'payload', 'output_hijack'):
                out[(r['source'], r['node_name'])] = r['role']
    return out


def positive_sources(roles):
    return {src for (src, _), _ in roles.items()}


def all_sources():
    out = set()
    with LINEAGE.open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if r['key'].startswith('trans'):
                out.add(r['source'])
    return out


def view_metrics(s, y, t, views, split, roles, names):
    aps, t1, t5 = [], [], []
    role_counts = {}
    role_hit = {}
    for v, lay in views.items():
        lo = lay['start']; hi = lo + (lay['old_stop'] - lay['old_start'])
        yy, tt, ss = y[lo:hi], t[lo:hi], s[lo:hi]
        m = tt
        if m.sum() >= 2 and len(np.unique(yy[m])) > 1:
            aps.append(average_precision_score(yy[m], ss[m]))
        idx = np.arange(len(ss))[m]
        if len(idx) >= 2:
            order = np.lexsort((idx, -ss[m]))
            idx = idx[order]
            pos = (yy[m] == 1)[order]
            for frac, acc in ((1, t1), (5, t5)):
                k = max(1, int(len(idx) * frac / 100))
                acc.append(float(pos[:k].sum() / max(1, pos.sum())))
        # role recall: per-view budget over trusted physical nodes
        vr = S.view_rows(views, names, v)
        for (src, node), role in roles.items():
            if not v.startswith(src + '__'):
                continue
            row = vr.get(node)
            if row is None or not (lo <= row < hi):
                continue
            if not (y[row] == 1 and t[row]):
                continue
            role_counts[role] = role_counts.get(role, 0) + 1
            if len(idx) and row in set(idx[:max(1, int(len(idx) * 1 / 100))].tolist()):
                role_hit[role] = role_hit.get(role, 0) + 1
    return dict(ap_view=float(np.mean(aps)) if aps else None, views_ap=len(aps),
                top1=float(np.mean(t1)) if t1 else None, top5=float(np.mean(t5)) if t5 else None,
                support_views=len(views),
                roles={r: dict(mapped=role_counts[r], hits=role_hit.get(r, 0),
                               recall=role_hit.get(r, 0) / role_counts[r]) for r in role_counts})


def equal_recall(mv, yv, tv, mt, yt, tt):
    p = tv & (yv == 1); n = tv & (yv == 0)
    tp = tt & (yt == 1); tn = tt & (yt == 0)
    A, B = {}, {}
    for target in (0.8, 0.9, 0.95):
        key = str(target)
        need = int(np.ceil(target * p.sum()))
        if need <= 0 or need > p.sum():
            A[key] = B[key] = None; continue
        thr = float(np.sort(mv[p])[::-1][need - 1])
        A[key] = dict(threshold=thr, val_recall=float((mv[p] >= thr).sum() / p.sum()),
                      val_fpr=float((mv[n] >= thr).sum() / max(1, n.sum())),
                      test_recall=float((mt[tp] >= thr).sum() / max(1, tp.sum())),
                      test_fpr=float((mt[tn] >= thr).sum() / max(1, tn.sum())))
        thr2 = float(np.sort(mt[tp])[::-1][need - 1])
        B[key] = dict(threshold=thr2, test_recall=float((mt[tp] >= thr2).sum() / tp.sum()),
                      test_fpr=float((mt[tn] >= thr2).sum() / max(1, tn.sum())))
    return dict(A_val_transfer=A, B_test_diagnostic=B)


def normal_metrics(s, y, t, views, roles, thr, known):
    alarm, na, tnodes, tfp = [], 0, 0, 0
    for v, lay in views.items():
        matching = [src for src in known if v.startswith(src + '__')]
        if not matching:
            na += 1
            continue
        src = max(matching, key=len)
        if '__inj' in src:
            continue
        if 'ctl' not in src:
            na += 1
            continue
        lo = lay['start']; hi = lo + (lay['old_stop'] - lay['old_start'])
        tt = t[lo:hi]; yy = y[lo:hi]; ss = s[lo:hi]
        if not tt.any():
            na += 1; continue
        alarm.append(float(ss[tt].max() >= thr))
        neg = tt & (yy == 0)
        tnodes += int(neg.sum()); tfp += int((ss[neg] >= thr).sum())
    return dict(normal_views=len(alarm), na_views=na,
                alarm_fpr=float(np.mean(alarm)) if alarm else None,
                trusted_normal_nodes=tnodes,
                trusted_normal_fpr=float(tfp / tnodes) if tnodes else None)


def cones_metrics(s, split, thr):
    path = OLD / 'CONE_CACHE_TEST.csv' if split == 'test' else PREP / 'CONE_CACHE_V2.csv'
    out = {}
    for kind in ('D', 'PO'):
        pos = neg = unk = 0; lab = []; sc = []
        with path.open(encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r['split'] != split or r['kind'] != kind:
                    continue
                mem = [int(x) for x in r['phys_rows'].split('|') if x]
                mem = [x for x in mem if bool(T_TRUST[x])]
                if int(r['label']) < 0 or len(mem) < 2:
                    unk += 1; continue
                if int(r['label']) == 1:
                    pos += 1
                else:
                    neg += 1
                lab.append(int(r['label'])); sc.append(float(max(s[x] for x in mem)))
        lab = np.array(lab); sc = np.array(sc)
        ap = float(average_precision_score(lab, sc)) if len(np.unique(lab)) > 1 else None
        fpr = float((sc[lab == 0] >= thr).sum() / max(1, (lab == 0).sum())) if thr is not None and (lab == 0).any() else None
        out[kind] = dict(pos=pos, neg=neg, unknown=unk, ap=ap, fpr_at_thr=fpr)
    return out


def main():
    global T_TRUST
    roles = role_map()
    _, _, names, _ = S.load_snapshot('val')
    out = {}
    for seed, tag in ((42, ''), (1, '_s1'), (2, '_s2')):
        for arm in ('N', 'NC'):
            z = np.load(OLD / f'{arm}{tag}_scores.npz')
            for point in ('best', 'last'):
                yv, tv, yt, tt = z['y_val'], z['trust_val'], z['y_test'], z['trust_test']
                mv, mt = z[f'val_{point}'], z[f'test_{point}']
                T_TRUST = tt
                vv = view_metrics(mv, yv, tv, views_of('val'), 'val', roles, names)
                tvw = view_metrics(mt, yt, tt, views_of('test'), 'test', roles, names)
                er = equal_recall(mv, yv, tv, mt, yt, tt)
                thr95 = er['A_val_transfer']['0.95']['threshold'] if er['A_val_transfer']['0.95'] else None
                T_TRUST = tv
                nv = normal_metrics(mv, yv, tv, views_of('val'), roles, thr95, all_sources()) if thr95 is not None else None
                T_TRUST = tt
                nt = normal_metrics(mt, yt, tt, views_of('test'), roles, thr95, all_sources()) if thr95 is not None else None
                cv = cones_metrics(mv, 'val', thr95) if thr95 is not None else None
                ct = cones_metrics(mt, 'test', thr95) if thr95 is not None else None
                out[f'{arm}_s{seed}_{point}'] = dict(seed=seed, arm=arm, point=point,
                                                     val=vv, test=tvw, equal_recall=er,
                                                     normal_val=nv, normal_test=nt,
                                                     cones_val=cv, cones_test=ct)
    (OUT / 'EVAL_V2_ALL.json').write_text(json.dumps(out, indent=2), encoding='utf-8')
    print('done', len(out))


if __name__ == '__main__':
    main()
