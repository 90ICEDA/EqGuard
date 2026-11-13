"""Build a five-view k4 benchmark: one full view per circuit."""
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k4_bench_round28'
P = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
VIEWS = ROOT / 'generate_trans/folds/hosts_bt31/views.json'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    T.mkdir(parents=True, exist_ok=True)
    d = json.loads(VIEWS.read_text(encoding='utf-8'))
    picks = []
    for circuit, split in (('rs232', 'train'), ('s15850', 'train'), ('s35932', 'train'),
                           ('s38417', 'val'), ('s38584', 'test')):
        key = split + '_views'
        v = next(x for x in d[key] if x.startswith(circuit))
        picks.append((v, split))
    g = torch.load(P / 'trans_graph.pt', map_location='cpu', weights_only=False, mmap=True)
    selected = {v for v, _ in picks}
    ids = torch.tensor([i for i, f in enumerate(g.file_ids) if f in selected], dtype=torch.long)
    order = {v: i for i, (v, _) in enumerate(picks)}
    vi = torch.tensor([order[g.file_ids[int(i)]] for i in ids], dtype=torch.long)
    rev = torch.full((g.num_nodes,), -1, dtype=torch.long)
    rev[ids] = torch.arange(len(ids))
    e = g.edge_index
    keep = (rev[e[0]] >= 0) & (rev[e[1]] >= 0)
    edges = rev[e[:, keep]].numpy()
    x = g.x[ids].numpy()
    assert np.all(vi.numpy()[edges[0]] == vi.numpy()[edges[1]])
    np.savez_compressed(T / 'base_inputs.npz', global_ids=ids.numpy(), x=x,
                        edge_index=edges, view_index=vi.numpy())
    plan = dict(created='2026-10-27T18:00:00+08:00',
                scope='five circuits; one full view each; k4 benchmark',
                views=[], selection='first view of each circuit/split; no labels read',
                context='native_unrestricted_combinational_physical_Q_v1',
                cut_rule=dict(max_inputs=4, max_depth=4,
                              choice='complete structural frontier; <=4 leaves'),
                target_rule='one sample per graph cell; comb output; DFF D data cone',
                family_rule='view token between __ segments',
                split='benchmark', sat_timeout=3, sat_batch_nodes=32)
    for v, split in picks:
        src = ROOT / 'generate_trans/folds/hosts_bt31/trans' / (v + '.v')
        assert src.exists(), src
        plan['views'].append(dict(view=v, family=v.split('__')[1], split=split,
                                  source=str(src.relative_to(ROOT)),
                                  bytes=src.stat().st_size, source_sha=sha(src)))
    plan['plan_sha'] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    (T / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    for item in plan['views']:
        one = dict(plan)
        one.pop('plan_sha', None)
        one['views'] = [item]
        one['selection'] = 'single benchmark view; no labels read'
        one['plan_sha'] = hashlib.sha256(json.dumps(one, sort_keys=True).encode()).hexdigest()
        out = T / 'views' / item['view']
        out.mkdir(parents=True, exist_ok=True)
        (out / 'plan.json').write_text(json.dumps(one, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(views=[(v, split) for v, split in picks], nodes=len(ids),
                          edges=edges.shape[1], plan_sha=plan['plan_sha']), indent=2))


if __name__ == '__main__':
    main()
