"""Summarise round-3 recovery: definite rates, statuses, per design/kind."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
TAB = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"


def main() -> int:
    r = pd.read_csv(TAB / "r3_recovery_relations.csv", encoding="utf-8-sig")
    q = pd.read_csv(TAB / "r3_recovery_queries.csv", encoding="utf-8-sig")
    print("relations", len(r), "queries", len(q))
    print("\nquery statuses:\n", q.status.value_counts().to_string())
    print("\nfunctional_sufficiency:\n", r.functional_sufficiency.value_counts().to_string())
    print("\nquery_status strings:\n", r.query_status.value_counts().to_string())
    print("\nby design/kind:\n", r.groupby(["purpose", "kind", "query_status"]).size().to_string())
    print("\nreplayed vs saved:\n",
          pd.crosstab(r.replayed, r.saved.astype(str)).to_string())
    print("\nforcing patterns:\n", r.forcing_patterns.value_counts().to_string())
    print("\ninfluence:\n", r.influence_status.value_counts().to_string())
    print("\ncut sizes:\n", r.cut_size.value_counts().to_string())
    # definite rate per design
    r["n_def"] = r.query_status.str.extract(r"proved=(\d+)").astype(int) + \
        r.query_status.str.extract(r"refuted=(\d+)").astype(int)
    print("\ndefinite values per relation:\n", r.n_def.value_counts().sort_index().to_string())
    print("\nrelations with >=1 definite:",
          int((r.n_def > 0).sum()), "/", len(r))
    print("\nper design definite rate:\n",
          r.groupby("design").agg(relations=("n_def", "size"), definite=("n_def", "sum"),
                                  zero=("n_def", lambda x: int((x == 0).sum()))).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
