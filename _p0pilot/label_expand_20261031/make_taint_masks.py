"""Build taint-based trusted-normal mask (general, no control-view assumption).

Three-way split per injection view (anchors = bound trojan positives):
  A forward-reachable (not crossing DFF)  -> affected; NOT used as normal
  B fanin-reachable                       -> ambiguous; stays unknown
  C neither                               -> functionally independent -> trusted normal

Outputs:
  trust_trans_v2_taint.npy        trust OR C(injection views)
  trust_trans_v2_taint_all.npy    the above OR train-split control views (superset)
  taint_masks_report.json         per-split coverage before/after, counts
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
    seen = np.zeros(N, bool); seen[seeds] = True
    stack = list(seeds)
    while stack:
        u = stack.pop()
        if stop[u]:
            continue
        for e in range(indptr[u], indptr[u + 1]):
            w = int(nbr[e])
            if not seen[w]:
                seen[w] = True; stack.append(w)
    return seen


def main():
    base_vi = np.load(FROZEN / 'view_index_all.npy')
    base_trust = np.load(DATA / 'trust_trans.npy')
    split = json.loads((ROOT / 'generate_trans/folds/hosts_bt31/views.json').read_text(encoding='utf-8'))
    order = split['train_views'] + split['val_views'] + split['test_views']

    lab = json.loads((DATA / 'label_transport.json').read_text(encoding='utf-8'))['trans_labels_from_orig']
    keys = np.fromiter((int(k) for k in lab), np.int64, len(lab))
    vals = np.fromiter(lab.values(), np.int8, len(lab))
    base_y = np.full(len(base_vi), -1, np.int8); base_y[keys] = vals

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

    split_id = np.full(N, -1, np.int8)
    for k in range(3):
        for v in (split['train_views'], split['val_views'], split['test_views'])[k]:
            split_id[vi == np.where(np.array(order) == v)[0][0]] = k
    # simpler split mapping via view index
    idx = {v: i for i, v in enumerate(order)}
    split_id[:] = -1
    for k in range(3):
        for v in (split['train_views'], split['val_views'], split['test_views'])[k]:
            split_id[vi == idx[v]] = k
    fam = np.array([v.split('__')[1] for v in order])
    view_fam = np.where(vi >= 0, fam[np.clip(vi, 0, len(order) - 1)], '')

    normal = np.zeros(N, bool)
    affected = np.zeros(N, bool)
    ambig = np.zeros(N, bool)
    for k, v in enumerate(order):
        if fam[k].startswith('ctl'):
            continue
        m = vi == k
        anchors = np.flatnonzero(m & (y == 1))
        if not len(anchors):
            continue
        A = closure(f_ind, dst, anchors, is_dff, N)
        B = closure(r_ind, rdst, anchors, is_dff, N)
        c = m & ~trust & ~A & ~B
        normal |= c
        affected |= (m & ~trust & A)
        ambig |= (m & ~trust & B & ~A)

    train_ctl = (split_id == 0) & np.char.startswith(view_fam.astype(str), 'ctl')
    taint = trust | normal
    allv = taint | train_ctl
    np.save(OUT / 'trust_trans_v2_taint.npy', taint)
    np.save(OUT / 'trust_trans_v2_taint_all.npy', allv)

    stats = {}
    for k, name in ((0, 'train'), (1, 'val'), (2, 'test')):
        m = split_id == k
        stats[name] = dict(
            nodes=int(m.sum()), positives=int((m & (y == 1)).sum()),
            base_trusted=int(trust[m].sum()), base_rate=round(float(trust[m].mean()), 4),
            taint_trusted=int(taint[m].sum()), taint_rate=round(float(taint[m].mean()), 4),
            all_trusted=int(allv[m].sum()), all_rate=round(float(allv[m].mean()), 4),
            new_normal=int((normal & m).sum()), new_affected=int((affected & m).sum()),
            still_ambiguous=int((ambig & m).sum()),
        )
    rep = dict(rule='injection views: A forward=affected(not normal), B fanin=ambiguous(unknown), '
                    'C neither=trusted normal; control views untouched except optional train control certification',
               graph_edges='edge_index_directed_v2.npy (v2 directed all-pin)',
               stop_rule='do not expand through DFF cells',
               total=dict(new_normal=int(normal.sum()), new_affected=int(affected.sum()),
                          still_ambiguous=int(ambig.sum())),
               split_stats=stats,
               files=dict(taint='trust_trans_v2_taint.npy', taint_all='trust_trans_v2_taint_all.npy'))
    (OUT / 'taint_masks_report.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(rep['split_stats'], ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
