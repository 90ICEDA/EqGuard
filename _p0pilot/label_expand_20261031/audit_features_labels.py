"""Audit: v2 feature sanity, P2 normalized copy check, taint-rule safety on Trojan-named cells."""
import json, re
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
DATA = ROOT / 'generate_trans/folds/hosts_bt31/data/for_train'
FROZEN = ROOT / '_p0pilot/round29_20261029/frozen'
V2 = ROOT / 'generate_trans/folds/hosts_bt31/data/derived_v2/bitwise_alias_20261029_v2'
P2 = ROOT / '_p0pilot/round32_20261029/inputs/trans_train'


def closure(indptr, nbr, seeds, stop, N):
    seen = np.zeros(N, bool); seen[seeds] = True
    st = list(seeds)
    while st:
        u = st.pop()
        if stop[u]:
            continue
        for e in range(indptr[u], indptr[u + 1]):
            w = int(nbr[e])
            if not seen[w]:
                seen[w] = True; st.append(w)
    return seen


def main():
    rep = {}
    vi = np.load(FROZEN / 'view_index_all.npy')
    trust = np.load(DATA / 'trust_trans.npy')
    split = json.loads((ROOT / 'generate_trans/folds/hosts_bt31/views.json').read_text(encoding='utf-8'))
    order = split['train_views'] + split['val_views'] + split['test_views']
    fam = np.array([v.split('__')[1] for v in order])
    lab = json.loads((DATA / 'label_transport.json').read_text(encoding='utf-8'))['trans_labels_from_orig']
    keys = np.fromiter((int(k) for k in lab), np.int64, len(lab))
    vals = np.fromiter(lab.values(), np.int8, len(lab))
    y = np.full(len(vi), -1, np.int8); y[keys] = vals

    # ---- 1) v2 feature sanity ----
    v2 = np.load(V2 / 'features39_v2.npy', mmap_mode='r')
    idx = np.arange(0, len(v2), 331)[:400000]
    X = np.asarray(v2[idx], dtype=np.float64)
    gate = X[:, :25]
    onehot_ok = np.all(np.isclose(gate.sum(1), 1.0))
    zero_cols = [int(c) for c in range(39) if np.ptp(X[:, c]) == 0]
    sent = {str(c): round(float(np.mean(np.asarray(v2[:, c]) == -1)), 4) for c in (29, 30, 33, 34)}
    rep['v2'] = dict(rows=len(v2), nan=bool(np.isnan(X).any()), finite=bool(np.isfinite(X).all()),
                     gate_onehot_ok=bool(onehot_ok), constant_columns=zero_cols,
                     sentinel_minus1_fraction=sent,
                     col30_min=float(X[:, 30].min()), col30_max=float(X[:, 30].max()))

    # ---- 2) P2 x39 vs v2 (normalization check) ----
    x39 = np.load(P2 / 'x39.npy', mmap_mode='r')
    gidx = np.flatnonzero((vi >= 0) & (vi < len(split['train_views'])))
    assert len(x39) == len(gidx) + 154, (len(gidx), len(x39))
    sidx = np.arange(0, len(gidx), 331)[:4000]
    Vraw = np.asarray(v2[gidx[sidx]], dtype=np.float64)
    same_gate = bool(np.allclose(np.asarray(x39[sidx, :25]), Vraw[:, :25]))
    struct = np.asarray(x39[sidx, 25:], dtype=np.float64)
    raw = Vraw[:, 25:]
    # fit per-column affine on the sample and report residual + clipping presence
    A = np.c_[raw, np.ones(len(raw))]
    coef, *_ = np.linalg.lstsq(A, struct, rcond=None)
    resid = float(np.abs(A @ coef - struct).max())
    rep['p2_x39'] = dict(same_gate_columns=same_gate, struct_affine_max_residual=round(resid, 4),
                         struct_min=float(struct.min()), struct_max=float(struct.max()),
                         clipped_fraction=round(float(np.mean(np.abs(struct) >= 9.999)), 5))

    # ---- 3) taint rule safety: do Trojan-named trans cells fall outside A/B? ----
    ei = np.load(V2 / 'edge_index_directed_v2.npy')
    N = int(ei.max()) + 1
    name = [None] * len(vi)
    with (ROOT / 'generate_trans/folds/hosts_bt31/data/processed/node_names_trans.txt').open(encoding='utf-8', errors='replace') as f:
        for i, line in enumerate(f):
            if i < len(vi):
                name[i] = line.rstrip('\r\n')
    name = np.array([n or '' for n in name])
    feat = np.load(DATA / 'feats_trans.npy', mmap_mode='r')
    is_dff = np.zeros(len(vi), bool)
    for c in (4, 5, 6, 19, 20):
        is_dff |= np.asarray(feat[:, c]) > 0.5
    del feat
    is_dff = np.concatenate([is_dff, np.zeros(N - len(is_dff), bool)])
    viN = np.full(N, -1, vi.dtype); viN[:len(vi)] = vi
    yN = np.full(N, -1, np.int8); yN[:len(y)] = y
    trN = np.zeros(N, bool); trN[:len(trust)] = trust
    src, dst = ei[0], ei[1]
    o = np.lexsort((dst, src)); s2, d2 = src[o], dst[o]
    fi = np.searchsorted(s2, np.arange(N + 1))
    o2 = np.lexsort((src, dst)); rs, rd = dst[o2], src[o2]
    ri = np.searchsorted(rs, np.arange(N + 1))

    trojan_name = np.array([bool(re.search(r'trojan', n, re.I)) for n in name])
    trojan_name = np.concatenate([trojan_name, np.zeros(N - len(trojan_name), bool)])
    stat = dict(trojan_named=int(trojan_name.sum()), labelled_pos=int((y == 1).sum()),
                trojan_named_but_not_pos=int(np.sum(trojan_name[:len(y)] & (y != 1))),
                trojan_named_in_C=0, trojan_named_in_B=0, samples=[])
    for k, v in enumerate(order):
        if fam[k].startswith('ctl'):
            continue
        m = viN == k
        anchors = np.flatnonzero(m & (yN == 1))
        if not len(anchors):
            continue
        A = closure(fi, d2, anchors, is_dff, N)
        B = closure(ri, rd, anchors, is_dff, N)
        C = m & ~A & ~B
        tn = m & trojan_name
        stat['trojan_named_in_C'] += int(np.sum(tn & C))
        stat['trojan_named_in_B'] += int(np.sum(tn & B))
        if np.any(tn & C) and len(stat['samples']) < 5:
            stat['samples'] += [name[i] for i in np.flatnonzero(tn & C)[:3]]
    rep['taint_safety'] = stat
    (OUT / 'feature_label_audit.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
