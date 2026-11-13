"""Deduplication / information-content summary for the qualified evidence."""

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(_eqguard_path(''))
OUT = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_map_round2"
OLD = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sparse_sat_round1"


def main() -> int:
    ev = pd.read_csv(OLD / "conditional_evidence.csv", encoding="utf-8-sig")
    ev["host"] = ev.source.str.split("__").str[0]
    ev["inst"] = ev.source.str.split("__").str[1]
    ev["recipe"] = ev.source.str.split("__").str[-1].str.replace(".v", "", regex=False)
    rows = []
    for keys, g in ev.groupby(["host", "inst", "recipe", "kind"]):
        rows.append(dict(keys=keys, relations=len(g),
                         unique_targets=g.target.nunique(),
                         unique_drivers=g.driver.nunique(),
                         unique_target_driver=len(g[["target", "driver"]].drop_duplicates()),
                         max_multiplicity=g.groupby("target").size().max()))
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "evidence_dedup_by_group.csv", index=False, encoding="utf-8-sig")
    print(d.to_string(index=False), flush=True)
    print("\nTOTAL relations", len(ev),
          "unique (host,inst,recipe,kind,target)",
          len(ev[["host", "inst", "recipe", "kind", "target"]].drop_duplicates()),
          "unique (host,kind,target)", len(ev[["host", "kind", "target"]].drop_duplicates()),
          "unique target", ev.target.nunique(),
          "unique target+driver", len(ev[["target", "driver"]].drop_duplicates()), flush=True)
    print("\nmultiplicity histogram\n",
          ev.groupby(["host", "target"]).size().value_counts().sort_index().to_string(),
          flush=True)
    # which design rows are definite but belong to a rejected log?
    q = pd.read_csv(OLD / "log_qualification.csv", encoding="utf-8-sig")
    bad = set(q[~q.accepted.astype(bool)].log)
    ag = pd.read_csv(ROOT / "_p0pilot/functional_relations_agnostic.csv",
                     encoding="utf-8-sig").fillna("")
    ag = ag[ag.kind.isin(["cone", "dff_next"])]
    ag = ag[ag[["sat_q1", "sat_q2", "sat_q3", "sat_q4"]].isin(["proved", "refuted"]).all(axis=1)]
    ag["log_bad"] = ag.log.isin(bad)
    print("\ndefinite complex rows:", len(ag), "in rejected logs:", int(ag.log_bad.sum()),
          "in aligned logs:", int((~ag.log_bad).sum()), flush=True)
    print(ag.groupby(["log_bad", "kind"]).size().to_string(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
