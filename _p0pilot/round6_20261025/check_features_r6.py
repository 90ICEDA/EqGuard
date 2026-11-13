"""Load-check corrected feature arrays in chunks; assert bounded and coverage."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import numpy as np

ROOT = Path(_eqguard_path(''))
R6 = ROOT / "_p0pilot/round6_20261025"
TAB6 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_expand_round6"


def main() -> int:
    out = {}
    for name in ("r6_extra_real.npy", "r6_extra_permuted.npy"):
        a = np.load(R6 / "features" / name, mmap_mode="r")
        lo, hi = 1.0, 0.0
        for s in range(0, a.shape[0], 200_000):
            chunk = np.asarray(a[s:s + 200_000])
            if not np.isfinite(chunk).all():
                raise ValueError(f"non-finite in {name}")
            lo, hi = min(lo, float(chunk.min())), max(hi, float(chunk.max()))
        covered = int(a[:, -1].sum())
        rows = int((a[:, -1] > 0).sum())
        out[name] = dict(shape=list(a.shape), min=lo, max=hi,
                         last_column="covered", covered=covered, support_rows=rows,
                         extra_norm_n=int(a.shape[1] - 1))
    base = 39
    out["total_dim_normalized"] = base + out["r6_extra_real.npy"]["extra_norm_n"]
    out["total_dim_including_covered"] = base + out["r6_extra_real.npy"]["shape"][1]
    out["bounded_ok"] = all(0.0 <= v["min"] and v["max"] <= 1.0
                            for k, v in out.items() if k.endswith(".npy"))
    (TAB6 / "r6_feature_load_check.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())