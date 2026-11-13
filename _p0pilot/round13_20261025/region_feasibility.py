"""Offline region-boundary feasibility for the two failed val blockers."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
import sys
from collections import deque
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
T12 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round12"
T13 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round13"
sys.path.insert(0, str(ROOT / "_p0pilot/round12_20261025"))
from audit_blockers import NetIndex, load_raw  # noqa: E402

CASES = [
    ("val_pair0", "s38417t100__ctlmatchb_d1_s42__ys_abc",
     "s38417t100__ctlmatchb_d1_s42__ys_aig", "_00375_"),
    ("val_pair1", "s38417t100__injalpha_d1_s42__ys_id",
     "s38417t100__injalpha_d1_s42__ys_opt", "_01360_"),
]


def cone(ix: NetIndex, net: str, maxd: int = 4):
    bits = ix.bits(net)
    if len(bits) != 1:
        return []
    q, seen, leaves = deque([(bits[0], 0)]), {bits[0]}, []
    while q:
        b, d = q.popleft()
        drv = ix.drv.get(b, [])
        if d >= maxd or not drv or any(
                "DFF" in x[1].upper() or "LATCH" in x[1].upper() for x in drv):
            leaves.append((b, d))
            continue
        for cn, _typ, _pin in drv:
            for ip, bs in ix.m["cells"][cn].get("connections", {}).items():
                dirs = ix.m["cells"][cn].get("port_directions", {})
                if dirs.get(ip) == "output" or ip in ("Y", "Q", "QN"):
                    continue
                for nb in bs:
                    if isinstance(nb, int) and nb not in seen:
                        seen.add(nb)
                        q.append((nb, d + 1))
    out = []
    for b, d in leaves:
        names = sorted(n for n, v in ix.nets.items() if v.get("bits") == [b])
        out.append(dict(net=names[0] if names else f"bit{b}", depth=d,
                        anchor=bool(names and ("." in names[0]))))
    return out


def main() -> int:
    rows = []
    for label, a, b, net in CASES:
        ma, _, _ = load_raw(a)
        mb, _, _ = load_raw(b)
        la, lb = cone(NetIndex(ma), net), cone(NetIndex(mb), net)
        na = {x["net"] for x in la}
        nb = {x["net"] for x in lb}
        common = sorted(na & nb)
        ok = bool(common) and len(na) <= 4 and len(nb) <= 4
        rows.append(dict(case=label, source_view=a, partner_view=b, net=net,
                         source_boundary=la, partner_boundary=lb,
                         source_size=len(na), partner_size=len(nb),
                         common=common, max_depth=4,
                         boundary_ok=bool(ok),
                         decision=("region_pair_candidate" if ok else
                                   "no_region_boundary: no common anchor and/or >4 inputs"),
                         sat_queries=0))
    (T13 / "region_feasibility.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    flat = [dict(case=r["case"], source_view=r["source_view"],
                 partner_view=r["partner_view"], net=r["net"],
                 source_size=r["source_size"], partner_size=r["partner_size"],
                 common=";".join(r["common"]), boundary_ok=r["boundary_ok"],
                 decision=r["decision"], sat_queries=r["sat_queries"])
            for r in rows]
    pd.DataFrame(flat).to_csv(T13 / "region_feasibility.csv", index=False,
                              encoding="utf-8-sig")
    (T13 / "region_feasibility_manifest.json").write_text(json.dumps(dict(
        cases=len(rows), region_candidates=sum(r["boundary_ok"] for r in rows),
        sat_queries=0, node_pairs=0,
        note=("no new transform-level map; depth-4 boundaries have no common "
              "anchors and are >4, so no region SAT was launched")),
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(flat, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())