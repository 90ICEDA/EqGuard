"""Fast, additive trusted-label expansion: certify TRAIN-split control views as normal.

Rationale (short):
  - A4 control families (ctldead / ctlequiv) are functionally equivalent to the clean
    base (conversion-time CEC PASS, see 10.15/01_数据与标签/A4_对照样本/说明.md), and
    they contain zero labelled trojan positives (verified below).
  - Therefore every physical cell in a control view is a normal (non-trojan) cell.
  - We only use TRAIN-split control views, so val/test control views stay untouched
    for the normal-control FPR diagnostic.

Outputs (all new; the original trust_trans.npy is never modified):
  trust_trans_v2_trainctl.npy   bool mask, same length/order as trust_trans.npy
  expansion_report.json         counts + rule + invariants
  per_view.csv                  per-view nodes / old trusted / newly trusted
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA = ROOT / 'generate_trans/folds/hosts_bt31/data/for_train'
FROZEN = ROOT / '_p0pilot/round29_20261029/frozen'


def main():
    vi = np.load(FROZEN / 'view_index_all.npy')
    trust = np.load(DATA / 'trust_trans.npy')
    split = json.loads((ROOT / 'generate_trans/folds/hosts_bt31/views.json').read_text(encoding='utf-8'))
    order = split['train_views'] + split['val_views'] + split['test_views']
    idx = {v: i for i, v in enumerate(order)}
    family = np.array([v.split('__')[1] for v in order])

    lab = json.loads((DATA / 'label_transport.json').read_text(encoding='utf-8'))['trans_labels_from_orig']
    keys = np.fromiter((int(k) for k in lab), np.int64, len(lab))
    vals = np.fromiter(lab.values(), np.int8, len(lab))
    y = np.full(len(vi), -1, np.int8)
    y[keys] = vals

    split_id = np.full(len(vi), -1, np.int8)
    for k in range(3):
        for v in (split['train_views'], split['val_views'], split['test_views'])[k]:
            split_id[vi == idx[v]] = k

    view_family = np.where(vi >= 0, family[np.clip(vi, 0, len(order) - 1)], '')

    # 1) invariant: control views must carry no labelled positive
    ctl = np.char.startswith(view_family.astype(str), 'ctl')
    assert not np.any(y[ctl] == 1), 'control view contains a labelled positive; abort'

    # 2) train-split control cells only
    new_mask = (split_id == 0) & ctl
    added = new_mask & ~trust
    assert not np.any(y[added] == 1)

    trust_v2 = trust | added
    np.save(OUT / 'trust_trans_v2_trainctl.npy', trust_v2)

    # 3) report
    stats = {}
    for k, name in ((0, 'train'), (1, 'val'), (2, 'test')):
        m = split_id == k
        stats[name] = dict(
            nodes=int(m.sum()),
            trusted_before=int(trust[m].sum()), rate_before=round(float(trust[m].mean()), 4),
            trusted_after=int(trust_v2[m].sum()), rate_after=round(float(trust_v2[m].mean()), 4),
            positives=int((m & (y == 1)).sum()),
        )
    ctl_train_views = sorted({v for v in split['train_views'] if v.split('__')[1].startswith('ctl')})
    rep = dict(
        time='2026-10-31T19:00:00+08:00',
        rule='train-split control views (family prefix ctl) certified as trusted normal; '
             'controls are CEC-equivalent to clean base and carry 0 labelled positives',
        original_trust=dict(path=str((DATA / 'trust_trans.npy').relative_to(ROOT)), sha=None),
        new_trust=dict(path=str((OUT / 'trust_trans_v2_trainctl.npy').relative_to(ROOT))),
        added=int(added.sum()),
        control_train_views=len(ctl_train_views),
        control_train_nodes=int(new_mask.sum()),
        invariants=dict(no_positive_in_control_views=True, no_positive_added=True,
                        val_test_untouched=True, original_file_untouched=True),
        split_stats=stats,
        caveat='train-split controls are now training negatives; do not report FPR on '
               'train-split controls afterwards. val/test controls remain diagnostic.',
    )
    (OUT / 'expansion_report.json').write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding='utf-8')

    rows = ['view,nodes,trusted_before,newly_trusted,positives']
    for v in ctl_train_views:
        m = vi == idx[v]
        rows.append(f'{v},{int(m.sum())},{int(trust[m].sum())},{int(added[m].sum())},{int((m & (y == 1)).sum())}')
    (OUT / 'per_view.csv').write_text('\n'.join(rows) + '\n', encoding='utf-8')

    print(json.dumps(rep['split_stats'], ensure_ascii=False, indent=1))
    print('added', int(added.sum()), 'control train views', len(ctl_train_views))


if __name__ == '__main__':
    main()
