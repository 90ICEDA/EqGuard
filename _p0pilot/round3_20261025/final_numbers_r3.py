"""Final round-3 numbers: witnesses, graded statuses, PO targets, mapping."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
R3 = ROOT / "_p0pilot/round3_20261025"
TAB = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"


def main() -> int:
    for src in ("recovery", "graded"):
        q = pd.read_csv(TAB / f"r3_{src}_queries.csv", encoding="utf-8-sig")
        print(src, "queries", len(q), "statuses", q.status.value_counts().to_dict())
        print("  witness non-empty", int((q.witness.astype(str).str.len() > 0).sum()))
        print("  witness sample", str(q.witness.iloc[0])[:160])
    g = pd.read_csv(TAB / "r3_graded_relations.csv", encoding="utf-8-sig")
    print("\ngraded relations:\n",
          g[["design", "kind", "target", "cut_nets", "cut_leaf_total", "cut_truncated",
             "cut_structure", "functional_sufficiency", "n_feasible", "n_forced",
             "determinism_ratio", "influence_status", "influence_mean",
             "reach_po", "reach_dff"]].to_string(index=False))
    print("\ngraded query_status:\n", g.query_status.value_counts().to_string())
    print("\ngraded attempts:\n",
          pd.read_csv(TAB / "r3_graded_attempts.csv", encoding="utf-8-sig").to_string(index=False))
    dumps = list((R3 / "witness").rglob("*.json"))
    print("\nmodel dumps", len(dumps), "bytes", sum(p.stat().st_size for p in dumps))
    cnfs = list((R3 / "cnf").rglob("*.cnf"))
    print("cnf", len(cnfs), "bytes", sum(p.stat().st_size for p in cnfs))
    mp = pd.concat([pd.read_csv(TAB / "r3_recovery_mapping_by_view.csv", encoding="utf-8-sig"),
                    pd.read_csv(TAB / "r3_graded_mapping_by_view.csv", encoding="utf-8-sig")])
    print("\nmapping rows", len(mp), "all mapped", int((mp.missing == 0).sum()),
          "views", mp.view.nunique(), "missing names", int(mp.missing.sum()))
    print(mp[mp.missing > 0].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
