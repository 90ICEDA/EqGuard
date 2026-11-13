"""Equal-recall FPR and role recall from saved margins (no model, no training)."""
import json
import sys
from pathlib import Path

import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/seed42_nc_ablation_20261109'
sys.path.insert(0, str(R / '_p0pilot/control_signed_carrier_20261109_v3'))
import Signed_common as S


def eq_recall(val_s, val_y, val_t, test_s, test_y, test_t):
    p = val_t & (val_y == 1); n = val_t & (val_y == 0)
    tp = test_t & (test_y == 1); tn = test_t & (test_y == 0)
    out = {}
    for target in (0.80, 0.90, 0.95):
        need = int(np.ceil(target * p.sum()))
        if need <= 0 or need > p.sum():
            out[f'recall{int(target*100)}'] = None; continue
        thr = np.sort(val_s[p])[::-1][need - 1]
        rec = float((test_s[tp] >= thr).sum() / max(1, tp.sum()))
        fpr = float((test_s[tn] >= thr).sum() / max(1, tn.sum()))
        vrec = float((val_s[p] >= thr).sum() / max(1, p.sum()))
        vfpr = float((val_s[n] >= thr).sum() / max(1, n.sum()))
        out[f'recall{int(target*100)}'] = dict(threshold=float(thr), val_recall=vrec, val_fpr=vfpr,
                                               test_recall=rec, test_fpr=fpr)
    return out


def main():
    lineage = S.rows(R / '_p0pilot/control_role_pattern_20261107/NODE_LINEAGE.csv')
    roles = {}
    for r in lineage:
        if r['key'].startswith('trans') and r['role'] in ('trigger', 'payload', 'output_hijack'):
            roles[(r['source'], r['node_name'])] = r['role']
    _, _, names, views = S.load_snapshot('val')
    res = {}
    for arm in ('N', 'NC'):
        z = np.load(OUT / f'{arm}_scores.npz')
        res[arm] = dict(
            equal_recall=eq_recall(z['val_best'], z['y_val'], z['trust_val'],
                                   z['test_best'], z['y_test'], z['trust_test']),
            equal_recall_last=eq_recall(z['val_last'], z['y_val'], z['trust_val'],
                                        z['test_last'], z['y_test'], z['trust_test']))
        # role recall at top-1% on val (roles from lineage, mapped through val views)
        y, t = z['y_val'], z['trust_val']; s = z['val_best']
        pos = (y == 1) & t
        k = max(1, int(len(y) * 0.01)); top = set(np.argsort(-s)[:k].tolist())
        by_role = {}
        for v, lay in views.items():
            vr = S.view_rows(views, names, v)
            for (src, node), role in roles.items():
                if not v.startswith(src + '__'):
                    continue
                row = vr.get(node)
                if row is None or not pos[row]:
                    continue
                by_role.setdefault(role, []).append(row)
        res[arm]['role_recall_top1'] = {r: float(len([x for x in rows if x in top]) / len(rows))
                                        for r, rows in by_role.items() if rows}
        res[arm]['role_positive_counts'] = {r: len(rows) for r, rows in by_role.items() if rows}
    (OUT / 'METRICS_EXTRA.json').write_text(json.dumps(res, indent=2), encoding='utf-8')
    print(json.dumps(res, indent=2))


if __name__ == '__main__':
    main()
