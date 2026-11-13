"""Append round-6 repro rows without touching earlier rows."""
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
BAK = P.with_name("index.csv.bak_20261025_r6")
T = "10.15/06_统一评测协议/N4_三向泛化/tables/sat_expand_round6/"
ROWS = [
    ("table", "satmap_r6_corrections", T + "r6_r5_corrected_relations.csv",
     "5 mis-encoded constants corrected to partial_forced; 6 partial + 1 complete + 1 domain-restricted"),
    ("table", "satmap_r6_plan", T + "r6_candidate_plan.json",
     "16 deep cuts, k=4, 8 designs, train 12/val 4; real timestamp + plan hash"),
    ("table", "satmap_r6_plan_binding", T + "r6_plan_binding.json",
     "plan sha recheck ok; 512 expansion + 24 review; unique execution ids"),
    ("table", "satmap_r6_nonlocal", T + "r6_nonlocal_relations.csv",
     "512 queries; 4 proved / 12 not_proved; qid 16/16; review 24/24"),
    ("table", "satmap_r6_coverage", T + "r6_coverage.csv",
     "31 nodes; net new 28 vs cum4+5; direct positive 0; val 1/2-hop increment 0"),
    ("table", "satmap_r6_propagation", T + "r6_propagation_edges.csv",
     "20 new fixed-cut conditional edges; 98 blocked; total 35 edges with r5"),
    ("table", "satmap_r6_features", "_p0pilot/round6_20261025/features/r6_extra_real.npy",
     "3220146x25 bounded; last=covered; 39+25=64; permutation train 30/val 14"),
    ("table", "satmap_r6_feature_groups", T + "r6_feature_diff_groups.csv",
     "per-group permutation impact: determinism/feasibility/influence; structure 0"),
    ("table", "satmap_r6_feature_load", T + "r6_feature_load_check.json",
     "bounded [0,1]; 24 normalized + covered; 47 support rows; 63/64 dims"),
    ("table", "satmap_r5_corrected_features",
     "_p0pilot/round6_20261025/features/r5_extra_corrected_real.npy",
     "round5-only 25-col corrected rebuild; 16 support; old 20-col array superseded"),
    ("table", "satmap_r5_corrected_diff", T + "r5_feature_diff_corrected.json",
     "round5 corrected permutation: 11 train / 0 val changed; 2 single-relation val designs"),
    ("table", "satmap_r6_review", T + "r6_review.csv",
     "24 independent re-runs; 24/24 status agreement"),
    ("table", "satmap_r6_legacy_hash", T + "r6_legacy_hash_audit.csv",
     "348 rows; raw mismatch 348; normalized text match 182; no overwrite claim"),
    ("table", "satmap_r6_report", "10.15/00_说明/SAT第六轮_编码修正与扩覆盖_20261025f.md",
     "round6 report; gate not passed; no training"),
    ("table", "satmap_r6_scripts", "_p0pilot/round6_20261025",
     "truth-class fix + frozen expansion + coverage/permutation/hash audit; CPU only"),
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