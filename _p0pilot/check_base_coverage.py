"""check_base_coverage.py -- do all p0clean4 variants share the same base/core coverage?

Checks
  1. row count & node order (same trans graph)
  2. the 7 functional-core columns are byte-identical across variants
  3. the `covered` mask column is byte-identical across variants
  4. p0clean4 core7 == p0clean3[:, :7] and p0clean3 == p0clean2 selected columns
  5. per-column non-zero fraction (= coverage) for each variant
Uses mmap so peak RAM stays small.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

from pathlib import Path

import numpy as np

PT = Path(_eqguard_path('generate_trans/folds/hosts_bt31/data/processed'))
VARIANTS = ["core_only", "verdict_only", "counts_only", "safe", "shuffle6",
            "verdict_perm", "struct", "control"]
CORE = ["n_rel_log", "frac_decided", "frac_influence", "frac_proved",
        "reach_po_log", "reach_dff_log", "p1_ratio"]


def load(name: str, tag: str = ""):
    p = PT / f"satrel_node_feats_sat_p0clean4{tag}_{name}.npy"
    return np.load(p, mmap_mode="r")


def nz(col: np.ndarray) -> float:
    return float((col != 0).mean())


def main() -> int:
    ref = load("safe")
    n = ref.shape[0]
    print(f"[ref] safe shape={ref.shape}")
    core_ref = [np.asarray(ref[:, j]) for j in range(7)]
    cov_ref = np.asarray(ref[:, ref.shape[1] - 1])

    print("\n[1] core7 identical across variants?")
    for v in VARIANTS:
        try:
            x = load(v)
        except FileNotFoundError:
            print(f"  {v:13s} MISSING")
            continue
        if x.shape[0] != n:
            print(f"  {v:13s} ROW MISMATCH {x.shape}")
            continue
        ok = all(np.array_equal(core_ref[j], np.asarray(x[:, j])) for j in range(7))
        c = np.asarray(x[:, x.shape[1] - 1])
        cov_ok = bool(np.array_equal(cov_ref, c))
        print(f"  {v:13s} dim={x.shape[1]:2d} core7={'OK' if ok else 'DIFF'} "
              f"covered={'OK' if cov_ok else 'DIFF'}")

    print("\n[2] p0clean4 core7 vs p0clean3[:7]")
    c3 = np.load(PT / "satrel_node_feats_sat_p0clean3.npy", mmap_mode="r")
    ok3 = all(np.array_equal(core_ref[j], np.asarray(c3[:, j])) for j in range(7))
    cov3 = np.array_equal(cov_ref, np.asarray(c3[:, 9]))
    print(f"  core7={'OK' if ok3 else 'DIFF'} covered={'OK' if cov3 else 'DIFF'}")

    print("\n[3] p0clean3 core7 vs p0clean2 selected columns")
    c2 = np.load(PT / "satrel_node_feats_sat_p0clean2.npy", mmap_mode="r")
    idx2 = [3, 4, 5, 6, 7, 8, 10]
    for j, k in enumerate(idx2):
        same = np.array_equal(core_ref[j], np.asarray(c2[:, k]))
        if not same:
            print(f"  core[{j}] {CORE[j]:16s} vs p0clean2[:,{k}] DIFF")
    print("  (未打印的列 = 完全一致)")
    print(f"  p0clean3 covered == p0clean2[:, -1]: "
          f"{bool(np.array_equal(np.asarray(c3[:, 9]), np.asarray(c2[:, -1])))}")

    print("\n[4] per-column non-zero fraction (coverage)")
    for v in ["core_only", "verdict_only", "counts_only", "safe", "shuffle6"]:
        x = load(v)
        ns = [round(nz(np.asarray(x[:, j])), 5) for j in range(x.shape[1] - 1)]
        print(f"  {v:12s} dim={x.shape[1]:2d} {ns}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
