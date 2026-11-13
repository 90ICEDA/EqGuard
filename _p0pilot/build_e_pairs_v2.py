"""build_e_pairs_v2.py -- label-conditioned kind1: y[a]=1, y[b]=0, same view + hard negatives."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import numpy as np
import torch

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"
SRC = PT / "satrel_node_pairs_labelclean.npz"
OUT = PT / "satrel_node_pairs_labelclean_v2.npz"
META = PT / "satrel_node_pairs_labelclean_v2_meta.json"
K = 10


def main() -> int:
    d = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = d.y.numpy().astype(int)
    x = d.x.float().numpy()
    fid = np.asarray(json.load(open(WORK / "data/for_train/metadata_trans.json",
                                    encoding="utf-8"))["file_ids"])
    z = np.load(SRC)
    a0, b0, k0 = z["a"], z["b"], z["kind"]
    keep0 = k0 == 0
    old1 = k0 == 1
    a_old, b_old = a0[old1], b0[old1]
    pos_pos = {(int(a0[i]), int(b0[i])) for i in np.where(keep0 & (y[a0] == 1) & (y[b0] == 1))[0]}
    gid = np.argmax(x[:, : min(25, x.shape[1])], axis=1)
    rng = np.random.default_rng(20261024)
    new_a, new_b = [], []
    for v in sorted(set(fid[y == 1])):
        idx = np.where(fid == v)[0]
        pos = idx[y[idx] == 1]
        neg = idx[y[idx] == 0]
        if len(pos) == 0 or len(neg) == 0:
            continue
        for p in pos:
            cand = neg[gid[neg] == gid[p]]
            if len(cand) < K:
                cand = neg
            if len(cand) > K:
                # hard: nearest in the 39-d base feature space
                diff = x[cand] - x[p]
                dist = np.einsum("ij,ij->i", diff, diff)
                cand = cand[np.argsort(dist)[:K]]
            for q in cand:
                q = int(q)
                if (int(p), q) in pos_pos or (q, int(p)) in pos_pos:
                    continue
                new_a.append(int(p)); new_b.append(q)
    # de-duplicate, keep old valid kind1 too
    pairs = set(zip(new_a, new_b))
    pairs |= set(zip(a_old.tolist(), b_old.tolist()))
    pairs = [(a, b) for a, b in sorted(pairs) if y[a] == 1 and y[b] == 0]
    na = np.asarray([p[0] for p in pairs], np.int32)
    nb = np.asarray([p[1] for p in pairs], np.int32)
    kind = np.ones(len(na), np.int8)
    # merge kind0 and new kind1
    aa = np.concatenate([a0[keep0], na]).astype(np.int32)
    bb = np.concatenate([b0[keep0], nb]).astype(np.int32)
    kk = np.concatenate([np.zeros(int(keep0.sum()), np.int8), kind]).astype(np.int8)
    np.savez_compressed(OUT, a=aa, b=bb, kind=kk)
    meta = dict(source=str(SRC), n_in=int(len(a0)), n_out=int(len(aa)),
                kind0=int(keep0.sum()), kind1=int(len(na)),
                a_pos=int((y[na] == 1).sum()) if len(na) else 0,
                b_neg=int((y[nb] == 0).sum()) if len(nb) else 0,
                same_label=0, hard_negative=True, same_view=True,
                min_kind1=1000, e_ready=bool(len(na) >= 1000),
                note="kind1 = y[a]=1 and y[b]=0; same view; same gate type if possible; nearest 10 in base features")
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[out] {OUT} kind0={int(keep0.sum())} kind1={len(na)} e_ready={meta['e_ready']}")
    print(f"[out] {META}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
