"""sat_label_v3.py -- SAT v3 label/plan: structural gate/mux + SAT cone/dff, dedupe, class-balanced cases."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
P0 = ROOT / "_p0pilot/functional_relations_agnostic.csv"
T = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables"
SIMPLE = {"INVX0", "AND2X2", "OR2X1", "XOR2X1", "NAND2X1", "NOR2X1", "MX2X1_RS", "MUX2X1"}
QUOTA = {"mux_cell": 20, "gate_simple": 40, "cone_po": 20, "dff_next": 10}


def cls_of(kind: str) -> str:
    return {"mux": "mux_cell", "gate": "gate_simple",
            "cone": "cone_po", "dff_next": "dff_next"}.get(str(kind), "complex")


def main() -> int:
    d = pd.read_csv(P0, encoding="utf-8-sig").fillna("")
    d["case_class"] = d.kind.map(cls_of)
    # structural labels: target is cell output -> decided=1; simple gate/mux influence=1
    d["decided_v3"] = d.decided.astype(int)
    d["influence_v3"] = d.influence.astype(int)
    d["influence_kind"] = "sat"
    d["sat_needed"] = 1
    simple = d.case_class.isin(["gate_simple", "mux_cell"]) & d.cell_type.isin(SIMPLE)
    d.loc[simple, "decided_v3"] = 1
    d.loc[simple, "influence_v3"] = 1
    d.loc[simple, "influence_kind"] = "structural"
    d.loc[simple, "sat_needed"] = 0
    d["status_v3"] = [
        "structural" if int(s) == 0 else
        ("proved_sat" if (int(a) and int(b)) else "partial_sat")
        for s, a, b in zip(d.sat_needed, d.decided_v3, d.influence_v3)
    ]
    # dedupe exact repeated (design, class, target, cut)
    d["_key"] = (d.design.astype(str) + "|" + d.case_class + "|"
                 + d.target.astype(str) + "|" + d.cut_nets.astype(str))
    u = d.drop_duplicates("_key").copy()
    u.to_csv(T / "functional_relations_v3.csv", index=False, encoding="utf-8-sig")

    # class-balanced case plan per design
    rows = []
    for design, g in u.groupby("design"):
        for cl, q in QUOTA.items():
            sub = g[g.case_class == cl]
            if cl == "gate_simple" and not sub.empty:
                # balance gate types: take up to 10 per cell_type
                sub = (sub.sort_values(["cell_type", "cell"])
                       .groupby("cell_type", group_keys=False).head(10))
            sub = sub.head(q)
            for _, r in sub.iterrows():
                rows.append(dict(design=design, case_class=cl,
                                 case_id=f"{design}|{cl}|{len(rows)}",
                                 target=r.get("target", ""), cut_nets=r.get("cut_nets", ""),
                                 cell_type=r.get("cell_type", ""),
                                 gate_name=r.get("cell", ""),
                                 influence_kind=r.get("influence_kind", "sat"),
                                 sat_needed=int(r.get("sat_needed", 1)),
                                 status_v3=r.get("status_v3", "partial")))
    plan = pd.DataFrame(rows)
    plan.to_csv(T / "case_plan_v3.csv", index=False, encoding="utf-8-sig")
    stats = dict(
        p0_rows=int(len(d)), unique_rows=int(len(u)),
        duplicates=int(len(d) - len(u)),
        sat_needed=int(u.sat_needed.sum()),
        structural=int((u.sat_needed == 0).sum()),
        reduction_frac=round(1 - float(u.sat_needed.mean()), 4),
        by_class=u.groupby("case_class").size().to_dict(),
        proved_v3=u.status_v3.value_counts().to_dict(),
        plan_rows=int(len(plan)), plan_sat=int(plan.sat_needed.sum()),
    )
    (T / "sat_v3_summary.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    print(f"[out] {T / 'functional_relations_v3.csv'}")
    print(f"[out] {T / 'case_plan_v3.csv'}")
    print(f"[out] {T / 'sat_v3_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
