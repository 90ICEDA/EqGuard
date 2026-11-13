"""Prototype: estimate how many equivalence-cone pairs can be built from SAT proved node pairs (C).

For each proved node pair (a,b) in the train split, the fanin cone of a and of b are supports of
two SAT-proved equivalent functions. We estimate cone sizes (bounded BFS) and how many pairs have
both cones >= thresholds. Read-only; no training, no SAT.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / 'generate_trans/folds/hosts_bt31/data/processed'
P2 = ROOT / '_p0pilot/round32_20261029'
MAPD = ROOT / '_p0pilot/label_expand_20261031/p2_mapping'
CAP = 2000
SAMPLE = 4000


def main():
    z = np.load(PROC / 'satrel_node_pairs.npz')
    a, b, k = z['a'], z['b'], z['kind']
    gid = np.load(MAPD / 'x39row_to_global_train.npy')
    inv = np.full(int(gid.max()) + 1, -1, np.int64); inv[gid] = np.arange(len(gid))
    ra, rb = inv[a], inv[b]
    ok = (ra >= 0) & (rb >= 0)
    ra, rb = ra[ok], rb[ok]
    print('pairs', len(a), 'mappable', int(ok.sum()))

    folder = ROOT / json.loads((P2 / 'input_contract.json').read_text(encoding='utf-8'))['shared_inputs']['trans_train']['folder']
    edge = np.load(folder / 'edge_index.npy').astype(np.int64)
    n = int(max(edge.max(), ra.max(), rb.max())) + 1
    src, dst = edge[0], edge[1]
    # reverse adjacency (dst -> src) as CSR
    order = np.argsort(dst, kind='stable')
    dst_s, src_s = dst[order], src[order]
    indptr = np.zeros(n + 1, np.int64)
    np.add.at(indptr, dst_s + 1, 1)
    indptr = np.cumsum(indptr)
    print('nodes', n, 'edges', len(edge))

    def cone_size(root):
        seen = np.zeros(n, bool)
        seen[root] = True
        frontier = np.array([root], np.int64)
        size = 1
        while frontier.size and size < CAP:
            nxt = []
            for u in frontier:
                s, e = indptr[u], indptr[u + 1]
                cand = src_s[s:e]
                cand = cand[~seen[cand]]
                if cand.size:
                    seen[cand] = True
                    nxt.append(cand)
                    size += cand.size
                    if size >= CAP:
                        break
            frontier = np.concatenate(nxt) if nxt else np.array([], np.int64)
        return min(size, CAP)

    rng = np.random.default_rng(0)
    idx = rng.choice(len(ra), size=min(SAMPLE, len(ra)), replace=False)
    sizes_a = np.array([cone_size(int(ra[i])) for i in idx])
    sizes_b = np.array([cone_size(int(rb[i])) for i in idx])
    m = np.minimum(sizes_a, sizes_b)
    out = dict(sampled=len(idx), cap=CAP,
               median=float(np.median(m)), p25=float(np.percentile(m, 25)), p75=float(np.percentile(m, 75)),
               ge8=float((m >= 8).mean()), ge16=float((m >= 16).mean()), ge64=float((m >= 64).mean()),
               ge256=float((m >= 256).mean()), capped=float((m >= CAP).mean()))
    print(json.dumps(out, indent=1))
    (Path(__file__).resolve().parent / 'cone_from_nodepairs_estimate.json').write_text(json.dumps(out, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
