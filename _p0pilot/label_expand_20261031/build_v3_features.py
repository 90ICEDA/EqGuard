"""P1: sentinel-safe feature matrix (v3, additive) + train-only normalization.

- v2 keeps -1 as "unreachable" in distance columns 30/33/34; z-scoring that mixes
  "unreachable" with "distance ~0". v3 adds explicit reachability masks and sets
  unreachable distances to 0 after standardization.
- Gate columns (0..24) stay raw; structural columns (25..38) are z-scored with
  train-physical-only statistics computed on reachable rows, clipped to +/-10.

Output: features42_v3.npy (39 normalized + 3 masks), norm_v3.npz, p1_report.json
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
FOLD = ROOT / 'generate_trans/folds/hosts_bt31'
V2 = FOLD / 'data/derived_v2/bitwise_alias_20261029_v2'
FROZEN = ROOT / '_p0pilot/round29_20261029/frozen'

MASK_COLS = (30, 33, 34)


def main():
    vi = np.load(FROZEN / 'view_index_all.npy')
    comp = json.loads((V2 / 'COMPLETE.json').read_text(encoding='utf-8'))
    virt_base = len(vi)
    n = comp['total_graph_nodes']
    fx = np.load(V2 / 'features39_v2.npy', mmap_mode='r')
    fv = np.load(V2 / 'virtual_features39_v2.npy', mmap_mode='r')

    train_views = len(json.loads((FOLD / 'views.json').read_text(encoding='utf-8'))['train_views'])
    train_idx = np.flatnonzero((vi >= 0) & (vi < train_views))

    # pass 1: train-only stats on reachable rows for structural columns
    s = np.zeros(39, np.float64); ss = np.zeros(39, np.float64); cnt = np.zeros(39, np.int64)
    masks_sum = {c: 0 for c in MASK_COLS}
    for st in range(0, len(train_idx), 200000):
        idx = train_idx[st:st + 200000]
        a = np.asarray(fx[idx], np.float64)
        for c in range(25, 39):
            v = a[:, c]
            ok = v != -1
            vv = v[ok]
            s[c] += vv.sum(); ss[c] += (vv * vv).sum(); cnt[c] += len(vv)
    mean = np.zeros(39); std = np.ones(39)
    for c in range(25, 39):
        mean[c] = s[c] / cnt[c]
        std[c] = max(np.sqrt(max(ss[c] / cnt[c] - mean[c] ** 2, 0)), 1e-6)

    # pass 2: write v3
    out = np.lib.format.open_memmap(OUT / 'features42_v3.npy', mode='w+', dtype=np.float32, shape=(n, 42))
    for st in range(0, n, 250000):
        en = min(n, st + 250000)
        block = np.empty((en - st, 39), np.float32)
        if en <= virt_base:
            block[:] = fx[st:en]
        elif st >= virt_base:
            block[:] = fv[st - virt_base:en - virt_base]
        else:
            cut = virt_base - st
            block[:cut] = fx[st:virt_base]
            block[cut:] = fv[0:en - virt_base]
        o = block.copy()
        for c in range(25, 39):
            v = o[:, c]
            ok = v != -1
            z = (v.astype(np.float32) - mean[c]) / std[c]
            z = np.clip(z, -10, 10)
            if c in MASK_COLS:
                z[~ok] = 0.0
            o[:, c] = z
        out[st:en, :39] = o
        for j, c in enumerate(MASK_COLS):
            out[st:en, 39 + j] = (block[:, c] != -1).astype(np.float32)
    out.flush()
    np.savez(OUT / 'norm_v3.npz', mean=mean.astype(np.float32), std=std.astype(np.float32),
             fit_count=np.int64(len(train_idx)), mask_cols=np.array(MASK_COLS),
             note='structural cols 25..38 z-scored on train physical reachable rows; gate cols raw')
    rep = dict(rows=int(n), cols=42, mask_cols=list(MASK_COLS),
               sentinel_fraction={str(c): round(float(np.mean(np.asarray(fx[:, c]) == -1)), 5) for c in MASK_COLS},
               mean={str(c): round(float(mean[c]), 3) for c in range(25, 39)},
               std={str(c): round(float(std[c]), 3) for c in range(25, 39)},
               output=str((OUT / 'features42_v3.npy').relative_to(ROOT)),
               note='unreachable distance -> 0 after z-score, mask column = 1 when reachable')
    (OUT / 'p1_report.json').write_text(json.dumps(rep, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
