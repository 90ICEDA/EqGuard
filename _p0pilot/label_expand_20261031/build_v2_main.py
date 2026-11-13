"""P0: rebuild a v2 main graph (additive) + exact x39<->global-id mapping.

P0a  p2_mapping/<split>_{global_ids,is_virtual}.npy   (x39 row -> graph global id)
P0b  processed_v2/trans_graph_v2.pt                   (x=features39_v2, directed edges)

No existing file is overwritten.
"""
import json, hashlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
FOLD = ROOT / 'generate_trans/folds/hosts_bt31'
V2 = FOLD / 'data/derived_v2/bitwise_alias_20261029_v2'
FROZEN = ROOT / '_p0pilot/round29_20261029/frozen'


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    rep = {}
    vi = np.load(FROZEN / 'view_index_all.npy')
    comp = json.loads((V2 / 'COMPLETE.json').read_text(encoding='utf-8'))
    rows = comp['rows']
    order = json.loads((FOLD / 'views.json').read_text(encoding='utf-8'))
    names = order['train_views'] + order['val_views'] + order['test_views']
    idx = {v: i for i, v in enumerate(names)}
    role = {v: s for s, k in [('train', 'train_views'), ('val', 'val_views'), ('test', 'test_views')]
            for v in order[k]}

    # virtual node ids are assigned sequentially in row order (v2 build)
    virt_base = int(vi.shape[0])
    cum = 0
    virt_of_row = {}
    for r in rows:
        virt_of_row[r['view']] = list(range(virt_base + cum, virt_base + cum + r['virtual_nodes']))
        cum += r['virtual_nodes']
    assert cum + virt_base == comp['total_graph_nodes'], (cum, comp['total_graph_nodes'])

    mapdir = OUT / 'p2_mapping'; mapdir.mkdir(parents=True, exist_ok=True)
    perm = {}
    for s in ('train', 'val', 'test'):
        ids, vir = [], []
        for r in rows:
            if role.get(r['view']) != s:
                continue
            ids.extend(range(r['start'], r['stop']))
            vir.extend([False] * (r['stop'] - r['start']))
            vids = virt_of_row[r['view']]
            ids.extend(vids); vir.extend([True] * len(vids))
        gid = np.asarray(ids, dtype=np.int64); isv = np.asarray(vir, bool)
        np.save(mapdir / f'x39row_to_global_{s}.npy', gid)
        np.save(mapdir / f'x39row_is_virtual_{s}.npy', isv)
        perm[s] = dict(rows=len(gid), virtual=int(isv.sum()), physical=int((~isv).sum()),
                       max_gid=int(gid.max()), first=int(gid[0]))
    rep['p2_mapping'] = perm

    # ---- v2 main graph ----
    fx = np.load(V2 / 'features39_v2.npy', mmap_mode='r')
    fv = np.load(V2 / 'virtual_features39_v2.npy', mmap_mode='r')
    assert len(fx) == virt_base and len(fv) == cum
    x = np.empty((len(fx) + len(fv), 39), np.float32)
    x[:len(fx)] = fx; x[len(fx):] = fv
    ei = np.load(V2 / 'edge_index_directed_v2.npy')

    lab = json.loads((FOLD / 'data/for_train/label_transport.json').read_text(encoding='utf-8'))['trans_labels_from_orig']
    y = np.full(len(x), -1, np.int8)
    for k, v in lab.items():
        y[int(k)] = v
    trust = np.zeros(len(x), bool)
    trust[:len(vi)] = np.load(FOLD / 'data/for_train/trust_trans.npy')

    split_id = np.full(len(x), -1, np.int8)
    split_id[:len(vi)] = np.where(vi < 0, -1, np.where(vi < len(order['train_views']), 0,
                              np.where(vi < len(order['train_views']) + len(order['val_views']), 1, 2)))
    for r in rows:
        for g in virt_of_row[r['view']]:
            split_id[g] = split_id[r['start']]

    import torch
    data = torch.utils.data.TensorDataset  # noqa: only to keep torch imported once
    torch.set_num_threads(1)
    graph = dict(x=torch.from_numpy(x), edge_index=torch.from_numpy(ei.astype(np.int64)),
                 y=torch.from_numpy(y), trust=torch.from_numpy(trust), split=torch.from_numpy(split_id))
    gdir = FOLD / 'data/processed_v2'; gdir.mkdir(parents=True, exist_ok=True)
    gp = gdir / 'trans_graph_v2.pt'
    torch.save(graph, gp)
    rep['graph'] = dict(path=str(gp.relative_to(ROOT)), nodes=int(len(x)), edges=int(ei.shape[1]),
                        size=int(gp.stat().st_size), sha=sha(gp))
    (OUT / 'p0_v2_graph_report.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
