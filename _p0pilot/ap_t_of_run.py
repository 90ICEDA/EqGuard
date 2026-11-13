"""ap_t_of_run.py -- AP_T (24 inj views) + 65-view AP for one or more run dirs.

Usage:
  python _p0pilot/ap_t_of_run.py results/<tag1> [results/<tag2> ...] [--csv-out tables/xxx.csv]

Notes
  * `circuit_level_summary.csv` has `AP_T == AP` (alias), so AP_T here is
    recomputed from `variant_level_summary.csv` by averaging `AP_T` over views
    whose name contains `__inj` (control views have AP_T = 0 and are excluded).
  * `AUC_T` / `Recall@5%_T` are averaged the same way.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
RES = ROOT / "results"


def one(p: Path) -> dict:
    v = pd.read_csv(p / "variant_level_summary.csv", encoding="utf-8-sig")
    v["View"] = v["View"].astype(str)
    inj = v[v.View.str.contains("__inj")]
    c = pd.read_csv(p / "circuit_level_summary.csv", encoding="utf-8-sig")
    row = c[c.Circuit.astype(str) == "MACRO_MEAN"]
    if row.empty:
        row = c.iloc[[0]]
    row = row.iloc[0]
    return dict(tag=p.name, n_views=len(v), n_inj=len(inj),
                AP_65=round(float(row.get("AP", float("nan"))), 4),
                AP_T=round(float(inj["AP_T"].mean()), 4),
                AUC_T=round(float(inj["ROC-AUC_T"].mean()), 4),
                R5_T=round(float(inj["Recall@5%_T"].mean()), 4),
                CEC_Pass=str(row.get("CEC_All_Pass")),
                CEC_ok=int(v.CEC_Status.astype(str).eq("PASS").sum()),
                CEC_n=int(v.CEC_Status.notna().sum()))


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = None
    for i, a in enumerate(sys.argv):
        if a == "--csv-out":
            out = Path(sys.argv[i + 1])
    rows = []
    for a in args:
        p = Path(a)
        if not p.is_absolute():
            p = RES / a if (RES / a).exists() else p
        if not (p / "variant_level_summary.csv").exists():
            print(f"[skip] {p} (no variant_level_summary.csv)")
            continue
        rows.append(one(p))
    d = pd.DataFrame(rows)
    print(d.to_string(index=False))
    if out is not None and rows:
        out.parent.mkdir(parents=True, exist_ok=True)
        d.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[out] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
