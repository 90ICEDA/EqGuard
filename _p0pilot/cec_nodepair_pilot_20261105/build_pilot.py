"""Pilot for option C: build equivalence-cone pairs from SAT proved/differ node pairs.

Cone definition: 4-hop fanin neighbourhood of the root in the split graph (cap 200).
Pair: a SAT-proved equivalent node pair -> real edges; a SAT-differ node pair -> negative edges.
A block pairs one proved pair (pair_a) with one differ pair (pair_b) from the same source.
Read-only w.r.t. existing assets; writes only into this directory.
"""
import collections
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PROC = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
P2 = ROOT / '_p0pilot/round32_20261029'
MAPD = ROOT / '_p0pilot/label_expand_20261031/p2_mapping'
VI = ROOT / '_p0pilot/round29_20261029/frozen/view_index_all.npy'

HOPS = 4
CAP = 200
MIN_CONE = 8
N_BLOCKS = 1000      # 50 updates x 20 blocks
SEED = 42


def main():
    vi = np.load(VI)
    names = json.loads((ROOT / 'generate_trans/folds/hosts_bt31/views.json').read_text(encoding='utf-8'))
    order = names['train_views'] + names['val_views'] + names['test_views']

    gid_tr = np.load(MAPD / 'x39row_to_global_train.npy')
    inv = np.full(int(gid_tr.max()) + 1, -1, np.int64); inv[gid_tr] = np.arange(len(gid_tr))

    folder = ROOT / json.loads((P2 / 'input_contract.json').read_text(encoding='utf-8'))['shared_inputs']['trans_train']['folder']
    e = np.load(folder / 'edge_index.npy').astype(np.int64); src, dst = e[0], e[1]
    n = int(max(src.max(), dst.max())) + 1
    order_e = np.argsort(dst, kind='stable'); ds, ss = dst[order_e], src[order_e]
    ind = np.zeros(n + 1, np.int64); np.add.at(ind, ds + 1, 1); ind = np.cumsum(ind)

    def cone(root):
        seen = {root}; frontier = [root]
        for _ in range(HOPS):
            nxt = []
            for u in frontier:
                for v in ss[ind[u]:ind[u + 1]]:
                    if v not in seen:
                        seen.add(v); nxt.append(v)
                        if len(seen) >= CAP:
                            return sorted(seen)
            frontier = nxt
        return sorted(seen)

    def source_of(row):
        g = int(gid_tr[row]); v = int(vi[g]); return order[v].split('__')[0] + '__' + order[v].split('__')[1]

    def load(npz):
        z = np.load(PROC / npz); a, b, k = z['a'], z['b'], z['kind']
        ra, rb = inv[a], inv[b]
        ok = (ra >= 0) & (rb >= 0)
        return ra[ok], rb[ok], k[ok]

    ra, rb, ka = load('satrel_node_pairs.npz')
    da, db, kd = load('satrel_node_pairs_differ.npz')
    rng = np.random.default_rng(SEED)

    def take(rows_a, rows_b, limit, require_same_source=False):
        idx = rng.permutation(len(rows_a))
        out = []; cones = {}; used = set()
        for i in idx:
            a, b = int(rows_a[i]), int(rows_b[i])
            if a in used or b in used:
                continue
            ca, cb = cone(a), cone(b)
            if min(len(ca), len(cb)) < MIN_CONE:
                continue
            used.add(a); used.add(b)
            out.append((a, b, ca, cb, source_of(a), source_of(b)))
            if len(out) >= limit:
                break
        return out

    proved = take(ra, rb, 4000)
    differ = take(da, db, 4000)
    print('proved cones', len(proved), 'differ cones', len(differ))

    by_source = collections.defaultdict(list)
    for t in proved:
        by_source[t[4]].append(t)
    differ_by_source = collections.defaultdict(list)
    for t in differ:
        differ_by_source[t[4]].append(t)

    pairs, cones_out, blocks = {}, {}, []
    pid = 0
    for src_name, plist in by_source.items():
        dlist = differ_by_source.get(src_name, [])
        if not dlist:
            continue
        for i, p in enumerate(plist):
            q = dlist[i % len(dlist)]
            pa = f'p{pid}'; pb = f'p{pid+1}'; pid += 2
            for name, t in ((pa, p), (pb, q)):
                la = f'{name}_l'; ra_ = f'{name}_r'
                cones_out[la] = dict(cone_id=la, view='', root_row=int(t[0]), graph_rows=[int(x) for x in t[2]])
                cones_out[ra_] = dict(cone_id=ra_, view='', root_row=int(t[1]), graph_rows=[int(x) for x in t[3]])
                pairs[name] = dict(pair_id=name, source_object=src_name, split='train', context_id=src_name,
                                   left_cone=la, right_cone=ra_)
            blocks.append(dict(pair_a=pa, pair_b=pb, pair_weight=0.1, source=src_name))
            if len(blocks) >= N_BLOCKS:
                break
        if len(blocks) >= N_BLOCKS:
            break

    schedule = []
    for u in range(1, 51):
        for blk in blocks[(u - 1) * 20: u * 20]:
            schedule.append(dict(mode='main', seed=SEED, update=u, source=blk['source'],
                                 block_id=f'b{len(schedule):05d}', pair_a=blk['pair_a'], pair_b=blk['pair_b'],
                                 pair_weight=0.1))
    inventory = [dict(pair_id=k, source=v['source_object'], context_id=v['context_id'],
                      left_cone=v['left_cone'], right_cone=v['right_cone']) for k, v in pairs.items()]
    (HERE / 'final_cones.json').write_text(json.dumps(list(cones_out.values())), encoding='utf-8')
    (HERE / 'function_inventory.json').write_text(json.dumps(inventory), encoding='utf-8')
    (HERE / 'schedule.json').write_text(json.dumps(schedule), encoding='utf-8')
    print('blocks', len(blocks), 'pairs', len(pairs), 'cones', len(cones_out), 'schedule rows', len(schedule))


if __name__ == '__main__':
    main()
