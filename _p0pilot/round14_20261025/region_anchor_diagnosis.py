"""Corrected anchor diagnosis for the two val region cases (no SAT/search)."""
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
T14 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round14"
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
        aliases = sorted(n for n, v in ix.nets.items() if v.get("bits") == [b])
        ports = [n for n in aliases if n in ix.m.get("ports", {})]
        drv = ix.drv.get(b, [])
        dff = [(c, t, p) for c, t, p in drv
               if "DFF" in t.upper() or "LATCH" in t.upper()]
        if ports:
            kind = "PI" if any(ix.m["ports"][n].get("direction") == "input"
                               for n in ports) else "PORT"
            anchor = True
        elif dff:
            kind = "DFF_state"
            anchor = True
        elif not drv:
            kind = "undriven_constant"
            anchor = False
        elif d >= maxd:
            kind = "internal_truncated"
            anchor = False
        else:
            kind = "internal_leaf"
            anchor = False
        out.append(dict(bit=b, depth=d, aliases=aliases[:12],
                        all_alias_count=len(aliases), ports=ports,
                        driver=[dict(cell=c, type=t, pin=p) for c, t, p in drv],
                        dff=[dict(cell=c, type=t, polarity=p) for c, t, p in dff],
                        kind=kind, anchor=anchor))
    return out


def main() -> int:
    rows = []
    for label, a, b, net in CASES:
        ma, _, _ = load_raw(a)
        mb, _, _ = load_raw(b)
        la, lb = cone(NetIndex(ma), net), cone(NetIndex(mb), net)
        rows.append(dict(case=label, source_view=a, partner_view=b, net=net,
                         depth=4, source=la, partner=lb,
                         source_anchor=sum(x["anchor"] for x in la),
                         partner_anchor=sum(x["anchor"] for x in lb),
                         source_dff=sum(x["kind"] == "DFF_state" for x in la),
                         partner_dff=sum(x["kind"] == "DFF_state" for x in lb),
                         source_truncated=sum(x["kind"] == "internal_truncated" for x in la),
                         partner_truncated=sum(x["kind"] == "internal_truncated" for x in lb),
                         source_pi=sum(x["kind"] == "PI" for x in la),
                         partner_pi=sum(x["kind"] == "PI" for x in lb)))
    (T14 / "region_anchor_diagnosis.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    flat = []
    for r in rows:
        for side in ("source", "partner"):
            for x in r[side]:
                flat.append(dict(case=r["case"], side=side, bit=x["bit"],
                                 depth=x["depth"], kind=x["kind"],
                                 anchor=x["anchor"], aliases=";".join(x["aliases"]),
                                 all_alias_count=x["all_alias_count"],
                                 ports=";".join(x["ports"]),
                                 driver=";".join(f"{d['cell']}|{d['type']}|{d['pin']}"
                                                 for d in x["driver"]),
                                 dff=";".join(f"{d['cell']}|{d['type']}|{d['polarity']}"
                                               for d in x["dff"])))
    pd.DataFrame(flat).to_csv(T14 / "region_anchor_diagnosis.csv", index=False,
                              encoding="utf-8-sig")
    summary = dict(
        cases=len(rows),
        source_dff=sum(r["source_dff"] for r in rows),
        partner_dff=sum(r["partner_dff"] for r in rows),
        source_pi=sum(r["source_pi"] for r in rows),
        partner_pi=sum(r["partner_pi"] for r in rows),
        source_truncated=sum(r["source_truncated"] for r in rows),
        partner_truncated=sum(r["partner_truncated"] for r in rows),
        conclusion=("Depth-4 leaves include real DFF-state anchors; absence of a "
                    "common proven anchor at this truncated depth does not prove "
                    "there is no region correspondence"),
        sat_queries=0, region_pairs_added=0)
    (T14 / "region_anchor_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())