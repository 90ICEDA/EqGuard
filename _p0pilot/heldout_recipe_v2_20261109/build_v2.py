"""held-out recipe v2 assets: full view ranges, aux preservation, fold normalization (cols 25:39, clip 10),
official-index filtering (no random negative substitution), cone remap, old/new maps."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_recipe_v2_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'
L = R / '_p0pilot/control_loader_po_20261105'
sys.path.insert(0, str(L))
sys.path.insert(0, str(R / '_p0pilot/control_signed_carrier_20261109_v3'))
import Signed_common as S
from supervision_loader import FiveGroupLoader

RECIPES = ('ys_abc', 'ys_aig', 'ys_nand')


def sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def contract():
    return json.loads((B / 'input_contract.json').read_text(encoding='utf-8'))


def load_arrays(split):
    folder = B / 'inputs' / f'trans_{split}'
    return {k: np.load(folder / f'{k}.npy') for k in ('x39', 'edge_index', 'y', 'trusted', 'physical')}


def views_of(split):
    return {v['view']: v for v in contract()['shared_inputs'][f'trans_{split}']['views']}


def build_subset(arr, keep, vs):
    rows = []
    for v, lay in vs.items():
        if v in keep:
            rows.extend(range(lay['start'], lay['start'] + (lay['old_stop'] - lay['old_start'])))
    rows = np.array(rows, np.int64)
    old2new = np.full(len(arr['y']), -1, np.int64); old2new[rows] = np.arange(len(rows))
    src, dst = arr['edge_index'][0], arr['edge_index'][1]
    m = (old2new[src] >= 0) & (old2new[dst] >= 0)
    edge = np.stack([old2new[src[m]], old2new[dst[m]]])
    return dict(rows=rows, old2new=old2new, edge=edge,
                x=arr['x39'][rows], y=arr['y'][rows],
                trusted=arr['trusted'][rows], physical=arr['physical'][rows])


def main():
    assert not (OUT / 'COMPLETE.json').exists()
    loader = FiveGroupLoader()
    tr, va, te = load_arrays('train'), load_arrays('val'), load_arrays('test')
    vtr, vva, vte = views_of('train'), views_of('val'), views_of('test')
    # orig train arrays for fold normalization
    orig_tr = {k: np.load(B / 'inputs' / f'orig_train/{k}.npy') for k in ('x39', 'y', 'trusted', 'physical', 'edge_index')}
    report = {}
    for rec in RECIPES:
        keep_tr = {v for v in vtr if rec not in v}
        keep_va = {v for v in vva if rec not in v}
        keep_te = {v for v in vte if rec in v}
        gtr = build_subset(tr, keep_tr, vtr); gva = build_subset(va, keep_va, vva); gte = build_subset(te, keep_te, vte)
        # fold normalization: cols 25:39 over orig_train + trans fold train
        cat = np.concatenate([orig_tr['x39'][:, 25:], gtr['x'][:, 25:]], 0)
        mean = cat.mean(0).astype(np.float32); std = cat.std(0).astype(np.float32); std[std < 1e-6] = 1.0
        # cones
        cone_rows, cone_meta = [], []
        import csv
        with (PREP / 'CONE_CACHE_V2.csv').open(encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r['split'] != 'train' or r['kind'] != 'D' or int(r['label']) < 0 or int(r['n_phys']) < 2:
                    continue
                if r['view'] not in keep_tr:
                    continue
                mem = [int(gtr['old2new'][int(x)]) for x in r['phys_rows'].split('|') if x and gtr['old2new'][int(x)] >= 0]
                mem = [x for x in mem if bool(gtr['trusted'][x]) and bool(gtr['physical'][x])]
                if len(mem) < 2:
                    continue
                cone_rows.extend(mem); cone_meta.append((r['cone_id'], int(r['label']), len(mem)))
        # official G0 indices filtered to fold-eligible rows
        steps, short, kept_counts = [], 0, []
        for step in range(200):
            q = loader.step('trans', 'G0', step)
            ids = np.array(q.indices, copy=True)
            ids = ids[gtr['old2new'][ids] >= 0]
            steps.append(sha(ids)); kept_counts.append(len(ids))
            if len(ids) < 9165:
                short += 1
        np.savez_compressed(OUT / f'{rec}_trans.npz', **{k: gtr[k] for k in ('x', 'y', 'trusted', 'physical', 'rows', 'edge')},
                            cone_rows=np.array(cone_rows, np.int64),
                            cone_label=np.array([m[1] for m in cone_meta], np.int8),
                            cone_ptr=np.array([0] + list(np.cumsum([m[2] for m in cone_meta])), np.int64),
                            mean=mean, std=std)
        np.savez_compressed(OUT / f'{rec}_val.npz', **{k: gva[k] for k in ('x', 'y', 'trusted', 'physical', 'rows', 'edge')})
        np.savez_compressed(OUT / f'{rec}_test.npz', **{k: gte[k] for k in ('x', 'y', 'trusted', 'physical', 'rows', 'edge')})
        report[rec] = dict(train_views=len(keep_tr), val_views=len(keep_va), test_views=len(keep_te),
                           train_nodes=len(gtr['y']), val_nodes=len(gva['y']), test_nodes=len(gte['y']),
                           aux_train=int((~gtr['physical']).sum()),
                           cones=len(cone_meta), pos=sum(1 for m in cone_meta if m[1] == 1),
                           neg=sum(1 for m in cone_meta if m[1] == 0), members=len(cone_rows),
                           index_short_steps=short, min_kept=int(min(kept_counts)),
                           max_kept=int(max(kept_counts)), norm_fit_nodes=int(len(orig_tr['y']) + len(gtr['y'])),
                           norm_sha=sha(np.concatenate([mean, std])))
    (OUT / 'FOLD_REPORT.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (OUT / 'COMPLETE.json').write_text(json.dumps(dict(recipes=RECIPES, report=report), indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
