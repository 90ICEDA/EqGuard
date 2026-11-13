"""Round-4 baseline diagnostics (no SAT): keys coverage, pattern dtype, cut inventory."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
R3 = ROOT / "_p0pilot/round3_20261025"
TAB = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"


def main() -> int:
    keys = set()
    for p in (R3 / "logs").glob("*.keys.json"):
        keys.update(json.loads(p.read_text(encoding="utf-8")).values())
    print("keys in sidecars", len(keys), flush=True)
    for name in ("r3_recovery_queries.csv", "r3_graded_queries.csv"):
        q = pd.read_csv(TAB / name, encoding="utf-8-sig")
        print(name, "rows", len(q), "pattern dtype", q.pattern.dtype,
              "unique keys", q.query_key.nunique(),
              "in sidecar", int(q.query_key.isin(keys).sum()),
              "cache-only", int((~q.query_key.isin(keys)).sum()), flush=True)
        print("  pattern values", q.pattern.value_counts().to_dict(), flush=True)
    rel = pd.read_csv(TAB / "r3_recovery_relations.csv", encoding="utf-8-sig")
    print("recovery cut sizes", rel.cut_size.value_counts().to_dict(), flush=True)
    two = rel[rel.cut_size == 2]
    print("two-input relations", len(two), "unique keys",
          pd.read_csv(TAB / "r3_recovery_queries.csv", encoding="utf-8-sig")
          .query_key.nunique(), flush=True)
    print(two[["design", "target", "cut_nets", "functional_sufficiency"]].to_string(index=False),
          flush=True)
    # rows with pattern "00"/"01" and their keys
    q = pd.read_csv(TAB / "r3_recovery_queries.csv", encoding="utf-8-sig",
                    dtype={"pattern": str})
    for pat in ("00", "01", "10", "11"):
        print(pat, int((q.pattern == pat).sum()), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
