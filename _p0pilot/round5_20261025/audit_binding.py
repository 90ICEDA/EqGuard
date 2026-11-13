"""Binding audit: target self-containment, alias/constant, qid count and binding."""
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
R5 = ROOT / "_p0pilot/round5_20261025"
TAB5 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5"
sys.path.insert(0, str(R5))
from r5_evidence import validate_qid_specs  # noqa: E402


def main() -> int:
    plan = json.loads((TAB5 / "r5_candidate_plan.json").read_text(encoding="utf-8"))
    rel = pd.read_csv(TAB5 / "r5_nonlocal_relations.csv", encoding="utf-8-sig")
    q = pd.read_csv(TAB5 / "r5_nonlocal_queries.csv", encoding="utf-8-sig",
                    dtype={"pattern": str})
    rows = []
    for r in plan["frozen"]:
        rid = f"r5|{r['design']}|{r['target']}"
        bits = list(map(int, r["cut_bits"])) if "cut_bits" in r else []
        # cut_bits are not stored in the plan; derive from the relation table
        rr = rel[rel.relation_id == rid].iloc[0]
        bits = list(map(int, rr.cut_bits.split(";")))
        sub = q[q.relation_id == rid]
        specs = [dict(qid=int(x), pattern=p, prove=int(pr))
                 for x, p, pr in zip(sub.qid, sub.pattern, sub.prove)]
        val = validate_qid_specs(r["cut"], specs)
        bad = list(specs)
        if bad:
            bad.pop()
        bad_val = validate_qid_specs(r["cut"], bad)
        rows.append(dict(relation_id=rid, k=len(r["cut"]),
                         cut_bits=";".join(map(str, bits)),
                         unique_bits=int(len(set(bits)) == len(bits)),
                         target_bit_not_in_cut=int(r["target_bit"] not in bits),
                         patterns_expected=2 ** len(r["cut"]),
                         patterns_observed=int(sub.pattern.nunique()),
                         qid_count=int(len(sub)),
                         qid_binding_valid=int(val["valid"]),
                         corrupted_spec_rejected=int(not bad_val["valid"]),
                         issues=val["issues"]))
    d = pd.DataFrame(rows)
    d.to_csv(TAB5 / "r5_binding_audit.csv", index=False, encoding="utf-8-sig")
    print(d.to_string(index=False), flush=True)
    info = dict(relations=len(d),
                all_bits_unique=int(d.unique_bits.sum()),
                target_never_in_cut=int(d.target_bit_not_in_cut.sum()),
                qid_binding_valid=int(d.qid_binding_valid.sum()),
                corrupted_spec_rejected=int(d.corrupted_spec_rejected.sum()))
    (TAB5 / "r5_binding_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
