"""General coverage probe: forward taint closure from bound trojan anchors.

A cell is "trojan-affected" iff a directed path exists from a bound trojan anchor to it
without crossing a register (DFF). Reached cells cannot be claimed normal; unreached
cells are functionally independent of the trojan.

Writes taint_probe.json only (no label file).
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA = ROOT / 'generate_trans/folds/hosts_bt31/data/for_train'
FROZEN = ROOT / '_p0pilot/round29_20261029/frozen'
V2 = ROOT / 'generate_trans/folds/hosts_bt31/data/derived_v2/bitwise_alias_20261029_v2'


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
    dff_cols = [4, 5, 6, 19, 20]
    is_dff = np.zeros(len(base_vi), bool)
    for c in dff_cols:
        is_dff |= np.asarray(feat[:, c]) > 0.5
    del feat
    is_dff = np.concatenate([is_dff, np.zeros(N - len(is_dff), bool)])

    src, dst = ei[0], ei[1]
    o = np.lexsort((dst, src))
    src, dst = src[o], dst[o]
    indptr = np.searchsorted(src, np.arange(N + 1))

    rep = {'definition': 'forward reachable from bound anchors, not crossing DFF',
           'views': {}, 'totals': {}}
    tot_anchor = tot_reach = tot_reach_unknown = tot_unknown = 0
    for k, v in enumerate(order):
        fam = v.split('__')[1]
        if fam.startswith('ctl'):
            continue
        m = vi == k
        anchors = np.flatnonzero(m & (y == 1))
        if not len(anchors):
            continue
        seen = np.zeros(N, bool)
        seen[anchors] = True
        stack = anchors.tolist()
        while stack:
            u = stack.pop()
            if is_dff[u]:
                continue
            for e in range(indptr[u], indptr[u + 1]):
                w = int(dst[e])
                if not seen[w]:
                    seen[w] = True
                    stack.append(w)
        unk = ~trust
        n_reach_unk = int(np.sum(seen & unk))
        rep['views'][v] = dict(anchors=int(len(anchors)), reached=int(seen.sum()),
                               reached_unknown=n_reach_unk,
                               view_unknown=int(np.sum(m & unk)))
        tot_anchor += len(anchors); tot_reach += int(seen.sum())
        tot_reach_unknown += n_reach_unk; tot_unknown += int(np.sum(m & unk))
    rep['totals'] = dict(anchors=tot_anchor, reached=tot_reach, reached_unknown=tot_reach_unknown,
                         injection_unknown=tot_unknown,
                         fraction_of_injection_unknown=round(tot_reach_unknown / max(1, tot_unknown), 4))
    (OUT / 'taint_probe.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(rep['totals'], ensure_ascii=False))


if __name__ == '__main__':
    main()
