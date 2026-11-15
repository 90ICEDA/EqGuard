"""Freeze native host negatives using provenance and a train-only similarity rule."""
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
P = OUT.parent
V = P / 'control_boundary_v3_20261104'
F = ROOT / 'generate_trans/folds/hosts_bt31'
DICT = P / 'control_loader_po_20261105/view_dictionary.csv'


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(name, items):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(items[0]))
        writer.writeheader()
        writer.writerows(items)


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def names(path):
    return [s.strip().lstrip('\\') for s in path.read_text(encoding='utf-8').splitlines()]


def inputs(split):
    return {k: np.load(V / 'inputs' / f'trans_{split}' / f'{k}.npy', mmap_mode='r')
            for k in ('y', 'trusted', 'physical', 'x39')}


def po_bin(d):
    assert ((d >= 0) | (d == -1)).all()
    return np.select([d == -1, d == 0, d <= 2, d <= 5], [0, 1, 2, 3], default=4)


def view_ids(view):
    return np.arange(int(view['start']), int(view['physical_stop']))


def key(view, data, ids):
    x = data['x39'][ids]
    assert (x[:, :25].sum(axis=1) == 1).all()
    return x[:, :25].argmax(axis=1)*5 + po_bin(x[:, 30])


def norm(data, ids, stats):
    return np.clip((data['x39'][ids, 25:] - stats[0]) / stats[1], -10, 10)


def native(split, by_split, arrays, contract):
    trans_path = F / 'data/processed/node_names_trans.txt'
    orig_path = P / 'round32_20261029/orig_names/node_names_orig.txt'
    align_path = F / 'data/for_train/alignment.json'
    used = [trans_path, orig_path, align_path]
    trans_names, orig_names = names(trans_path), names(orig_path)
    views = by_split[split]
    orig_views = {v['view']: v for v in contract['shared_inputs'][f'orig_{split}']['views']}
    orig_dir = ROOT / contract['shared_inputs'][f'orig_{split}']['folder']
    orig_y = np.load(orig_dir / 'y.npy', mmap_mode='r')
    used.append(orig_dir / 'y.npy')
    prov = defaultdict(set)
    for p in sorted((ROOT / 'generate_trans').glob('hosts*/*/provenance.json')):
        matching = [r for r in read(p) if r.get('view') in orig_views and r.get('kind') == 'trojan']
        if matching:
            used.append(p)
        for r in matching:
            prov[r['view']].add(tuple(sorted(s.lstrip('\\') for s in r['new_gates'])))
    source_ids = {s: i for i, s in enumerate(sorted({v['source'] for v in views}))}
    source_by_orig = np.full(len(orig_names), -1, np.int32)
    bad_orig = np.ones(len(orig_names), bool)
    inserted = {}
    for source, code in source_ids.items():
        v = orig_views[source]
        lo, hi = v['old_start'], v['old_stop']
        ns = orig_names[lo:hi]
        pp = [set(p) for p in prov[source] if p and set(p) <= set(ns)]
        assert len(pp) == 1, (source, pp)
        inserted[source] = pp[0]
        source_by_orig[lo:hi] = code
        bad_orig[lo:hi] = np.isin(ns, list(pp[0])) | (orig_y[v['start']:v['physical_stop']] == 1)
    align = np.asarray(read(align_path), dtype=np.int64)
    oi, ti = align.T
    assert oi.min() >= 0 and oi.max() < len(orig_names) and ti.min() >= 0 and ti.max() < len(trans_names)
    expected = np.full(len(trans_names), -1, np.int32)
    for v in views:
        expected[int(v['old_start']):int(v['old_stop'])] = source_ids[v['source']]
    seen = expected[ti] >= 0
    parents = np.bincount(ti[seen], minlength=len(trans_names)) > 0
    bad = np.zeros(len(trans_names), bool)
    bad[ti[seen & (bad_orig[oi] | (source_by_orig[oi] != expected[ti]))]] = True
    result, audit = {}, []
    for v in views:
        ids = view_ids(v)
        lo, hi = int(v['old_start']), int(v['old_stop'])
        ns = trans_names[lo:hi]
        assert len(ids) == len(ns) and arrays['physical'][ids].all()
        path = F / 'mappings' / (v['view'] + '.json')
        used.append(path)
        mapping = read(path)
        assert mapping['src_view'] == v['source'] and mapping['rw_view'] == v['view']
        lookup = {name: i for i, name in enumerate(ns)}
        assert len(lookup) == len(ns)
        traced, excluded = 0, set()
        for name in inserted[v['source']]:
            found = {lookup[t.lstrip('\\')] for t in mapping['node_alignment'].get(name, [])
                     if t.lstrip('\\') in lookup}
            if name in lookup:
                found.add(lookup[name])
            traced += bool(found)
            excluded.update(found)
        valid = arrays['trusted'][ids] & (arrays['y'][ids] == 0)
        pure = valid & parents[lo:hi] & ~bad[lo:hi]
        pure[list(excluded)] = False
        complete = traced == len(inserted[v['source']])
        result[v['view']] = ids[pure] if complete else ids[:0]
        audit.append(dict(split=split, view=v['view'], source=v['source'], recipe=v['recipe'],
                          trusted_negative=int(valid.sum()), pure_parent=int(pure.sum()),
                          source_added=len(inserted[v['source']]), traced=traced,
                          strict_native=len(result[v['view']])))
    return result, audit, used


def main():
    contract = read(V / 'input_contract.json')
    assert contract['columns39'][30] == 'directed_distance_to_PO_driver'
    by_split = {s: [v for v in rows(DICT) if v['key'] == f'trans_{s}' and v['kind'] == 'trojan']
                for s in ('train', 'val', 'test')}
    train = inputs('train')
    pos = defaultdict(list)
    with np.load(V / 'normalization.npz') as z:
        stats = z['mean'][25:], z['std'][25:]
    for v in by_split['train']:
        ids = view_ids(v)
        ids = ids[train['trusted'][ids] & train['physical'][ids] & (train['y'][ids] == 1)]
        kk = key(v, train, ids)
        for k in np.unique(kk):
            pos[v['recipe'], int(k)].append(ids[kk == k])
    trees = {k: cKDTree(norm(train, np.unique(np.concatenate(ids)), stats)) for k, ids in pos.items()}

    def distances(v, arrays, ids):
        d = np.full(len(ids), np.inf)
        kk = key(v, arrays, ids)
        for k in np.unique(kk):
            tree = trees.get((v['recipe'], int(k)))
            if tree is not None:
                use = kk == k
                d[use] = tree.query(norm(arrays, ids[use], stats), k=1)[0] / np.sqrt(14)
        return d

    hp_path = P / 'control_overall_contract_20261105/trojan_host_trans_train.npz'
    with np.load(hp_path) as z:
        hrows, hview = z['rows'][z['eligible']], z['view_id'][z['eligible']]
    by_recipe = defaultdict(list)
    for v in by_split['train']:
        ids = hrows[hview == int(v['view_id'])]
        assert np.isin(ids, view_ids(v)).all()
        d = distances(v, train, ids)
        by_recipe[v['recipe']].append(d[np.isfinite(d)])
    cutoff = {}
    for r, pieces in by_recipe.items():
        support = np.concatenate(pieces)
        if len(support):
            cutoff[r] = float(np.quantile(support, .10))
    audits, used = [], [DICT, V / 'input_contract.json', V / 'normalization.npz', hp_path, Path(__file__)]
    output = {}
    for s in ('val', 'test'):
        arrays = inputs(s)
        eligible, audit, paths = native(s, by_split, arrays, contract)
        used.extend(paths)
        for v, row in zip(by_split[s], audit):
            assert row['view'] == v['view']
            ids = eligible[v['view']]
            d = distances(v, arrays, ids)
            hard = np.isfinite(d) & (d <= cutoff.get(v['recipe'], -1))
            row.update(template_supported=int(np.isfinite(d).sum()), hard=int(hard.sum()))
            output[v['view']] = ids[hard]
            output[v['view']+'__native'] = ids
            audits.append(row)
    for s in ('train', 'val', 'test'):
        used.extend(V / 'inputs' / f'trans_{s}' / f'{k}.npy' for k in ('y','trusted','physical','x39'))
    np.savez_compressed(OUT / 'PANEL.npz', **output)
    write('COVERAGE.csv', audits)
    manifest = dict(train_only_rule='same recipe/gate/PO bin, normalized 14-d RMS <= recipe train-native p10',
                    cutoff=cutoff, inputs={str(p.relative_to(ROOT)): digest(p) for p in sorted(set(used))},
                    panel=digest(OUT / 'PANEL.npz'), predictions_read=False)
    (OUT / 'FROZEN.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    for s in ('val','test'):
        rr = [r for r in audits if r['split']==s]
        print(s, len(rr), sum(r['strict_native']>0 for r in rr), sum(r['hard']>0 for r in rr),
              sum(r['strict_native'] for r in rr), sum(r['hard'] for r in rr), flush=True)


if __name__ == '__main__':
    main()
