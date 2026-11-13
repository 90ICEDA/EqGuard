"""Bind a two-hop positive training mask without touching evaluation."""
import numpy as np

from audit import CACHE, OUT, P, V5, load_module, read, sha, write_json
from audit_endpoint_locality import cache_records, d_neighborhood, view_graph

HOPS = 2


def main():
    source = OUT / 'PILOT_PREFLIGHT.json'
    contract = read(source)
    panel = load_module('training_locality', P / 'lcone_endpoint_frozen_20261112/audit.py')
    io = load_module('training_fold', V5 / 'fold_io.py')
    _, _, names, layouts = panel.S.load_snapshot('train')
    views = {p['view'] for f in contract['folds'].values() for p in f['pool']}
    cache = cache_records(CACHE, 'train', views)
    graph = view_graph('train', layouts, views)
    mapping = {v: panel.S.view_rows(layouts, names, v) for v in views}
    output = {}
    for fold, plan in contract['folds'].items():
        path = io.V4 / f'{fold}_train_map.npz'
        assert sha(path) == plan['train_map_sha256']
        with np.load(path) as data:
            rows, reverse, physical = (data[k] for k in ('new2old', 'old2new', 'physical'))
        masks = []
        for pair_id, p in enumerate(plan['pool']):
            view = p['view']
            driver, hops = d_neighborhood(view, p['positive'], graph[view], mapping[view], layouts[view], cache)
            assert driver in hops and not view.endswith('__' + fold)
            original = p['pos_rows']
            assert set(rows[original]) == hops.keys()
            local = sorted(int(reverse[r]) for r, h in hops.items() if h <= HOPS)
            assert set(local) <= set(original) and len(local) > 0 and physical[local].all()
            peaks = p['reference_pos_argmax']
            masks.append(dict(pair_id=pair_id, view=view, source=p['source'], endpoint=p['positive'],
                              near_positive_rows=local, full_positive_count=len(original),
                              reference_winner_hops=[hops[int(rows[r])] for r in peaks],
                              reference_winner_kept=bool(set(peaks) & set(local))))
        output[fold] = dict(masks=masks, train_map_sha256=sha(path))
        print(fold, len(masks), [x['reference_winner_hops'] for x in masks],
              'reference maxima retained', sum(x['reference_winner_kept'] for x in masks), flush=True)
    write_json(OUT / 'D_LOCALITY_POSITIVE_MASK.json', dict(folds=output, hops=HOPS, contract_sha256=sha(source),
               optimizer_steps=0, forward_passes=0, sat_cec_calls=0, labels_modified=False))


if __name__ == '__main__':
    main()
