"""Explicit polarity-coordinate checks for the three rejected local slots."""
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


def inv_code(ca, sa, cb):
    return ca + "\n" + cb + f'''\nmodule check(input [{sa['width']-1}:0] env,output [4:0] delta,output [4:0] delta_inv,output observation_diff);
wire [4:0] a,b;wire [{len(sa['obs'])-1}:0] oa,ob;
left_design l(env,a,oa);right_design r(env,b,ob);assign delta=a^b;assign delta_inv=a^~b;
assign observation_diff=|(oa^ob);endmodule
'''


def main() -> int:
    plan = json.loads((T12 / "plan.json").read_text(encoding="utf-8"))
    N.OUT = T12
    N.ROWS = []
    N.START = time.monotonic()
    targets = [(0, 0), (1, 2), (2, 2)]
    rows = []
    for pair, slot in targets:
        item = plan["selected"][pair]
        a, _, _ = load_raw(item["source_view"])
        b, _, _ = load_raw(item["partner"])
        mapped = [s["preferred"] for s in item["slots"]]
        ca, sa = N.emit(a, "left_design", item["source_nets"])
        cb, sb = N.emit(b, "right_design", mapped)
        q = N.run(T12 / "polarity" / f"p{pair}_s{slot}", inv_code(ca, sa, cb), [dict(
            pair_index=pair, kind="polarity_check", pattern=str(slot), prove=0,
            partner_net=mapped[slot],
            args=f"-prove delta_inv[{slot}] 0")])[0]
        rows.append(dict(pair_index=pair, slot=slot, source=item["source_nets"][slot],
                         partner=mapped[slot], status=q["status"], folder=q["folder"]))
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    pd.DataFrame(rows).to_csv(T12 / "polarity_checks.csv", index=False,
                              encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())