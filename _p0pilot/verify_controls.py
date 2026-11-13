"""verify_controls.py -- confirm shuffle6 / verdict_perm are valid permutation controls.

For each control vs `safe`:
  * counts columns (0..3 of the 6-block) byte-identical?
  * value multiset preserved per view? (sum & sorted-hash per view)
  * per-node values actually changed for the intended subset?
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import numpy as np

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"


def load(name: str):
    return np.load(PT / f"satrel_node_feats_sat_p0clean4_{name}.npy", mmap_mode="r")


def view_ids() -> np.ndarray:
    meta = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
    fid = meta["file_ids"]
    lookup: dict[str, int] = {}
    vid = np.zeros(len(fid), np.int16)
    for i, v in enumerate(fid):
        j = lookup.get(v)
        if j is None:
            j = len(lookup)
            lookup[v] = j
        vid[i] = j
    return vid, len(lookup)


def main() -> int:
    safe = load("safe")
    vid, nv = view_ids()
    cols = {"n_gate": 7, "n_mux": 8, "n_cone": 9, "n_dff": 10, "verdict1": 11, "verdict2": 12}
    ref = {k: np.asarray(safe[:, j]) for k, j in cols.items()}

    for name in ("shuffle6", "verdict_perm"):
        x = load(name)
        print(f"\n=== {name} vs safe ===")
        for k, j in cols.items():
            col = np.asarray(x[:, j])
            same = np.array_equal(ref[k], col)
            diff = int((ref[k] != col).sum())
            print(f"  {k:9s} identical={same} changed_nodes={diff}")
        # multiset check per view on the 6-column block
        blk_s = np.asarray(safe[:, 7:13]).astype(np.float32)
        blk_c = np.asarray(x[:, 7:13]).astype(np.float32)
        bad = 0
        for v in range(nv):
            idx = np.flatnonzero(vid == v)
            if idx.size == 0:
                continue
            if not np.array_equal(np.sort(blk_s[idx].ravel()), np.sort(blk_c[idx].ravel())):
                bad += 1
        print(f"  per-view multiset of 6-col block: {'OK' if bad == 0 else f'{bad} views differ'}")
        # support (nonzero mask of verdict cols) preserved?
        sup_s = (blk_s[:, 4] != 0) | (blk_s[:, 5] != 0)
        sup_c = (blk_c[:, 4] != 0) | (blk_c[:, 5] != 0)
        print(f"  verdict support size: safe={int(sup_s.sum())} {name}={int(sup_c.sum())}")
        # how many nodes with a case changed verdict value
        has_case = (blk_s[:, :4].sum(1) > 0)
        mov = int(((blk_s[:, 4] != blk_c[:, 4]) & has_case).sum())
        print(f"  case nodes={int(has_case.sum())} verdict1 moved on {mov}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
