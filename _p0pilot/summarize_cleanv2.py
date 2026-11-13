"""summarize_cleanv2.py -- 只读汇总 C/D cleanV2 + D variants 的 MACRO_MEAN。"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

from pathlib import Path

import pandas as pd

R = Path(_eqguard_path('results'))
NAMES = [
    "hosts_bt31_seed42mode4_allb1_fold_fghtl_CncleanV2R42",
    "hosts_bt31_seed42mode4_allb1_fold_fghtl_DncleanV2R42",
    "hosts_bt31_seed1mode4_allb1_fold_fghtl_CncleanV2R1",
    "hosts_bt31_seed1mode4_allb1_fold_fghtl_DncleanV2R1",
    "hosts_bt31_seed42mode4_allb1_fold_fghtl_DncleanV2Pos42",
    "hosts_bt31_seed42mode4_allb1_fold_fghtl_DncleanV2W42",
]
COLS = ["AP", "ROC-AUC", "Recall@1%", "Recall@5%", "FPR", "CEC_All_Pass"]


def main() -> int:
    rows = []
    for n in NAMES:
        p = R / n / "circuit_level_summary.csv"
        if not p.exists():
            print(f"[missing] {n}")
            continue
        d = pd.read_csv(p, encoding="utf-8-sig")
        m = d[d["Circuit"].astype(str).str.strip() == "MACRO_MEAN"]
        if m.empty:
            print(f"[no MACRO_MEAN] {n}")
            continue
        r = m.iloc[0]
        rows.append({"run": n.replace("hosts_bt31_", "").replace("mode4_allb1_", ""), **{c: r[c] for c in COLS}})
    print(pd.DataFrame(rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
