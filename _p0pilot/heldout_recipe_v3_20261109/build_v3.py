"""held-out recipe v3 assets: [start,stop) full ranges incl. aux rows, physical_stop split,
fold G0 rebuild (positives + 8192 common + 144 extras), normalization fit rows, cone remap."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

R = Path(r'C:\Users\91344\Desktop\GraphSAINT\GIN_train')
OUT = R / '_p0pilot/heldout_recipe_v3_20261109'
B = R / '_p0pilot/control_boundary_v3_20261104'
PREP = R / '_p0pilot/seed42_supervised_prep_20261109'
L = R / '_p0pilot/control_loader_po_20261105'
sys.path.insert(0, str(L))
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
    rows, aux = [], 0
    phys_rows = []
    for v, lay in vs.items():
        if v not in keep:
            continue
        rows.extend(range(lay['start'], lay['stop']))
        phys_rows.extend(range(lay['start'], lay['physical_stop']))
        aux += lay['stop'] - lay['physical_stop']
    rows = np.array(rows, np.int64); phys_rows = np.array(phys_rows, np.int64)
    old2new = np.full(len(arr['y']), -1, np.int64); old2new[rows] = np.arange(len(rows))
    src, dst = arr['edge_index'][0], arr['edge_index'][1]
    m = (old2new[src] >= 0) & (old2new[dst] >= 0)
    edge = np.stack([old2new[src[m]], old2new[dst[m]]])
    is_phys = np.zeros(len(rows), bool); is_phys[old2new[phys_rows]] = True
    return dict(rows=rows, old2new=old2new, edge=edge, x=arr['x39'][rows], y=arr['y'][rows],
                trusted=arr['trusted'][rows], physical=arr['physical'][rows], is_phys=is_phys,
                aux=aux, new2old=np.arange(len(rows), dtype=np.int64))


def main():
    assert not (OUT / 'COMPLETE.json').exists()
    loader = FiveGroupLoader()
    tr, va, te = load_arrays('train'), load_arrays('val'), load_arrays('test')
    vtr, vva, vte = views_of('train'), views_of('val'), views_of('test')
    orig_tr = {k: np.load(B / 'inputs' / f'orig_train/{k}.npy') for k in ('x39',)}
    common_ids = loader.pools['trans']['common_negative']
    h_ids = loader.pools['trans']['H']
    report = {}
    for rec in RECIPES:
        keep_tr = {v for v in vtr if rec not in v}
        keep_va = {v for v in vva if rec not in v}
        keep_te = {v for v in vte if rec in v}
        gtr = build_subset(tr, keep_tr, vtr); gva = build_subset(va, keep_va, vva); gte = build_subset(te, keep_te, vte)
        # eligibility in fold: trusted & physical & y==0
        elig = (gtr['y'] == 0) & gtr['trusted'] & gtr['physical']
        o2n = gtr['old2new']
        common_pool = np.array([o2n[x] for x in common_ids if o2n[x] >= 0], np.int64)
        h_pool = np.array([o2n[x] for x in h_ids if o2n[x] >= 0], np.int64)
        common_pool = common_pool[elig[common_pool]]
        h_pool = h_pool[elig[h_pool]]
        pos = np.where((gtr['y'] == 1) & gtr['trusted'] & gtr['physical'])[0]
        steps, comp, exposure = [], [], np.zeros(len(gtr['y']), np.int32)
        for step in range(200):
            rng = np.random.default_rng(42 + step)
            if len(common_pool) < 8192 or len(h_pool) < 144:
                raise SystemExit(f'candidate shortfall {rec}: common={len(common_pool)} h={len(h_pool)}')
            c = rng.choice(common_pool, 8192, replace=False)
            e = rng.choice(h_pool, 144, replace=False)
            ids = np.concatenate([pos, c, e]).astype(np.int64)
            exposure[ids] += 1
            steps.append(sha(ids)); comp.append((len(pos), 8192, 144))
        # cones
        cone_rows, cone_meta = [], []
        import csv
        with (PREP / 'CONE_CACHE_V2.csv').open(encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r['split'] != 'train' or r['kind'] != 'D' or int(r['label']) < 0 or int(r['n_phys']) < 2:
                    continue
                if r['view'] not in keep_tr:
                    continue
                mem = [int(o2n[int(x)]) for x in r['phys_rows'].split('|') if x and o2n[int(x)] >= 0]
                mem = [x for x in mem if bool(gtr['trusted'][x]) and bool(gtr['physical'][x])]
                if len(mem) < 2:
                    continue
                cone_rows.extend(mem); cone_meta.append((r['cone_id'], int(r['label']), len(mem)))
        # normalization fit rows: orig all + trans fold train, cols 25:39
        fit_rows = np.arange(len(orig_tr['x39']), dtype=np.int64)
        cat = np.concatenate([orig_tr['x39'][:, 25:], gtr['x'][:, 25:]], 0)
        mean = cat.mean(0).astype(np.float32); std = cat.std(0).astype(np.float32); std[std < 1e-6] = 1.0
        np.savez_compressed(OUT / f'{rec}_trans.npz', **{k: gtr[k] for k in ('x', 'y', 'trusted', 'physical', 'rows', 'edge', 'is_phys', 'new2old')},
                            cone_rows=np.array(cone_rows, np.int64),
                            cone_label=np.array([m[1] for m in cone_meta], np.int8),
                            cone_ptr=np.array([0] + list(np.cumsum([m[2] for m in cone_meta])), np.int64),
                            mean=mean, std=std, pos=pos, common_pool=common_pool, h_pool=h_pool,
                            steps=np.array(steps), comp=np.array(comp), exposure=exposure)
        np.savez_compressed(OUT / f'{rec}_val.npz', **{k: gva[k] for k in ('x', 'y', 'trusted', 'physical', 'rows', 'edge', 'is_phys', 'new2old')})
        np.savez_compressed(OUT / f'{rec}_test.npz', **{k: gte[k] for k in ('x', 'y', 'trusted', 'physical', 'rows', 'edge', 'is_phys', 'new2old')})
        report[rec] = dict(train_views=len(keep_tr), val_views=len(keep_va), test_views=len(keep_te),
                           train_nodes=int(len(gtr['y'])), val_nodes=int(len(gva['y'])), test_nodes=int(len(gte['y'])),
                           aux_train=int(gtr['aux']), aux_val=int(gva['aux']), aux_test=int(gte['aux']),
                           pos=int(len(pos)), common_capacity=int(len(common_pool)), h_capacity=int(len(h_pool)),
                           cones=len(cone_meta), cone_pos=sum(1 for m in cone_meta if m[1] == 1),
                           cone_neg=sum(1 for m in cone_meta if m[1] == 0), members=len(cone_rows),
                           norm_fit_rows=int(len(fit_rows) + len(gtr['y'])),
                           norm_sha=sha(np.concatenate([mean, std])),
                           exposure_unique=int((exposure > 0).sum()), exposure_max=int(exposure.max()),
                           step0=steps[0])
    (OUT / 'FOLD_REPORT.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (OUT / 'COMPLETE.json').write_text(json.dumps(dict(recipes=RECIPES, report=report), indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
