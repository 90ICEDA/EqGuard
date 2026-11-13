"""Verify prior-round log binding for the four attempted blockers."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
T11 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round11"
T12 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round12"
IDS = [
    "r7|s38417t100__ctlmatchb_d1_s42__ys_abc.v|g24734",
    "r7|s38417t100__injalpha_d1_s42__ys_id.v|U6927.Q",
    "r5|rs232t1000__injzeta_d1_s42__ys_abc.v|U58.Y",
    "r6|rs232t1000__injzeta_d1_s42__ys_abc.v|U12.Y",
]


def main() -> int:
    out = pd.read_csv(T11 / "all_outcomes.csv", encoding="utf-8-sig")
    rows = []
    for rid in IDS:
        r = out[out.relation_id == rid].iloc[0]
        f = T11 / ("queries.csv" if int(r.batch_id) == 1
                   else f"queries_batch{int(r.batch_id)}.csv")
        q = pd.read_csv(f, encoding="utf-8-sig", dtype={"pattern": str})
        q = q[(q.pair_index == int(r.pair_index)) & (q.kind == "boundary_equivalence")
              & (q.get("batch_id", 1) == int(r.batch_id))]
        ok = 0
        for x in q.itertuples():
            d = ROOT / x.folder
            good = (hashlib.sha256((d / "model.v").read_bytes()).hexdigest() == x.model_sha
                    and hashlib.sha256((d / "run.log").read_bytes()).hexdigest() == x.log_sha)
            ok += int(good)
        rows.append(dict(relation_id=rid, batch=int(r.batch_id),
                         pair_index=int(r.pair_index), prior_status=r.status,
                         prior_failed_slot=r.failed_slot,
                         boundary_queries=len(q), binding_ok=ok))
    pd.DataFrame(rows).to_csv(T12 / "prior_log_binding.csv", index=False,
                              encoding="utf-8-sig")
    print(pd.DataFrame(rows).to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())