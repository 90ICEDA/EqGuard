"""Freeze a four-view s15850 panel for the k=6 check (no labels read)."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_s15850_round22'
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k6_s15850_round26'
PANEL = [
    's15850t100__injalpha_d1_s42__ys_abc',
    's15850t100__injdelta_d1_s42__ys_abc',
    's15850t100__injepsilon_d1_s42__ys_abc',
    's15850t100__injgamma_d1_s42__ys_abc',
]


def main():
    T.mkdir(parents=True, exist_ok=True)
    src_plan = json.loads((SRC / 'plan.json').read_text(encoding='utf-8'))
    by_view = {x['view']: x for x in src_plan['views']}
    assert all(v in by_view for v in PANEL), set(PANEL) - set(by_view)
    z = np.load(SRC / 'base_inputs.npz')
    base_names = [x['view'] for x in src_plan['views']]
    vi_all = z['view_index']
    mask = np.array([base_names[int(v)] in PANEL for v in vi_all], bool)
    ids = z['global_ids'][mask]
    x = z['x'][mask]
    # s15850 base stores edge endpoints as local positions (unlike the rs232 base,
    # which stores global ids); subset with the old->new local position map.
    old_positions = np.flatnonzero(mask)
    pos = {int(p): i for i, p in enumerate(old_positions)}
    keep = np.array([int(a) in pos and int(b) in pos
                     for a, b in zip(z['edge_index'][0], z['edge_index'][1])], bool)
    e = z['edge_index'][:, keep]
    edges = np.array([[pos[int(a)], pos[int(b)]] for a, b in zip(e[0], e[1])], np.int64).T
    order = {v: i for i, v in enumerate(PANEL)}
    vi = np.array([order[base_names[int(v)]] for v in vi_all[mask]], np.int64)
    assert np.all(vi[edges[0]] == vi[edges[1]])
    np.savez_compressed(T / 'base_inputs.npz', global_ids=ids, x=x,
                        edge_index=edges, view_index=vi)
    plan = dict(created='2026-10-27T16:00:00+08:00',
                scope='4 s15850 ys_abc injection views: alpha/delta/epsilon/gamma; k6 full',
                views=[by_view[v] for v in PANEL],
                selection='first four inj views in round22 plan order; no labels read',
                split_scope='same host s15850; feature audit only; not training',
                context='native_unrestricted_combinational_physical_Q_v1',
                cut_rule=dict(max_inputs=6, max_depth=4,
                              choice='complete structural frontier; <=6 leaves'),
                target_rule='one sample per graph cell; comb output; DFF D data cone',
                family_rule='view token between __ segments',
                split='train', sat_timeout=3, sat_batch_nodes=32,
                no_labels_read_before_freeze=True)
    plan['plan_sha'] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    (T / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    for item in plan['views']:
        one = dict(plan)
        one.pop('plan_sha', None)
        one['views'] = [item]
        one['selection'] = 'single s15850 k6 panel view; no labels read'
        one['plan_sha'] = hashlib.sha256(json.dumps(one, sort_keys=True).encode()).hexdigest()
        d = T / 'views' / item['view']
        d.mkdir(parents=True, exist_ok=True)
        (d / 'plan.json').write_text(json.dumps(one, ensure_ascii=False, indent=2), encoding='utf-8')
    (T / 'panel.json').write_text(json.dumps(dict(panel=PANEL, nodes=len(ids),
                                                  edges=edges.shape[1], source='s15850 k4 base subset'),
                                             ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(views=len(PANEL), nodes=len(ids), edges=edges.shape[1],
                          plan_sha=plan['plan_sha']), indent=2))

if __name__ == '__main__':
    main()
