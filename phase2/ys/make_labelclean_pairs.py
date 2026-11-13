"""make_labelclean_pairs.py -- repair D/E node pairs with labels + train mask.

Input : satrel_node_pairs.npz  (a, b, kind)
Graph : trans_graph.pt         (y, train_mask)
Output: satrel_node_pairs_labelclean.npz + meta

kind0 consistency:
  both endpoints train, y[a] == y[b]
kind1 pair_trojan:
  both endpoints train, y[a] == 1, y[b] == 0
  (NOT the old "a4trojan instance" heuristic)
kind2 is dropped (not used by D/E).

E is only considered ready when kind1 has at least --min-kind1 pairs.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
from pathlib import Path

import numpy as np
import torch

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt-dir", type=Path, default=PT)
    ap.add_argument("--in-npz", default="satrel_node_pairs.npz")
    ap.add_argument("--out-npz", default="satrel_node_pairs_labelclean.npz")
    ap.add_argument("--graph", default="trans_graph.pt")
    ap.add_argument("--min-kind1", type=int, default=1000)
    ap.add_argument("--include-nontrain", action="store_true")
    a = ap.parse_args()

    z = np.load(a.pt_dir / a.in_npz)
    A, B, K = z["a"], z["b"], z["kind"]
    d = torch.load(a.pt_dir / a.graph, map_location="cpu",
                   weights_only=False, mmap=True)
    y = np.asarray(d.y).astype(np.int8)
    tm = np.asarray(d.train_mask).astype(bool)
    del d

    def train_ok(x, yidx):
        return tm[x] if not a.include_nontrain else np.ones(len(x), bool)

    m0 = (K == 0) & train_ok(A, None) & train_ok(B, None) & (y[A] == y[B])
    m1 = ((K == 1) & train_ok(A, None) & train_ok(B, None)
          & (y[A] == 1) & (y[B] == 0))
    keep = m0 | m1
    A2, B2, K2 = A[keep], B[keep], K[keep]

    np.savez_compressed(a.pt_dir / a.out_npz, a=A2, b=B2, kind=K2)
    n0 = int((K2 == 0).sum())
    n1 = int((K2 == 1).sum())
    pos0 = int(((K2 == 0) & (y[A2] == 1)).sum())
    meta = {
        "source": str(a.pt_dir / a.in_npz),
        "graph": str(a.pt_dir / a.graph),
        "include_nontrain": bool(a.include_nontrain),
        "n_in": int(len(K)),
        "n_out": int(len(K2)),
        "by_kind": {"0": n0, "1": n1},
        "kind0": {"same_label": True, "positive_positive": pos0,
                  "negative_negative": int(n0 - pos0)},
        "kind1": {"a_pos": int(n1), "b_neg": int(n1),
                  "label_conditioned": True},
        "e_ready": bool(n1 >= int(a.min_kind1)),
        "min_kind1": int(a.min_kind1),
        "note": ("kind1 is now y[a]==1 and y[b]==0, not an instance-name "
                 "heuristic; E should be skipped when e_ready is false"),
    }
    (a.pt_dir / "satrel_node_pairs_labelclean_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
