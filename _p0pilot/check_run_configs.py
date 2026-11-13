"""check_run_configs.py -- are the dump runs comparable (39-dim base, same hyper-params)?"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

RES = Path(_eqguard_path('results'))
KEYS = ("in_channels", "seed", "epochs", "steps_per_epoch", "val_every", "train_mode",
        "label_mask", "view_policy", "model", "lr", "weight_decay", "amp",
        "extra_feats", "norm_extra", "extra_dense_prefix", "no_cov_flag")


def find(tag: str) -> Path | None:
    hits = list(RES.glob(f"*_fold_{tag}/run_config.json"))
    return hits[0] if hits else None


def main() -> int:
    tags = ["v31a_A2s42", "fghtl_CncleanV4coreD42", "fghtl_CncleanV4verdictD42",
            "fghtl_CncleanV4countsD42", "fghtl_CncleanV4safeD42",
            "fghtl_CncleanV4shuf6D42", "fghtl_CncleanV4safeD1", "fghtl_CncleanV4safeD2"]
    cols: dict[str, dict] = {}
    for t in tags:
        p = find(t)
        if p is None:
            print(f"[skip] {t} (no run_config.json yet)")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        cols[t] = {k: d.get(k) for k in KEYS}
    if not cols:
        return 1
    names = list(cols)
    print("key".ljust(20) + "".join(n[-14:].rjust(16) for n in names))
    for k in KEYS:
        vals = [str(cols[n].get(k)) for n in names]
        if len(set(vals)) == 1:
            print(f"{k:20s}{vals[0]:>16s}  (same for all)")
        else:
            print(k.ljust(20) + "".join(v.rjust(16) for v in vals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
