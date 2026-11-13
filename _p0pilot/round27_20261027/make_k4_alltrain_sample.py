"""Pick all positives + 200 random negatives for each remaining train view."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k4_alltrain_round27'
P = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
PLAN = json.loads((T / 'plan.json').read_text(encoding='utf-8'))
N_NEG = 200


def main():
    parser=argparse.ArgumentParser(description='Optional label-aware TRAIN analysis only; never used for SAT candidate selection')
    parser.add_argument('--label-aware-analysis',action='store_true')
    if not parser.parse_args().label_aware_analysis:
        print('Disabled by default: full-cell SAT extraction does not use label sampling')
        return
    assert all(v['split']=='train' for v in PLAN['views'])
    if any((T/n).exists() for n in ('sample_ids.csv','sample_ids.npz','sample_meta.json')):
        raise RuntimeError('Existing analysis artifacts retained; refusing overwrite')
    g = torch.load(P / 'trans_graph.pt', map_location='cpu', weights_only=False, mmap=True)
    by_view = {}
    for i, f in enumerate(g.file_ids):
        by_view.setdefault(f, []).append(i)
    rng = np.random.default_rng(20261027)
    rows = []
    for item in PLAN['views']:
        v = item['view']
        ids = np.asarray(by_view[v], dtype=np.int64)
        y = g.y[torch.tensor(ids)].numpy().astype(int)
        pos = ids[y == 1]
        neg = ids[y == 0]
        take = min(N_NEG, len(neg))
        chosen_neg = rng.choice(neg, take, replace=False)
        for gid, lab in [(int(z), 1) for z in pos] + [(int(z), 0) for z in chosen_neg]:
            rows.append(dict(global_node=gid, view=v, family=item['family'], label=lab))
        print(v, 'pos', len(pos), 'neg_sample', len(chosen_neg))
    d = pd.DataFrame(rows)
    d.to_csv(T / 'sample_ids.csv', index=False, encoding='utf-8-sig')
    np.savez_compressed(T / 'sample_ids.npz', global_ids=d.global_node.to_numpy(),
                        label=d.label.to_numpy(), view=d.view.to_numpy())
    (T / 'sample_meta.json').write_text(json.dumps(dict(
        views=len(PLAN['views']), n_neg_per_view=N_NEG, rows=len(d),
        positives=int(d.label.sum()), negatives=int((d.label == 0).sum()),
        sampling='all positives + random negatives per view; no labels used for feature design',
        seed=20261027), ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(views=len(PLAN['views']), rows=len(d), positives=int(d.label.sum()),
                          negatives=int((d.label == 0).sum())), indent=2))


if __name__ == '__main__':
    main()
