"""Re-classify round-5 relations with the corrected rules (no SAT)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
R6 = ROOT / "_p0pilot/round6_20261025"
TAB5 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5"
TAB6 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_expand_round6"
sys.path.insert(0, str(R6))
from r6_truth import classify, influence_from_tt, parse_tt  # noqa: E402


def old_class(tt: str, k: int) -> str:
    d = parse_tt(tt, k)
    vals = {p: int(f) for p, (fe, f) in d.items()
            if fe == "feasible" and f in ("0", "1")}
    if not vals:
        return "other"
    if all(v == 0 for v in vals.values()):
        return "constant0"
    if all(v == 1 for v in vals.values()):
        return "constant1"
    if k == 1:
        if vals.get("0") == 0 and vals.get("1") == 1:
            return "identity"
        if vals.get("0") == 1 and vals.get("1") == 0:
            return "inverter"
    if k == 2:
        def ok(fn):
            return all(fn(p) == v for p, v in vals.items())
        if ok(lambda p: int(all(c == "1" for c in p))):
            return "and"
        if ok(lambda p: int(any(c == "1" for c in p))):
            return "or"
        if ok(lambda p: int(p[0] != p[1])):
            return "xor"
    return "other"


def main() -> int:
    rel = pd.read_csv(TAB5 / "r5_nonlocal_relations.csv", encoding="utf-8-sig")
    rows = []
    for _, r in rel.iterrows():
        k = int(str(r.cut_nets).count(";") + 1)
        new = classify(r.truth_table, k, bool(r.enum_complete), r.query_status)
        inf = influence_from_tt(r.truth_table, k,
                                [c for c in str(r.cut_nets).split(";") if c])
        rows.append(dict(relation_id=r.relation_id, design=r.design,
                         role=r.role, usage=r.usage, target=r.target,
                         k=k, enum_complete=int(r.enum_complete),
                         query_status=r.query_status,
                         old_class=old_class(r.truth_table, k),
                         new_status=new["function_status"],
                         new_class=new["function_class"],
                         domain_restricted=new["domain_restricted"],
                         n_feasible=new["n_feasible"], n_forced=new["n_forced"],
                         n_undecided=new["n_undecided"],
                         n_infeasible=new["n_infeasible"],
                         **inf))
    d = pd.DataFrame(rows)
    d.to_csv(TAB6 / "r6_r5_corrected_relations.csv", index=False, encoding="utf-8-sig")
    print("old classes:\n", d.old_class.value_counts().to_string(), flush=True)
    print("\nnew statuses:\n", d.new_status.value_counts().to_string(), flush=True)
    print("\nnew classes:\n", d.new_class.value_counts().to_string(), flush=True)
    print("\nmis-encoded as constant:\n",
          d[(d.old_class.str.startswith("constant")) &
            (d.new_status == "partial_forced")][
              ["target", "old_class", "new_status", "n_forced", "n_undecided"]]
          .to_string(index=False), flush=True)
    info = dict(relations=len(d),
                old_counts=d.old_class.value_counts().to_dict(),
                new_status_counts=d.new_status.value_counts().to_dict(),
                new_class_counts=d.new_class.value_counts().to_dict(),
                old_constant_but_partial=int(((d.old_class.str.startswith("constant")) &
                                              (d.new_status == "partial_forced")).sum()),
                influence_pair_coverage_mean=float(d.influence_pair_coverage.mean()),
                influence_scope_counts=d.influence_scope.value_counts().to_dict())
    (TAB6 / "r6_r5_correction_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
