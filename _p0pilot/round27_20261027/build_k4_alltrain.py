"""Freeze k4 plans for remaining s15850/s35932 all-cell train views (no labels read)."""
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k4_alltrain_round27'
P = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
VIEWS = ROOT / 'generate_trans/folds/hosts_bt31/views.json'
EXCLUDE = set(json.loads((ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_s15850_round22/plan.json').read_text(
    encoding='utf-8'))['views'][i]['view'] for i in range(10))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    if (T/'plan.json').exists() or (T/'base_inputs.npz').exists():
        raise RuntimeError('Frozen round27 inputs already exist; use run_all_k4_alltrain.py to resume')
    T.mkdir(parents=True, exist_ok=True)
    d = json.loads(VIEWS.read_text(encoding='utf-8'))
    names = [v for v in d['train_views']
             if (v.startswith('s15850') or v.startswith('s35932')) and v not in EXCLUDE]
    assert len(names) == 136, len(names)
    g = torch.load(P / 'trans_graph.pt', map_location='cpu', weights_only=False, mmap=True)
    selected = set(names)
    ids = torch.tensor([i for i, f in enumerate(g.file_ids) if f in selected], dtype=torch.long)
    view_order = {v: i for i, v in enumerate(names)}
    vi = torch.tensor([view_order[g.file_ids[int(i)]] for i in ids], dtype=torch.long)
    rev = torch.full((g.num_nodes,), -1, dtype=torch.long)
    rev[ids] = torch.arange(len(ids))
    e = g.edge_index
    keep = (rev[e[0]] >= 0) & (rev[e[1]] >= 0)
    edges = rev[e[:, keep]].numpy()
    x = g.x[ids].numpy()
    assert np.all(vi.numpy()[edges[0]] == vi.numpy()[edges[1]])
    np.savez_compressed(T / 'base_inputs.npz', global_ids=ids.numpy(), x=x,
                        edge_index=edges, view_index=vi.numpy())
    plan = dict(created='2026-10-27T17:30:00+08:00',
                scope='remaining s15850/s35932 train views; k4 all graph cells',
                views=[], selection='all remaining train views for s15850/s35932; no labels read',
                context='native_unrestricted_combinational_physical_Q_v1',
                cut_rule=dict(max_inputs=4, max_depth=4,
                              choice='complete structural frontier; <=4 leaves'),
                target_rule='one sample per graph cell; comb output; DFF D data cone',
                family_rule='view token between __ segments',
                split='train', sat_timeout=3, sat_batch_nodes=32,
                sample_rule='all graph cells; extraction is label blind')
    for v in names:
        src = ROOT / 'generate_trans/folds/hosts_bt31/trans' / (v + '.v')
        assert src.exists(), src
        plan['views'].append(dict(view=v, family=v.split('__')[1], split='train',
                                  source=str(src.relative_to(ROOT)),
                                  bytes=src.stat().st_size, source_sha=sha(src)))
    plan['plan_sha'] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    (T / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    for item in plan['views']:
        one = dict(plan)
        one.pop('plan_sha', None)
        one['views'] = [item]
        one['selection'] = 'single remaining k4 panel view; no labels read'
        one['plan_sha'] = hashlib.sha256(json.dumps(one, sort_keys=True).encode()).hexdigest()
        out = T / 'views' / item['view']
        out.mkdir(parents=True, exist_ok=True)
        (out / 'plan.json').write_text(json.dumps(one, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(views=len(names), nodes=len(ids), edges=edges.shape[1],
                          plan_sha=plan['plan_sha']), indent=2))


if __name__ == '__main__':
    main()
