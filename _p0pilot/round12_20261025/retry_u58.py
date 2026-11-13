"""Retry U58 slot2 with all other slots at their preferred local mappings."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
T12 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round12"
sys.path.insert(0, str(ROOT / "_p0pilot/round10_20261025"))
sys.path.insert(0, str(ROOT / "_p0pilot/round12_20261025"))
import native as N  # noqa: E402
from audit_blockers import load_raw  # noqa: E402
from run_round12 import eq_code  # noqa: E402

N.OUT = T12
N.ROWS = []
N.START = time.monotonic()


def main() -> int:
    plan = json.loads((T12 / "plan.json").read_text(encoding="utf-8"))
    item = plan["selected"][2]
    a, _, _ = load_raw(item["source_view"])
    b, _, _ = load_raw(item["partner"])
    ca, sa = N.emit(a, "left_design", item["source_nets"])
    mapped = [s["preferred"] for s in item["slots"]]
    rows = []
    for j, name in enumerate(item["slots"][2]["alternatives"]):
        mapped[2] = name
        cb, sb = N.emit(b, "right_design", mapped)
        q = N.run(T12 / "retry_u58" / f"slot2_try{j}", eq_code(ca, sa, cb),
                  [dict(pair_index=2, kind="boundary_equivalence", pattern="2",
                        prove=0, partner_net=name,
                        args="-prove delta[2] 0")])[0]
        rows.append(dict(slot=2, candidate=name, status=q["status"],
                         folder=q["folder"]))
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    pd.DataFrame(rows).to_csv(T12 / "retry_u58.csv", index=False,
                              encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())