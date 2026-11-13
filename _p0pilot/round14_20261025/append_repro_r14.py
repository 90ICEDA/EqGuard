"""Append round-14 repro rows without changing old entries."""
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
BAK = P.with_name("index.csv.bak_20261025_r14")
T = "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round14/"
ROWS = [
    ("table", "satmap_r14_stats", T + "corrected_training_stats.json",
     "89 valid nodes train71/val18; 96 relation-side dedup; 8 PI anchors; L1 median 1.21875"),
    ("table", "satmap_r14_attachments", T + "attachment_validation.csv",
     "view/driver/index validation; -1 PI separated; no unmapped"),
    ("table", "satmap_r14_l1", T + "pair_l1_distances.csv",
     "per-row nearest L1 min0/median1.21875/max3.75; descriptive only"),
    ("table", "satmap_r14_region", T + "region_anchor_diagnosis.json",
     "depth4: ctlmatchb source 5 DFF, partner 4 truncated; no common proven anchor"),
    ("table", "satmap_r14_contract", T + "pair_sample_manifest.json",
     "11 relation-boundary samples; A/B claims separated; no safety labels"),
    ("table", "satmap_r14_adapter", "_p0pilot/round14_20261025/sample_adapter.py",
     "read-only loader: 11 records, 9 train/2 val, training_allowed 0"),
    ("table", "satmap_r14_dryrun", T + "dry_run_report.json",
     "15/15 checks; 11x18 finite/bounded; train/val disjoint; no training"),
    ("table", "satmap_r14_info", T + "info_increment.json",
     "9 unique 18-d descriptions; 89 nodes/80 structural vectors; no predictive gain"),
    ("table", "satmap_r14_cumulative", T + "pair_coverage_40_round14.csv",
     "40 rows: 11 paired/29 blocked; 11 contract+dryrun; 2 region reaudit"),
    ("table", "satmap_r14_report", "10.15/00_说明/SAT第十四轮_统计勘误与样本合同_20261025n.md",
     "round14 stats corrections, sample contract and dry-run; no training"),
    ("table", "satmap_r14_scripts", "_p0pilot/round14_20261025",
     "offline stats/region/contract/dry-run/info; no SAT"),
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