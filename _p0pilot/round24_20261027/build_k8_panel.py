"""Freeze a four-view rs232 panel for the k=8 check (no labels read)."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k6_rs232_round23'
T = ROOT / '10.15/06_统一评测协议/N4_三向泛化/tables/sat_k8_rs232_round24'
PANEL = [
    'rs232t1000__injalpha_d1_s42__ys_abc',
    'rs232t1000__injbeta_d1_s42__ys_abc',
    'rs232t1000__injepsilon_d1_s42__ys_abc',
    'rs232t1000__injzeta_d1_s42__ys_abc',
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
    gid_to_new = {int(g): i for i, g in enumerate(ids)}
    keep = np.array([int(a) in gid_to_new and int(b) in gid_to_new
                     for a, b in zip(z['edge_index'][0], z['edge_index'][1])], bool)
    e = z['edge_index'][:, keep]
    edges = np.array([[gid_to_new[int(a)], gid_to_new[int(b)]] for a, b in zip(e[0], e[1])], np.int64).T
    order = {v: i for i, v in enumerate(PANEL)}
    vi = np.array([order[base_names[int(v)]] for v in vi_all[mask]], np.int64)
    assert np.all(vi[edges[0]] == vi[edges[1]])
    np.savez_compressed(T / 'base_inputs.npz', global_ids=ids, x=x,
                        edge_index=edges, view_index=vi)
    plan = dict(created='2026-10-27T00:20:00+08:00',
                scope='4 rs232 injection views: alpha/beta/epsilon/zeta; ys_abc',
                views=[by_view[v] for v in PANEL],
                selection='pre-registered four-view panel; no labels read',
                context='native_unrestricted_combinational_physical_Q_v1',
                cut_rule=dict(max_inputs=8, max_depth=4,
                              choice='complete structural frontier; <=8 leaves'),
                target_rule='one sample per graph cell; comb output; DFF D data cone',
                family_rule='view token between __ segments',
                split='train', sat_timeout=3, sat_batch_nodes=32)
    plan['plan_sha'] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    (T / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    for item in plan['views']:
        one = dict(plan)
        one.pop('plan_sha', None)
        one['views'] = [item]
        one['selection'] = 'single k8 panel view; no labels read'
        one['plan_sha'] = hashlib.sha256(json.dumps(one, sort_keys=True).encode()).hexdigest()
        d = T / 'views' / item['view']
        d.mkdir(parents=True, exist_ok=True)
        (d / 'plan.json').write_text(json.dumps(one, ensure_ascii=False, indent=2), encoding='utf-8')
    (T / 'panel.json').write_text(json.dumps(dict(panel=PANEL, nodes=len(ids),
                                                  edges=edges.shape[1], source='k6 base subset'),
                                             ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(views=len(PANEL), nodes=len(ids), edges=edges.shape[1],
                          plan_sha=plan['plan_sha']), indent=2))


if __name__ == '__main__':
    main()
