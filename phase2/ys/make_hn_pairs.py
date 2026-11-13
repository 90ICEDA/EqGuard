"""make_hn_pairs.py -- add label-conditioned, view-matched hard negatives for E.

Input : satrel_node_pairs_labelclean.npz  (kind0 cleaned consistency)
Output: satrel_node_pairs_labelclean_hn.npz

kind1 (new pair_trojan):
  a = train positive node (y=1)
  b = train negative node (y=0) from the same view
  no SAT-equivalence requirement; this is a supervised hard-negative pair.

The old kind1 (a4trojan instance name) is NOT reused.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt-dir", type=Path, default=PT)
    ap.add_argument("--work", type=Path, default=WORK)
    ap.add_argument("--in-npz", default="satrel_node_pairs_labelclean.npz")
    ap.add_argument("--out-npz", default="satrel_node_pairs_labelclean_hn.npz")
    ap.add_argument("--graph", default="trans_graph.pt")
    ap.add_argument("--neg-per-pos", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-kind1", type=int, default=1000)
    a = ap.parse_args()

    z = np.load(a.pt_dir / a.in_npz)
    A0, B0, K0 = z["a"], z["b"], z["kind"]
    d = torch.load(a.pt_dir / a.graph, map_location="cpu",
                   weights_only=False, mmap=True)
    y = np.asarray(d.y).astype(np.int8)
    tm = np.asarray(d.train_mask).astype(bool)
    del d
    fid = json.loads((a.work / "data/for_train/metadata_trans.json")
                     .read_text(encoding="utf-8"))["file_ids"]

    pos = np.where(tm & (y == 1))[0]
    neg = np.where(tm & (y == 0))[0]
    by_view: dict[str, list[int]] = defaultdict(list)
    for i in neg:
        by_view[fid[i]].append(i)

    rng = np.random.default_rng(int(a.seed))
    A1, B1 = [], []
    for i in pos:
        cand = by_view.get(fid[i], [])
        if not cand:
            continue
        n = min(int(a.neg_per_pos), len(cand))
        if n <= 0:
            continue
        pick = rng.choice(np.asarray(cand), size=n, replace=False)
        for j in pick:
            A1.append(int(i))
            B1.append(int(j))

    A = np.concatenate([A0, np.asarray(A1, np.int32)])
    B = np.concatenate([B0, np.asarray(B1, np.int32)])
    K = np.concatenate([K0, np.ones(len(A1), np.int8)])
    np.savez_compressed(a.pt_dir / a.out_npz, a=A, b=B, kind=K)

    n1 = int(len(A1))
    meta = {
        "source": str(a.pt_dir / a.in_npz),
        "out": str(a.pt_dir / a.out_npz),
        "positive_train_nodes": int(len(pos)),
        "negative_train_nodes": int(len(neg)),
        "neg_per_pos": int(a.neg_per_pos),
        "same_view": True,
        "n_kind0": int((K == 0).sum()),
        "n_kind1": n1,
        "e_ready": bool(n1 >= int(a.min_kind1)),
        "min_kind1": int(a.min_kind1),
        "note": ("kind1 is a supervised positive-vs-negative pair from the same "
                 "train view; it is not a SAT-equivalence pair"),
    }
    (a.pt_dir / "satrel_node_pairs_labelclean_hn_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
