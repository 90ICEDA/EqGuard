"""Classify the 71 rejected SAT logs and look for recoverable structure."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

from collections import Counter
from pathlib import Path
import re

import pandas as pd

ROOT = Path(_eqguard_path(''))
OLD = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sparse_sat_round1"


def main() -> int:
    q = pd.read_csv(OLD / "log_qualification.csv", encoding="utf-8-sig")
    bad = q[~q["accepted"].astype(bool)]
    rows = []
    for _, r in bad.iterrows():
        p = ROOT / r["log"]
        t = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        rows.append(dict(
            log=r["log"], exists=p.exists(), bytes=p.stat().st_size if p.exists() else 0,
            actual=r["actual"], saved=r["saved"],
            sat_passes=t.count("Executing SAT pass"),
            obj0=t.count("Object `\\0' not found"),
            obj_other=len(re.findall(r"ERROR: Object `[^']*' not found", t)),
            errors=len(re.findall(r"^ERROR:", t, flags=re.M)),
            timeout=t.count("TIMEOUT"),
            finished=t.count("End of script"),
            design=str(r["log"]).split("\\")[-1].replace(".sat.log", ""),
        ))
    d = pd.DataFrame(rows)
    d["host"] = d["design"].str.split("__").str[0]
    d["recipe"] = d["design"].str.split("__").str[-1]
    d.to_csv(ROOT / "_p0pilot/round2_20261025/failed_log_classes.csv",
             index=False, encoding="utf-8-sig")
    print(d.groupby(["host", "recipe"]).agg(
        logs=("log", "size"), actual_sum=("actual", "sum"),
        saved_sum=("saved", "sum"), obj0=("obj0", "sum"),
        errors=("errors", "sum"), finished=("finished", "sum")).to_string(), flush=True)
    print("\nzero-SAT-pass logs:", int((d["sat_passes"] == 0).sum()), flush=True)
    print("obj0 logs:", int((d["obj0"] > 0).sum()), flush=True)
    print("partial logs:", int(((d["actual"] > 0) & (d["actual"] != d["saved"])).sum()), flush=True)
    print(d[["design", "actual", "saved", "sat_passes", "obj0", "errors", "finished"]]
          .to_string(index=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
