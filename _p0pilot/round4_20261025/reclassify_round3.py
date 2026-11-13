"""Re-classify round-3 recovery relations without any new SAT query.

Patterns are reconstructed from the stored row order (all-1 then all-0) because
the saved CSV column lost leading zeros when written as integers.
"""
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
R3 = ROOT / "_p0pilot/round3_20261025"
R4 = ROOT / "_p0pilot/round4_20261025"
TAB3 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"
TAB4 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_chain_round4"
sys.path.insert(0, str(R4))
from sat_evidence_v4 import evaluate_case_v4, normalize_cut  # noqa: E402


def main() -> int:
    rel = pd.read_csv(TAB3 / "r3_recovery_relations.csv", encoding="utf-8-sig")
    q = pd.read_csv(TAB3 / "r3_recovery_queries.csv", encoding="utf-8-sig",
                    dtype={"pattern": str})
    out, truths = [], []
    for _, r in rel.iterrows():
        cut_orig = [c for c in str(r.cut_nets).split(";") if c]
        design = str(r.design)
        raw = R3 / "struct_raw" / (Path(design).stem + ".json")
        mods = json.loads(raw.read_text(encoding="utf-8"))["modules"]
        mod = next(iter(mods.values()))
        netbits = {nm: tuple(b for b in info.get("bits", []) if isinstance(b, int))
                   for nm, info in mod["netnames"].items()}
        for nm, p in mod.get("ports", {}).items():
            netbits[nm] = tuple(b for b in p.get("bits", []) if isinstance(b, int))
        norm = normalize_cut(cut_orig, netbits, str(r.target))
        canon = [c["name"] for c in norm["canonical"]]
        # map each original cut name to a canonical index (or None)
        idx_of_name = {c["name"]: i for i, c in enumerate(norm["canonical"])}
        for a in norm["aliases"]:
            if a["name"] not in idx_of_name:
                idx_of_name[a["name"]] = idx_of_name.get(a["alias_of"])
        sub = q[q.relation_id == r.relation_id].reset_index(drop=True)
        if len(sub) != 4:
            out.append(dict(relation_id=r.relation_id, design=design,
                            target=r.target, status="bad_query_rows",
                            n_rows=len(sub)))
            continue
        statuses = {i + 1: sub.status.iloc[i] for i in range(4)}
        # reconstruct original patterns from row order
        pats_orig = [(1,) * len(cut_orig), (0,) * len(cut_orig)]
        # map to canonical patterns
        canon_pats = []
        for po in pats_orig:
            cp = []
            for j, nm in enumerate(cut_orig):
                ci = idx_of_name.get(nm)
                if ci is not None:
                    cp.append((ci, po[j]))
            cp = [b for _, b in sorted(cp)]
            canon_pats.append(tuple(cp))
        patterns = ["".join(str(b) for b in p) for p in canon_pats]
        ev = evaluate_case_v4(canon, patterns, [1, 2, 3, 4], statuses,
                              cut_meta=dict(original=cut_orig,
                                            aliases=norm["aliases"],
                                            constants=norm["constants"],
                                            invalid=norm["invalid"]))
        row = dict(relation_id=r.relation_id, design=design, role=r.role,
                   host=r.host, recipe=r.recipe, kind=r.kind, target=r.target,
                   cut_orig=";".join(cut_orig), cut_canonical=";".join(canon),
                   cut_size_orig=len(cut_orig), cut_size_canonical=len(canon),
                   aliases=json.dumps(norm["aliases"], ensure_ascii=False),
                   constants=";".join(norm["constants"]),
                   invalid=json.dumps(norm["invalid"], ensure_ascii=False),
                   old_sufficiency=r.functional_sufficiency,
                   old_patterns_enumerated=r.patterns_enumerated)
        row.update({k: ev[k] for k in (
            "enum_complete", "enum_reason", "enum_expected", "enum_observed",
            "enum_duplicates", "enum_missing", "n_patterns", "n_feasible",
            "n_infeasible", "n_forced", "n_undecided", "n_one_sided",
            "n_premise_feasible_known", "determinism_ratio",
            "functional_sufficiency", "sufficiency_reason", "query_status",
            "influence_status", "influence_mean", "influence_max",
            "n_influence_inputs", "n_valid_influence_inputs", "truth_table")})
        out.append(row)
        truths.append(dict(relation_id=r.relation_id, design=design,
                           target=r.target, patterns=";".join(patterns),
                           truth_table=ev["truth_table"]))
    d = pd.DataFrame(out)
    d.to_csv(TAB4 / "r4_reclassify.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(truths).to_csv(TAB4 / "r4_truth_tables_round3.csv", index=False,
                                encoding="utf-8-sig")
    print(d.groupby(["cut_size_canonical", "enum_complete",
                     "functional_sufficiency"]).size().to_string(), flush=True)
    print("\nold -> new sufficiency:\n",
          pd.crosstab(d.old_sufficiency, d.functional_sufficiency).to_string(),
          flush=True)
    print("\ninfluence new:\n", d.influence_status.value_counts().to_string(), flush=True)
    print("\nupgraded single-input:",
          int(((d.cut_size_canonical == 1) &
               (d.old_sufficiency == "not_enumerated") &
               (d.functional_sufficiency == "proved")).sum()), flush=True)
    print("\nnon-trivial aliases/constants:",
          int((d.aliases != "[]").sum()), int((d.constants != "").sum()), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
