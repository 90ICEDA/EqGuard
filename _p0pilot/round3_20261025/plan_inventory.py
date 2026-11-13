"""Enumerate train/val unfinished complex candidates and propose the round-3 plan."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
WORK = ROOT / "generate_trans/folds/hosts_bt31"
OUT = ROOT / "_p0pilot/round3_20261025"
TAB = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"


def hpick(items, prefix="r3|"):
    return sorted(items, key=lambda s: hashlib.sha256((prefix + s).encode()).hexdigest())


def main() -> int:
    split = json.loads((WORK / "views.json").read_text(encoding="utf-8"))
    role = {v: r for r in ("train", "val") for v in split[f"{r}_views"]}
    d = pd.read_csv(ROOT / "_p0pilot/functional_relations_agnostic.csv",
                    encoding="utf-8-sig").fillna("")
    d = d[d.kind.isin(["cone", "dff_next"])].copy()
    d["role"] = d.design.map(lambda s: role.get(Path(str(s)).stem, "other"))
    unknown = d[["sat_q1", "sat_q2", "sat_q3", "sat_q4"]].isin(
        ["proved", "refuted"]).sum(axis=1) == 0
    u = d[unknown & d.role.isin(["train", "val"])].copy()
    print("train/val unfinished complex rows:", len(u), flush=True)
    print(u.groupby(["role", "design", "kind"]).size().to_string(), flush=True)
    print("\nby host/recipe:\n",
          u.groupby(["role", u.design.str.split("__").str[0],
                     u.design.str.split("__").str[-1]]).size().to_string(), flush=True)
    u.to_csv(TAB / "r3_unfinished_inventory.csv", index=False, encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
