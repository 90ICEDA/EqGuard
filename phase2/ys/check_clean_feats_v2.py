"""check_clean_feats_v2.py -- validate the p0clean2 matrix."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import numpy as np

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"
TAG = "_p0clean2"

F = np.load(PT / f"satrel_node_feats_sat{TAG}.npy")
FF = np.load(PT / f"satrel_node_feats_sat_full{TAG}.npy")
M = np.load(PT / f"satrel_node_mask_sat{TAG}.npy")
meta = json.loads((PT / f"satrel_node_meta_sat{TAG}.json").read_text(encoding="utf-8"))
fid = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))["file_ids"]
names = meta["core_names"]

print("core", F.shape, F.dtype, "finite", bool(np.isfinite(F).all()))
print("full", FF.shape, FF.dtype, "finite", bool(np.isfinite(FF).all()))
print("mask", M.shape, "layers", [int(M[:, i].sum()) for i in range(3)])
for i, nm in enumerate(names):
    col = F[:, i]
    print(f"  [{i:2d}] {nm:16s} nz={int((col != 0).sum()):8d} "
          f"min={float(col.min()):.4g} max={float(col.max()):.4g} "
          f"mean={float(col.mean()):.6g}")

covered = (M.max(1) > 0).astype(np.float32)
print("covered_last_equals_mask", bool(np.array_equal(covered, F[:, -1])))
print("duplicate_core_columns", [(names[i], names[j]) for i in range(F.shape[1])
      for j in range(i + 1, F.shape[1]) if np.array_equal(F[:, i], F[:, j])])
print("fractions_0_1", {names[i]: bool((F[:, i] >= 0).all() and (F[:, i] <= 1).all())
      for i in [3, 4, 5, 6, 10, 11]})
print("binary_core", {names[i]: sorted(set(np.unique(F[:, i]).tolist()))
      for i in [0, 1, 2, 11]})
print("observable_nonzero_meta", meta.get("observable_nonzero"))
print("status_counts", meta.get("p0_status_counts"))
print("p0_rows", meta.get("p0_rows_used"), "apps", meta.get("p0_row_view_applications"))
print("S/P/trojan", meta.get("coverage_by_layer"), meta.get("S_covered_of_trojan_named"),
      meta.get("P_covered_of_trojan_named"), "trojan_total", meta.get("trojan_named_nodes"))
print("core", names)
print("full", meta.get("full_names"))
