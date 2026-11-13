"""p3_lro_diag.py -- 只读：LRO 同 seed 基线 vs Cv2，按 split 结合 SAT 覆盖/证明率。"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(_eqguard_path(''))
R = ROOT / "results"
N4 = R / "hosts_bt31_seed42mode4_allb1_lro_n4blros42"
CV = R / "hosts_bt31_seed42mode4_allb1_lro_fghtl_P3lroCv2s42"
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"


def ap_by_split(p: Path) -> pd.Series:
    d = pd.read_csv(p / "loco_summary.csv", encoding="utf-8-sig")
    m = (d["Type"].astype(str) == "TRANS") & d["View"].astype(str).str.contains("__inj")
    x = d[m].groupby(["Split", "View"])["AP_T"].mean()
    return x, d[m]


def main() -> int:
    a4, d4 = ap_by_split(N4)
    ac, dc = ap_by_split(CV)
    cmp = pd.concat([a4.rename("N4_seed42_100ep"), ac.rename("Cv2_seed42_100ep")], axis=1)
    cmp["delta"] = cmp["Cv2_seed42_100ep"] - cmp["N4_seed42_100ep"]
    by_split = cmp.groupby(level=0).agg(["count", "mean"])
    print("=== AP_T by split (24 inj views) ===")
    print(by_split.to_string())
    print(f"\noverall N4={a4.mean():.4f} Cv2={ac.mean():.4f} delta={ac.mean()-a4.mean():+.4f}")

    # SAT mask coverage by view
    mask = np.load(PT / "satrel_node_mask_sat_p0clean2.npy").astype(bool)
    fid = np.asarray(json.load(open(WORK / "data/for_train/metadata_trans.json",
                                    encoding="utf-8"))["file_ids"])
    views = sorted(set(dc["View"].astype(str)) | set(d4["View"].astype(str)))
    cov = {v: float(mask[fid == v].mean()) if (fid == v).any() else np.nan for v in views}
    rows = []
    for split in sorted(cmp.index.get_level_values(0).unique()):
        vs = [v for v in views if (dc["Split"].astype(str) == split).any()
              and v in set(dc[dc["Split"].astype(str) == split]["View"])]
        rows.append(dict(split=split, n_views=len(vs),
                         ap_n4=float(cmp.loc[split, "N4_seed42_100ep"].mean()),
                         ap_cv2=float(cmp.loc[split, "Cv2_seed42_100ep"].mean()),
                         delta=float(cmp.loc[split, "delta"].mean()),
                         sat_mask_cov_test=float(np.nanmean([cov[v] for v in vs])) if vs else np.nan))
    sat = pd.DataFrame(rows)

    # P0 proved rate by recipe
    p0 = pd.read_csv(ROOT / "_p0pilot/functional_relations_agnostic.csv", encoding="utf-8-sig").fillna("")
    p0["recipe"] = p0["top"].astype(str).str.split("__").str[-1]
    pr = p0.groupby("recipe").agg(rows=("status", "size"),
                                  proved=("status", lambda s: int((s == "proved").sum())))
    pr["proved_rate"] = pr["proved"] / pr["rows"].clip(lower=1)
    sat = sat.merge(pr.reset_index(), left_on="split", right_on="recipe", how="left")
    print("\n=== by split: AP vs SAT coverage / P0 proved ===")
    print(sat.to_string(index=False))
    out = ROOT / "_p0pilot/p3_lro_diag.csv"
    sat.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n[out] {out}")

    print("\n=== run_config diff ===")
    c4 = json.load(open(N4 / "run_config.json", encoding="utf-8"))
    cc = json.load(open(CV / "run_config.json", encoding="utf-8"))
    keys = sorted(set(c4) | set(cc))
    for k in keys:
        if c4.get(k) != cc.get(k):
            print(f"  {k}: N4={c4.get(k)!r}  Cv2={cc.get(k)!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
