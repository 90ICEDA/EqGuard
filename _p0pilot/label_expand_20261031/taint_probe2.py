"""General coverage probe v2: forward + backward taint closure from bound anchors.

Sound 3-way split for injection views:
  A. forward-reachable (not crossing DFF)  -> trojan-affected, cannot be normal
  B. backward-reachable (trigger/host fanin, not crossing DFF) -> ambiguous, keep unknown
  C. neither                               -> functionally independent of the trojan -> normal

Writes taint_probe2.json only (no label file).
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA = ROOT / 'generate_trans/folds/hosts_bt31/data/for_train'
FROZEN = ROOT / '_p0pilot/round29_20261029/frozen'
V2 = ROOT / 'generate_trans/folds/hosts_bt31/data/derived_v2/bitwise_alias_20261029_v2'


def closure(indptr, nbr, seeds, stop, N):
    seen = np.zeros(N, bool)
    seen[seeds] = True
    stack = list(seeds)
    while stack:
        u = stack.pop()
        if stop[u]:
            continue
        for e in range(indptr[u], indptr[u + 1]):
            w = int(nbr[e])
            if not seen[w]:
                seen[w] = True
                stack.append(w)
    return seen


def main():
    base_vi = np.load(FROZEN / 'view_index_all.npy')
    base_trust = np.load(DATA / 'trust_trans.npy')
    split = json.loads((ROOT / 'generate_trans/folds/hosts_bt31/views.json').read_text(encoding='utf-8'))
    order = split['train_views'] + split['val_views'] + split['test_views']

    lab = json.loads((DATA / 'label_transport.json').read_text(encoding='utf-8'))['trans_labels_from_orig']
    keys = np.fromiter((int(k) for k in lab), np.int64, len(lab))
    vals = np.fromiter(lab.values(), np.int8, len(lab))
    base_y = np.full(len(base_vi), -1, np.int8)
    base_y[keys] = vals

    ei = np.load(V2 / 'edge_index_directed_v2.npy')
    N = int(ei.max()) + 1
    vi = np.full(N, -1, base_vi.dtype); vi[:len(base_vi)] = base_vi
    trust = np.zeros(N, bool); trust[:len(base_trust)] = base_trust
    y = np.full(N, -1, np.int8); y[:len(base_y)] = base_y

    feat = np.load(DATA / 'feats_trans.npy', mmap_mode='r')
    is_dff = np.zeros(len(base_vi), bool)
    for c in [4, 5, 6, 19, 20]:
        is_dff |= np.asarray(feat[:, c]) > 0.5
    del feat
    is_dff = np.concatenate([is_dff, np.zeros(N - len(is_dff), bool)])

    src, dst = ei[0], ei[1]
    o = np.lexsort((dst, src)); src, dst = src[o], dst[o]
    f_ind = np.searchsorted(src, np.arange(N + 1))
    o2 = np.lexsort((src, dst)); rsrc, rdst = dst[o2], src[o2]
    r_ind = np.searchsorted(rsrc, np.arange(N + 1))

    rep = {'definition': 'A forward-affected; B fanin-ambiguous; C independent',
           'views': {}, 'totals': {}}
    T = dict(anchors=0, A=0, A_unknown=0, B=0, B_unknown=0, C_unknown=0, unknown=0)
    for k, v in enumerate(order):
        if v.split('__')[1].startswith('ctl'):
            continue
        m = vi == k
        anchors = np.flatnonzero(m & (y == 1))
        if not len(anchors):
            continue
        A = closure(f_ind, dst, anchors, is_dff, N)
        B = closure(r_ind, rdst, anchors, is_dff, N)
        unknown = m & ~trust
        A_unk = int(np.sum(A & unknown))
        B_unk = int(np.sum(B & unknown & ~A))
        C_unk = int(np.sum(unknown & ~A & ~B))
        rep['views'][v] = dict(anchors=int(len(anchors)), A=int(A.sum()), A_unknown=A_unk,
                               B=int(B.sum()), B_unknown=B_unk, C_unknown=C_unk,
                               view_unknown=int(unknown.sum()))
        T['anchors'] += len(anchors); T['A'] += int(A.sum()); T['A_unknown'] += A_unk
        T['B'] += int(B.sum()); T['B_unknown'] += B_unk; T['C_unknown'] += C_unk
        T['unknown'] += int(unknown.sum())
    T['C_fraction_of_unknown'] = round(T['C_unknown'] / max(1, T['unknown']), 4)
    rep['totals'] = T
    (OUT / 'taint_probe2.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(T, ensure_ascii=False))


if __name__ == '__main__':
    main()
