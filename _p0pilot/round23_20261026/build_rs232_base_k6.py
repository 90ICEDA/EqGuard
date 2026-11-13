"""Freeze all rs232 training views and build their small base for k=6 extraction."""
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k6_rs232_round23'
P = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
VIEWS = ROOT / 'generate_trans/folds/hosts_bt31/views.json'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    T.mkdir(parents=True, exist_ok=True)
    views_json = json.loads(VIEWS.read_text(encoding='utf-8'))
    names = [x for x in views_json['train_views'] if x.startswith('rs232')]
    g = torch.load(P / 'trans_graph.pt', map_location='cpu', weights_only=False, mmap=True)
    selected = set(names)
    ids = torch.tensor([i for i, f in enumerate(g.file_ids) if f in selected], dtype=torch.long)
    view_order = {v: i for i, v in enumerate(names)}
    vi = torch.tensor([view_order[g.file_ids[int(i)]] for i in ids], dtype=torch.long)
    rev = torch.full((g.num_nodes,), -1, dtype=torch.long)
    rev[ids] = torch.arange(len(ids))
    ei = g.edge_index
    keep = (rev[ei[0]] >= 0) & (rev[ei[1]] >= 0)
    edges = rev[ei[:, keep]].numpy()
    x = g.x[ids].numpy()
    assert np.all(vi.numpy()[edges[0]] == vi.numpy()[edges[1]])
    np.savez_compressed(T / 'base_inputs.npz', global_ids=ids.numpy(),
                        x=x, edge_index=edges, view_index=vi.numpy())
    plan = dict(created='2026-10-26T21:45:00+08:00',
                scope='all 113 rs232 training views; ys_abc/id/aig/nand/opt/rt',
                views=[], selection='all rs232 train views; no labels read',
                context='native_unrestricted_combinational_physical_Q_v1',
                cut_rule=dict(max_inputs=6, max_depth=4,
                              choice='complete structural frontier; <=6 leaves'),
                target_rule='one sample per graph cell; comb output; DFF D data cone',
                family_rule='view token between __ segments',
                split='train', sat_timeout=3, sat_batch_nodes=32)
    for v in names:
        src = ROOT / 'generate_trans/folds/hosts_bt31/trans' / (v + '.v')
        assert src.exists(), src
        fam = v.split('__')[1] if len(v.split('__')) > 1 else 'unknown'
        plan['views'].append(dict(view=v, family=fam, split='train',
                                  source=str(src.relative_to(ROOT)),
                                  bytes=src.stat().st_size, source_sha=sha(src)))
    plan['plan_sha'] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    (T / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(views=len(names), nodes=len(ids), edges=edges.shape[1],
                          plan_sha=plan['plan_sha']), indent=2))


if __name__ == '__main__':
    main()
