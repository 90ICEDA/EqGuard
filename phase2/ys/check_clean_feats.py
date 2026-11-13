"""check_clean_feats.py -- validate the p0clean feature matrix."""
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
TAG = "_p0clean"

names = ["is_target", "is_cut", "is_cell", "decided", "influence",
         "observable", "P1_logcnt", "P1_ratio", "covered"]
F = np.load(PT / f"satrel_node_feats_sat{TAG}.npy")
M = np.load(PT / f"satrel_node_mask_sat{TAG}.npy")
meta = json.loads((PT / f"satrel_node_meta_sat{TAG}.json").read_text(encoding="utf-8"))
fid = json.loads((WORK / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))["file_ids"]

print("F", F.shape, F.dtype, "finite", bool(np.isfinite(F).all()), "M", M.shape)
for i, nm in enumerate(names):
    col = F[:, i]
    print(f"  [{i}] {nm:12s} nz={int((col != 0).sum()):8d} "
          f"min={float(col.min()):.4g} max={float(col.max()):.4g} mean={float(col.mean()):.6g}")
cov = (M.max(1) > 0).astype(np.float32)
print("covered_last_equals_mask", bool(np.array_equal(cov, F[:, -1])))
print("mask_layers", [int(M[:, i].sum()) for i in range(3)])
print("S_and_P_overlap", int(((M[:, 0] > 0) & (M[:, 1] > 0)).sum()))
print("P1_logcnt_in_0_1", bool((F[:, 6] >= 0).all() and (F[:, 6] <= 1).all()))
print("P1_ratio_in_0_1", bool((F[:, 7] >= 0).all() and (F[:, 7] <= 1).all()))
print("binary_dims_0_5", [sorted(set(np.unique(F[:, i]).tolist())) for i in range(6)])

# per-view sanity: S coverage should exist in many views, P1 should be broad
fid = np.asarray(fid, dtype=object)
s_views = set(fid[F[:, 0] > 0].tolist())
p_views = set(fid[F[:, 6] > 0].tolist())
print("views_total", len(set(fid.tolist())), "S_views", len(s_views), "P_views", len(p_views))
print("meta_coverage", meta.get("coverage_by_layer"), "S_trojan", meta.get("S_covered_of_trojan_named"))
print("meta_p0_rows", meta.get("p0_rows_used"), "meta_p0_view_apps", meta.get("p0_row_view_applications"))
