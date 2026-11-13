"""Choose all positives plus 300 stratified negatives per s15850 panel view."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
T4 = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_s15850_round22'
T8 = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k8_s15850_round25'
PANEL = json.loads((T8 / 'panel.json').read_text(encoding='utf-8'))['panel']
N_NEG = 300


def main():
    d = pd.read_csv(T4 / 'merged_s15850.csv')
    d = d[d.covered & d.status.eq('eligible') & d.view.isin(PANEL)]
    rng = np.random.default_rng(20261027)
    choices = []
    for vi, view in enumerate(PANEL):
        m = d[d.view == view]
        pos = m[m.label == 1]
        neg = m[m.label == 0]
        chosen = list(pos.global_node.to_numpy())
        # Preserve the negative driver x k composition as closely as possible.
        groups = list(neg.groupby(['driver_type', 'k'], dropna=False))
        total = len(neg)
        alloc = []
        for _, g in groups:
            n = int(round(N_NEG * len(g) / total)) if total else 0
            alloc.append(min(n, len(g)))
        # Fix rounding so the total is exactly N_NEG where possible.
        while sum(alloc) < min(N_NEG, total):
            for i, (_, g) in enumerate(groups):
                if alloc[i] < len(g) and sum(alloc) < min(N_NEG, total):
                    alloc[i] += 1
        while sum(alloc) > min(N_NEG, total):
            for i in range(len(alloc) - 1, -1, -1):
                if alloc[i] > 0 and sum(alloc) > min(N_NEG, total):
                    alloc[i] -= 1
        for (_, g), n in zip(groups, alloc):
            if n:
                chosen += list(rng.choice(g.global_node.to_numpy(), n, replace=False))
        for gid in chosen:
            lab = int(m.loc[m.global_node == gid, 'label'].iloc[0])
            choices.append(dict(global_node=int(gid), view=view, label=lab,
                                family=m.family.iloc[0]))
        print(view, 'pos', len(pos), 'neg_sample', len(chosen) - len(pos),
              'total', len(chosen))
    s = pd.DataFrame(choices).drop_duplicates('global_node')
    s.to_csv(T8 / 'sample_ids.csv', index=False, encoding='utf-8-sig')
    np.savez_compressed(T8 / 'sample_ids.npz', global_ids=s.global_node.to_numpy(),
                        label=s.label.to_numpy(), view=s.view.to_numpy())
    (T8 / 'sample_meta.json').write_text(json.dumps(dict(
        panel=PANEL, n_neg_per_view=N_NEG, rows=len(s),
        positives=int(s.label.sum()), negatives=int((s.label == 0).sum()),
        sampling='all positives + stratified negatives by driver_type x k',
        seed=20261027), ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(rows=len(s), positives=int(s.label.sum()),
                          negatives=int((s.label == 0).sum())), indent=2))


if __name__ == '__main__':
    main()
