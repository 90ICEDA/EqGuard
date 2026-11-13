"""Append round-15 repro rows without changing old entries."""
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
BAK = P.with_name("index.csv.bak_20261025_r15")
T = "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round15/"
ROWS = [
    ("table", "satmap_r15_contract", T + "signal_contract_manifest.json",
     "110 coords; 89 valid nodes train71/val18; 8 PI; 6 Q/QN groups; target22 train18/val4"),
    ("table", "satmap_r15_coords", T + "signal_coordinates.csv",
     "per-coordinate view/raw hash/net/bit/driver/pin/QN polarity/PI/shared node"),
    ("table", "satmap_r15_target18", T + "target18_manifest.json",
     "target-only 18+covered; 22 support; real vs perm changed 6 nodes/12 cols; val unchanged"),
    ("table", "satmap_r15_groups", T + "group_manifest.json",
     "structure 39 and three 58-dim arms; same mask/support; parameter-matched comparison"),
    ("table", "satmap_r15_preflight", T + "preflight_report.json",
     "24/24 tensor checks; 5/5 negative rejections; no training initialized"),
    ("table", "satmap_r15_plan", T + "experiment_plan.json",
     "4 frozen arms, seed42, LRO ys_aig, 30 epochs, input hashes; not executed"),
    ("table", "satmap_r15_cumulative", T + "pair_coverage_40_round15.csv",
     "40 rows: 11 paired/29 blocked; 11 target-only contract; 2 region reaudit"),
    ("table", "satmap_r15_report", "10.15/00_说明/SAT第十五轮_信号坐标合同与最小特征预检_20261025o.md",
     "round15 coordinate contract, target-only features and preflight; no training"),
    ("table", "satmap_r15_scripts", "_p0pilot/round15_20261025",
     "contract/target features/groups/preflight/plan; no SAT/training"),
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