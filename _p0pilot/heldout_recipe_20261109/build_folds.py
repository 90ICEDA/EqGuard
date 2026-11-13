"""Build held-out-recipe fold assets (trans subgraphs, normalization, cone mapping, sampling)."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_recipe_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'
sys.path.insert(0, str(R / '_p0pilot/control_signed_carrier_20261109_v3'))
import Signed_common as S


def sha_arr(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def load_split(split, domain='trans'):
    folder = B / 'inputs' / f'{domain}_{split}'
    return dict(x=np.load(folder / 'x39.npy'), edge=np.load(folder / 'edge_index.npy'),
                y=np.load(folder / 'y.npy'), trusted=np.load(folder / 'trusted.npy'),
                physical=np.load(folder / 'physical.npy'))


def views(split, domain='trans'):
    c = json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))
    return {v['view']: v for v in c['shared_inputs'][f'{domain}_{split}']['views']}


def subgraph(arr, keep_views, vs):
    rows = []
    for v, lay in vs.items():
        if v in keep_views:
            rows.extend(range(lay['start'], lay['start'] + (lay['old_stop'] - lay['old_start'])))
    rows = np.array(sorted(rows), np.int64)
    old2new = np.full(len(arr['y']), -1, np.int64); old2new[rows] = np.arange(len(rows))
    src, dst = arr['edge'][0], arr['edge'][1]
    m = (old2new[src] >= 0) & (old2new[dst] >= 0)
    edge = np.stack([old2new[src[m]], old2new[dst[m]]])
    return dict(x=arr['x'][rows], edge=edge, y=arr['y'][rows], trusted=arr['trusted'][rows],
                physical=arr['physical'][rows], old_rows=rows, old2new=old2new)


def main():
    assert not (OUT / 'FOLDS_COMPLETE.json').exists()
    recipes = ('ys_abc', 'ys_aig', 'ys_nand')
    tr, va, te = load_split('train'), load_split('val'), load_split('test')
    vtr, vva, vte = views('train'), views('val'), views('test')
    report = {}
    for rec in recipes:
        keep_tr = {v for v in vtr if rec not in v}
        keep_va = {v for v in vva if rec not in v}
        keep_te = {v for v in vte if rec in v}
        gtr = subgraph(tr, keep_tr, vtr); gva = subgraph(va, keep_va, vva); gte = subgraph(te, keep_te, vte)
        # normalization over fold train nodes (trans side only here; orig unchanged)
        mean = gtr['x'].mean(0).astype(np.float32); std = gtr['x'].std(0).astype(np.float32)
        std[std < 1e-6] = 1.0
        # cones: filter train D cones to fold train views, remap rows
        cone_rows, cone_meta = [], []
        import csv
        with (PREP / 'CONE_CACHE_V2.csv').open(encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r['split'] != 'train' or r['kind'] != 'D' or int(r['label']) < 0 or int(r['n_phys']) < 2:
                    continue
                if r['view'] not in keep_tr:
                    continue
                mem = [int(x) for x in r['phys_rows'].split('|') if x]
                mem = [int(gtr['old2new'][x]) for x in mem if gtr['old2new'][x] >= 0]
                mem = [x for x in mem if bool(gtr['trusted'][x]) and bool(gtr['physical'][x])]
                if len(mem) < 2:
                    continue
                cone_rows.extend(mem); cone_meta.append((r['cone_id'], int(r['label']), len(mem)))
        # deterministic sampling: all positives + 8336 negatives per step
        pos = np.where((gtr['y'] == 1) & gtr['trusted'] & gtr['physical'])[0]
        neg = np.where((gtr['y'] == 0) & gtr['trusted'] & gtr['physical'])[0]
        rng = np.random.default_rng(42)
        steps = []
        for step in range(200):
            pick = rng.choice(neg, size=8336, replace=len(neg) < 8336)
            ids = np.concatenate([pos, pick]).astype(np.int64)
            steps.append(hashlib.sha256(ids.tobytes()).hexdigest())
        np.savez_compressed(OUT / f'{rec}_trans.npz', **{k: gtr[k] for k in ('x', 'edge', 'y', 'trusted', 'physical', 'old_rows')},
                            cone_rows=np.array(cone_rows, np.int64),
                            cone_label=np.array([m[1] for m in cone_meta], np.int8),
                            cone_ptr=np.array([0] + list(np.cumsum([m[2] for m in cone_meta])), np.int64),
                            mean=mean, std=std)
        np.savez_compressed(OUT / f'{rec}_val.npz', **{k: gva[k] for k in ('x', 'edge', 'y', 'trusted', 'physical', 'old_rows')})
        np.savez_compressed(OUT / f'{rec}_test.npz', **{k: gte[k] for k in ('x', 'edge', 'y', 'trusted', 'physical', 'old_rows')})
        report[rec] = dict(train_views=len(keep_tr), val_views=len(keep_va), test_views=len(keep_te),
                           train_nodes=len(gtr['y']), val_nodes=len(gva['y']), test_nodes=len(gte['y']),
                           cones=len(cone_meta), pos=sum(1 for m in cone_meta if m[1] == 1),
                           neg=sum(1 for m in cone_meta if m[1] == 0), members=len(cone_rows),
                           positives=int(len(pos)), negatives=int(len(neg)), neg_per_step=8336,
                           norm_fit_nodes=int(len(gtr['y'])), norm_sha=sha_arr(np.concatenate([mean, std])),
                           index_sha=steps[0], step0_index_sha=steps[0])
    (OUT / 'FOLD_REPORT.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (OUT / 'FOLDS_COMPLETE.json').write_text(json.dumps(dict(recipes=recipes, report=report), indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
