"""Append round-12 repro rows without touching old rows."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
P = ROOT / "10.15/99_共用资产/repro/index.csv"
BAK = P.with_name("index.csv.bak_20261025_r12")
T = "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round12/"
ROWS = [
    ("table", "satmap_r12_audit", T + "blocker_audit.json",
     "29 blockers, 145 slots; 10 absent, 103 same-base, 95 local, 36 legacy; no SAT"),
    ("table", "satmap_r12_transform", T + "transform_map_audit.csv",
     "transform node_alignment is original-cell only; no temporary-net/physical-Q coverage"),
    ("table", "satmap_r12_plan", T + "plan.json",
     "4 frozen blockers (2 val/2 train); local candidates only; real timestamp+hash"),
    ("table", "satmap_r12_queries", T + "queries.csv",
     "17 SAT subqueries; 5 proved partial slots; 12 refuted; binding 17/17"),
    ("table", "satmap_r12_prior_binding", T + "prior_log_binding.csv",
     "4 prior failed blockers: 8/8 boundary logs bound; pair2 advanced slot1->slot2"),
    ("table", "satmap_r12_outcomes", T + "outcomes.csv",
     "0 complete pairs; no full table or review because no 5/5 boundary"),
    ("table", "satmap_r12_cumulative", T + "pair_coverage_40_round12.csv",
     "40 rows unchanged: 11 paired / 29 blocked; 4 round12 attempted"),
    ("table", "satmap_r12_report", "10.15/00_说明/SAT第十二轮_映射阻塞与局部对应_20261025l.md",
     "round12 mapping audit and stop decision; no training"),
    ("table", "satmap_r12_scripts", "_p0pilot/round12_20261025",
     "offline blocker audit + frozen local mappings + bounded SAT + consolidation"),
]


def main() -> int:
    if not BAK.exists():
        shutil.copy2(P, BAK)
    d = pd.read_csv(P, encoding="utf-8-sig")
    add = pd.DataFrame([dict(kind=k, id=i, path=p, seed=None, config=None,
                             note=n) for k, i, p, n in ROWS])
    add = add[~add.id.isin(d.id)]
    out = pd.concat([d, add], ignore_index=True)
    out.to_csv(P, index=False, encoding="utf-8-sig")
    print(dict(before=len(d), added=len(add), after=len(out),
               backup=str(BAK), ids=add.id.tolist()), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())