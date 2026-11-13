"""append_repro_20261024.py -- append current SAT/P3/P4 artifacts to repro/index.csv."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import csv
from pathlib import Path

ROOT = Path(_eqguard_path(''))
IDX = ROOT / "10.15/99_共用资产/repro/index.csv"
ROWS = [
    ("run", "fghtl_P3locoC5S42", r"results\hosts_bt31_seed42mode4_allb1_loco_fghtl_P3locoC5S42", "42", "56d=39+cone5+SAT", "56-dim LOCO; AP_T=0.1753"),
    ("run", "fghtl_P3lroC5S42", r"results\hosts_bt31_seed42mode4_allb1_lro_fghtl_P3lroC5S42", "42", "56d=39+cone5+SAT", "56-dim LRO, only ys_abc completed; summary partial"),
    ("run", "fghtl_CncleanV2R2", r"results\hosts_bt31_seed2mode4_allb1_fold_fghtl_CncleanV2R2", "2", "51d=39+12SAT", "P2 C_n seed2; C_n 3seed AP_T=0.1587"),
    ("table", "fg_htl_ablation_v2", r"10.15\06_统一评测协议\N4_三向泛化\tables\fg_htl_ablation_v2.csv", "", "", "A/B/C_n/D_n; E not run"),
    ("table", "FGHTL_stability_832_summary", r"10.15\06_统一评测协议\N4_三向泛化\tables\FGHTL_stability_832_summary.csv", "", "", "C_v2 vs C_v1 clean; 832 pairs"),
    ("table", "Q1_evidence", r"10.15\06_统一评测协议\N4_三向泛化\tables\Q1_evidence.csv", "", "", "LOCO/LRO/fold AP_T"),
    ("table", "Q3_a4_evidence", r"10.15\06_统一评测协议\N4_三向泛化\tables\Q3_a4_evidence.csv", "", "", "A4 legacy control"),
    ("table", "region_pairs_v3", r"10.15\06_统一评测协议\N4_三向泛化\tables\region_pairs_v3.csv", "", "", "483 regions; 1:1=405/N:1=56/1:N=22"),
    ("table", "region_role_status_v3", r"10.15\06_统一评测协议\N4_三向泛化\tables\region_role_status_v3.csv", "", "", "v3 region roles"),
    ("table", "P4_matching_risk_pairs", r"10.15\06_统一评测协议\N4_三向泛化\tables\P4_matching_risk_pairs.csv", "", "", "832 pairs; C v2/C v1 scores"),
    ("table", "SAT_stratified_AP_summary", r"10.15\06_统一评测协议\N4_三向泛化\tables\SAT_stratified_AP_summary.csv", "", "", "all/covered/S/P/unknown AP; C v2 vs C v1"),
    ("fig", "SAT_stratified_AP", r"10.15\07_论文图表\figs\SAT_stratified_AP.png", "", "", "coverage-stratified AP"),
    ("fig", "Q1_functional_gain", r"10.15\07_论文图表\figs\Q1_functional_gain.png", "", "", "Q1 three-panel"),
    ("fig", "Q3_a4_control", r"10.15\07_论文图表\figs\Q3_a4_control.png", "", "", "Q3 legacy A4"),
    ("fig", "P4_matching_risk", r"10.15\07_论文图表\figs\P4_matching_risk.png", "", "", "P4 1b matching+risk"),
    ("fig", "F7_region_correspondence_v2", r"10.15\07_论文图表\figs\F7_region_correspondence_v2.png", "", "", "F7 v3/v2"),
    ("fig", "F6_functional_relations_v2", r"10.15\07_论文图表\figs\F6_functional_relations_v2.png", "", "", "F6 v2 from agnostic P0"),
    ("fig", "F9_gnn_internals_v2", r"10.15\07_论文图表\figs\F9_gnn_internals_v2.png", "", "", "C v2 51d; zero-SAT ablation"),
    ("scores", "FGHTL_scores_C_v2", r"generate_trans\folds\hosts_bt31\data\processed\FGHTL_scores_C_v2.npy", "42", "51d", "per-node C v2 scores"),
    ("scores", "FGHTL_scores_C_v1_clean", r"generate_trans\folds\hosts_bt31\data\processed\FGHTL_scores_C_v1_clean.npy", "42", "48d", "per-node C v1 legacy scores"),
]


def main() -> int:
    with open(IDX, "r", encoding="utf-8-sig", newline="") as f:
        r = list(csv.DictReader(f))
    seen = {(x.get("kind"), x.get("id")) for x in r}
    add = []
    for kind, i, path, seed, cfg, note in ROWS:
        if (kind, i) in seen:
            continue
        if not (ROOT / path).exists():
            print(f"[skip missing] {path}")
            continue
        add.append(dict(kind=kind, id=i, path=path, seed=seed, config=cfg, note=note))
    if not add:
        print("[ok] nothing to append")
        return 0
    with open(IDX, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["kind", "id", "path", "seed", "config", "note"])
        w.writerows(add)
    print(f"[out] appended {len(add)} rows -> {IDX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
