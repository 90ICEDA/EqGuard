"""Inspect truth-table signatures vs driver gate types (no SAT)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
R3 = ROOT / "_p0pilot/round3_20261025"
TAB4 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_chain_round4"


def gate_type(design: str, cell: str) -> str:
    raw = R3 / "struct_raw" / (Path(design).stem + ".json")
    mods = json.loads(raw.read_text(encoding="utf-8"))["modules"]
    mod = next(iter(mods.values()))
    c = mod.get("cells", {}).get(cell)
    return str(c.get("type", "")) if c else ""


def main() -> int:
    rc = pd.read_csv(TAB4 / "r4_reclassify.csv", encoding="utf-8-sig")
    c = pd.read_csv(TAB4 / "r4_two_input_relations.csv", encoding="utf-8-sig")
    r3rel = pd.read_csv(ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/"
                        "sat_valid_round3/r3_recovery_relations.csv",
                        encoding="utf-8-sig")
    drv = dict(zip(r3rel.relation_id, r3rel.driver))
    single = rc[rc.cut_size_canonical == 1].copy()
    single["truth_sig"] = single.truth_table
    single["driver_type"] = [gate_type(d, drv.get(r, "")) for d, r in
                             zip(single.design, single.relation_id)]
    two = c.copy()
    two["truth_sig"] = two.truth_table
    two["driver_type"] = [gate_type(d, drv.get(r, "")) for d, r in
                          zip(two.design, two.relation_id)]
    print("single", len(single), "two", len(two), flush=True)
    print("\nsingle signatures:\n", single.truth_sig.value_counts().to_string(), flush=True)
    print("\ntwo signatures:\n", two.truth_sig.value_counts().to_string(), flush=True)
    print("\nsingle by gate type:\n",
          single.groupby(["driver_type", "truth_sig"]).size().to_string(), flush=True)
    print("\ntwo by gate type:\n",
          two.groupby(["driver_type", "truth_sig"]).size().to_string(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
