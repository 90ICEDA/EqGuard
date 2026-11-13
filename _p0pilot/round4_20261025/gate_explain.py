"""Check whether every forced value is exactly the driver gate's truth table."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
TAB4 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_chain_round4"


def gate_fn(typ: str, pat: str):
    bits = [int(c) for c in pat]
    if typ == "AND2X2" and len(bits) == 2:
        return int(all(bits))
    if typ == "OR2X1" and len(bits) == 2:
        return int(any(bits))
    if typ == "XOR2X1" and len(bits) == 2:
        return int(bits[0] ^ bits[1])
    if typ == "INVX0" and len(bits) == 1:
        return int(1 - bits[0])
    return None


def main() -> int:
    d = pd.read_csv(TAB4 / "r4_unified_relations.csv", encoding="utf-8-sig")
    rows = []
    for _, r in d.iterrows():
        checked = matched = mismatched = 0
        for item in str(r.truth_table).split(";"):
            pat, feas, force = item.split(":")
            if feas != "feasible" or force in ("not_applicable", "undecided", "unknown"):
                continue
            exp = gate_fn(str(r.driver_type), pat)
            if exp is None:
                continue
            checked += 1
            if int(force) == exp:
                matched += 1
            else:
                mismatched += 1
        rows.append(dict(relation_id=r.relation_id, design=r.design,
                         target=r.target, driver_type=r.driver_type,
                         cut_size=r.cut_size, source=r.source,
                         checked=checked, matched=matched, mismatched=mismatched,
                         explained=(int(mismatched == 0 and checked > 0)
                                    if checked else None)))
    out = pd.DataFrame(rows)
    out.to_csv(TAB4 / "r4_gate_explain.csv", index=False, encoding="utf-8-sig")
    print(out.groupby(["source", "driver_type"]).agg(
        relations=("relation_id", "size"), checked=("checked", "sum"),
        matched=("matched", "sum"), mismatched=("mismatched", "sum"),
        explained=("explained", "sum")).to_string(), flush=True)
    print("\ntotal relations", len(out), "explained", int(out.explained.fillna(0).sum()),
          "unchecked", int((out.checked == 0).sum()),
          "mismatched relations", int((out.mismatched > 0).sum()), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
