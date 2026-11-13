
# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path
import csv
from pathlib import Path

p = Path(_eqguard_path('10.15/99_共用资产/repro/index.csv'))
rows = [
    ("table", "satmap_r2_baseline",
     "10.15/06_统一评测协议/N4_三向泛化/tables/sat_map_round2/baseline_manifest.json", "", "",
     "train/val/test baseline; 259/65/64 views; masks 1250510/937552/1029013; no training"),
    ("table", "satmap_r2_funnel",
     "10.15/06_统一评测协议/N4_三向泛化/tables/sat_map_round2/mapping_funnel_rows.csv", "", "",
     "3295 definite cone/DFF rows; all single-bit single-driver; 0 name miss"),
    ("table", "satmap_r2_dedup",
     "10.15/06_统一评测协议/N4_三向泛化/tables/sat_map_round2/evidence_dedup_by_group.csv", "", "",
     "3295 relations -> 106 net names; 4809 mapped nodes in 290 views"),
    ("table", "satmap_r2_replay_accepted",
     "_p0pilot/round2_20261025/extraction/replay_accepted_rs232t1000_ctlmatcha_ys_abc.csv",
     "", "", "4 cases; 16/16 query agreement with saved statuses"),
    ("table", "satmap_r2_replay_recovery",
     "_p0pilot/round2_20261025/extraction/replay_recovery_s38417t100_ctlmatcha_ys_id.csv",
     "", "", "8 cases; 32/32 definite after proc -noopt (saved was all unknown)"),
    ("table", "satmap_r2_graded",
     "_p0pilot/round2_20261025/extraction/graded_graded_main.csv", "", "",
     "12 targets; 24 nodes; 144 queries; 38.1s; train/val only"),
    ("table", "satmap_r2_graded_ysid",
     "_p0pilot/round2_20261025/extraction/graded_graded_val_ysid.csv", "", "",
     "3 targets; 6 val nodes; 40 queries; 18.5s; recovery design"),
    ("table", "satmap_r2_report",
     "10.15/00_说明/SAT覆盖与映射审计_20261025b.md", "", "",
     "round-2 report; gate not passed; no training"),
    ("table", "satmap_r2_scripts", "_p0pilot/round2_20261025", "", "",
     "new audit/extract/replay/eval scripts; CPU only; old scripts untouched"),
]
with p.open("a", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    for r in rows:
        w.writerow(r)
print("appended", len(rows))
print("total lines", sum(1 for _ in p.open(encoding="utf-8-sig")))
for line in p.read_text(encoding="utf-8-sig").splitlines()[-3:]:
    print(line)
