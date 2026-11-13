"""analyze_clean_dims.py -- redundancy / usefulness diagnostics for p0clean."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
F = np.load(PT / "satrel_node_feats_sat_p0clean.npy")
names = ["is_target", "is_cut", "is_cell", "decided", "influence",
         "observable", "P1_logcnt", "P1_ratio", "covered"]

print("=== exact column equality ===")
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        if np.array_equal(F[:, i], F[:, j]):
            print(f"  {names[i]} == {names[j]}")

for i, nm in enumerate(names):
    print(nm, "unique", np.unique(F[:, i]).tolist()[:12],
          "n_unique", int(len(np.unique(F[:, i]))))

a = F[:, 0] > 0
c = F[:, 2] > 0
b = F[:, 1] > 0
print("target/cell n", int(a.sum()), int(c.sum()),
      "overlap", int((a & c).sum()), "jaccard", round(float((a & c).sum() / max((a | c).sum(), 1)), 4))
print("target/cut overlap", int((a & b).sum()), "cell/cut overlap", int((b & c).sum()))
print("P1 corr", round(float(np.corrcoef(F[:, 6], F[:, 7])[0, 1]), 4))
print("P1_logcnt quantiles", np.quantile(F[F[:, 6] > 0, 6], [0, .25, .5, .75, 1]).round(4).tolist())
print("P1_ratio quantiles", np.quantile(F[F[:, 7] > 0, 7], [0, .25, .5, .75, 1]).round(4).tolist())

p0 = pd.read_csv(ROOT / "_p0pilot/functional_relations_agnostic.csv", encoding="utf-8-sig").fillna("")
p0["obs"] = ((pd.to_numeric(p0["n_po_reached"], errors="coerce").fillna(0) > 0) |
             (pd.to_numeric(p0["n_dff_reached"], errors="coerce").fillna(0) > 0))
p0["tro"] = p0["target"].astype(str).str.contains("trojan", case=False)
print("\n=== raw P0 observable distribution ===")
print(p0.groupby(["kind", "status"]).agg(n=("obs", "size"), obs=("obs", "mean"),
                                         decided=("decided", "mean"),
                                         influence=("influence", "mean")).round(3).to_string())
print("\nproved target Trojan vs obs")
print(p0[p0.status == "proved"].groupby("tro").agg(n=("obs", "size"), obs=("obs", "mean")).round(3).to_string())
print("\nproved kind counts")
print(p0[p0.status == "proved"].groupby("kind").size().to_string())
