"""ap_t_stats.py -- stability diagnostics for the 24 inj-view AP_T (tiny positive counts)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RES = Path(_eqguard_path('results'))


def one(tag: str) -> dict:
    p = RES / tag / "variant_level_summary.csv"
    d = pd.read_csv(p, encoding="utf-8-sig")
    d = d[d.View.astype(str).str.contains("__inj")]
    ap = d["AP_T"].astype(float)
    w = d["N_Trojan"].astype(float)
    r5 = d["Recall@5%_T"].astype(float)
    return dict(tag=tag.split("_fold_")[-1], n_views=len(d), n_pos=int(w.sum()),
                pos_min=int(w.min()), pos_max=int(w.max()),
                mean=round(ap.mean(), 4),
                wmean=round(float(np.average(ap, weights=w)), 4),
                median=round(float(ap.median()), 4),
                n_gt_02=int((ap > 0.2).sum()), n_lt_01=int((ap < 0.01).sum()),
                r5=round(r5.mean(), 4))


def main() -> int:
    tags = sys.argv[1:]
    rows = [one(t) for t in tags]
    print(pd.DataFrame(rows).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
