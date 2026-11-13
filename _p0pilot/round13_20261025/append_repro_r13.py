"""Append round-13 repro rows without changing old entries."""
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
BAK = P.with_name("index.csv.bak_20261025_r13b")
T = "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round13/"
ROWS = [
    ("table", "satmap_r13_dedup", T + "dedup_manifest.json",
     "17 exec/15 distinct; 2 alias groups; 4/5 proved historical; 1 new U58 slot1"),
    ("table", "satmap_r13_context", T + "dedup_context_binding.csv",
     "raw SHA256 and same context_id for 4 frozen source/partner pairs"),
    ("table", "satmap_r13_logs", T + "log_block_audit.csv",
     "29 folders batch/query log blocks exact; no new SAT"),
    ("table", "satmap_r13_replay", T + "replay_refutations.csv",
     "12 refuted witnesses independently replayed by iverilog/vvp 12/12"),
    ("table", "satmap_r13_regen", T + "model_regeneration.csv",
     "17/17 models regenerated from raw snapshots (normalized text hash)"),
    ("table", "satmap_r13_region", T + "region_feasibility.csv",
     "2 val boundaries size 5/4 and 6/3; no common anchor; 0 region SAT"),
    ("table", "satmap_r13_training", T + "training_value.json",
     "11 pairs train9/val2; 90 graph nodes; 9 unique 18-d descriptions; no loader"),
    ("table", "satmap_r13_cumulative", T + "pair_coverage_40_round13.csv",
     "40 rows: 11 paired / 29 blocked; 2 region feasibility checked; round13_new=0"),
    ("table", "satmap_r13_report", "10.15/00_说明/SAT第十三轮_证据去重与区域可行性_20261025m.md",
     "round13 evidence dedup and training-value report; no training"),
    ("table", "satmap_r13_scripts", "_p0pilot/round13_20261025",
     "dedup + log/model/replay + region feasibility + training value; no SAT"),
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