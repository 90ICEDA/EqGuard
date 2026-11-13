"""Leave-one-control-family-out masks: train on 7 control families, hold 1 out for FPR.

For each control family f in the frozen fold:
  train_trust = (orig_trust OR train_ctl_cells_of_other_7_families) MINUS heldout_f
  heldout_f   = train-split control cells of family f (normal by construction)

Outputs (new only):
  trust_trans_v2_loco_<family>.npy     bool mask, train mask for that rotation
  loco_report.json                     per-fold stats + heldout family + counts
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
    ctl = np.char.startswith(view_family.astype(str), 'ctl')
    train_ctl = (split_id == 0) & ctl

    fams = sorted({v.split('__')[1] for v in split['train_views'] if v.split('__')[1].startswith('ctl')})
    assert len(fams) == 8, fams
    assert not np.any(y[train_ctl] == 1), 'control positive present; abort'

    report = dict(time='2026-10-31T19:05:00+08:00', families=fams, folds={})
    for f in fams:
        held = train_ctl & (view_family == f)
        other = train_ctl & (view_family != f)
        mask = (trust | other) & ~held
        assert not np.any(y[held] == 1), 'held-out control family contains a positive'
        assert not np.any(mask & held)
        np.save(OUT / f'trust_trans_v2_loco_{f}.npy', mask)
        m = split_id == 0
        report['folds'][f] = dict(
            heldout_family=f,
            heldout_nodes=int(held.sum()),
            train_nodes=int(m.sum()),
            train_trusted=int(mask[m].sum()),
            train_rate=round(float(mask[m].mean()), 4),
            heldout_trusted_excluded=int(trust[held].sum()),
            added_vs_original=int((mask[m] & ~trust[m]).sum()),
        )
    (OUT / 'loco_report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    for f, d in report['folds'].items():
        print(f, d)


if __name__ == '__main__':
    main()
