"""Build P2-B main-experiment masks on the corrected (v2) inputs.

Training mask : taint-derived trusted labels, INJECTION VIEWS ONLY (no control labels).
Eval mask     : taint-derived trusted labels, all views (controls keep only their original
                provenance labels, so control FPR is measured on the same subset as before).

Rows follow the round32 split input order; mapping to global ids comes from p2_mapping.
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
MAP = OUT.parent / 'label_expand_20261031' / 'p2_mapping'
FOLD = ROOT / 'generate_trans/folds/hosts_bt31'
P2 = ROOT / '_p0pilot/round32_20261029/inputs'


def main():
    vi = np.load(ROOT / '_p0pilot/round29_20261029/frozen/view_index_all.npy')
    taint = np.load(OUT.parent / 'label_expand_20261031/trust_trans_v2_taint.npy')
    names = json.loads((FOLD / 'views.json').read_text(encoding='utf-8'))
    order = names['train_views'] + names['val_views'] + names['test_views']
    fam = np.array([v.split('__')[1] for v in order])
    split = np.full(len(vi), -1, np.int8)
    for k, key in enumerate(('train_views', 'val_views', 'test_views')):
        for v in names[key]:
            split[vi == order.index(v)] = k
    ctl = np.array([('ctl' in f) for f in np.where(vi >= 0, fam[np.clip(vi, 0, len(order) - 1)], 'x')])
    ctl = np.concatenate([ctl, np.zeros(len(taint) - len(ctl), bool)])

    rep = {}
    for s, k in (('train', 0), ('val', 1), ('test', 2)):
        gid = np.load(MAP / f'x39row_to_global_{s}.npy')
        isv = np.load(MAP / f'x39row_is_virtual_{s}.npy')
        t = taint[gid]
        inj = ~ctl[gid]
        m = t & ~isv
        if s == 'train':
            m = m & inj
        np.save(OUT / f'new_mask_{s}.npy', m)
        a = np.load(P2 / f'trans_{s}' / 'trusted.npy')
        assert len(a) == len(m), (s, len(a), len(m))
        rep[s] = dict(rows=int(len(m)), old_trusted=int(a.sum()), new_trusted=int(m.sum()),
                      removed=int((a & ~m).sum()), added=int((m & ~a).sum()),
                      nodes_physical=int((~isv).sum()))
    (OUT / 'mask_report.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
