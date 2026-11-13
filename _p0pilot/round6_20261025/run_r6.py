"""Run the frozen round-6 expansion (16 x 4-bit relations, 512 queries)."""
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
WORK = ROOT / "generate_trans/folds/hosts_bt31"
R3 = ROOT / "_p0pilot/round3_20261025"
R5 = ROOT / "_p0pilot/round5_20261025"
R6 = ROOT / "_p0pilot/round6_20261025"
TAB6 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_expand_round6"
sys.path.insert(0, str(R3))
sys.path.insert(0, str(R5))
sys.path.insert(0, str(R6))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402
from r3_nets import build_index  # noqa: E402
from r6_runner import query_key, run_batch  # noqa: E402
from r5_evidence import validate_qid_specs, statuses_by_qid  # noqa: E402
from sat_evidence_v4 import evaluate_case_v4  # noqa: E402


def main() -> int:
    plan = json.loads((TAB6 / "r6_candidate_plan.json").read_text(encoding="utf-8"))
    frozen = plan["frozen"]
    t0 = time.perf_counter()
    rows, qrows, execs = [], [], []
    total = 0
    for design, group in pd.DataFrame(frozen).groupby("design", sort=False):
        v = WORK / "trans" / design
        top = P0.module_name(v)
        mods = json.loads((R6 / "struct_raw" / f"{Path(design).stem}.json")
                          .read_text(encoding="utf-8"))["modules"]
        idx = build_index(next(iter(mods.values())))
        ports = set(idx["ports"].keys())
        cases, meta = [], []
        for _, r in group.iterrows():
            cut = list(r["cut"])
            cut_bits = [idx["netbits"][c][0] for c in cut]
            specs, qid = [], 0
            for pat in r["patterns"]:
                for prove in (1, 0):
                    qid += 1
                    k = query_key(v, cut, cut_bits, str(r["target"]), pat,
                                  prove, 5)
                    cases.append(dict(cut=cut, cut_bits=cut_bits,
                                      target=str(r["target"]), pattern=pat,
                                      prove=prove, query_key=k, _ports=ports))
                    specs.append(dict(qid=qid, pattern=pat, prove=prove,
                                      query_key=k))
            val = validate_qid_specs(cut, specs)
            meta.append((r, cut, cut_bits, specs, val))
        total += len(cases)
        exec_id = f"r6_expand_{Path(design).stem}_{int(t0)}"
        res = run_batch(v, top, cases, exec_id, TAB6, timeout=5)
        execs.append(dict(execution_id=exec_id, design=design,
                          queries=res["new"], hits=res["hits"],
                          timeouts=res["timeouts"], errors=res["errors"],
                          wall_s=res.get("wall_s", 0)))
        for r, cut, cut_bits, specs, val in meta:
            st = statuses_by_qid(specs, res["statuses"])
            ev = evaluate_case_v4(cut, list(r["patterns"]),
                                  list(range(1, 2 * len(r["patterns"]) + 1)), st,
                                  cut_meta=dict(cut_bits=cut_bits,
                                                depths=list(r["cut_distances"]),
                                                qid_binding=val))
            drv = str(r["driver"])
            dtype = (idx["cells"].get(drv, {}).get("type", "")
                     if drv in idx["cells"] else "")
            row = dict(relation_id=f"r6|{r['design']}|{r['target']}",
                       design=r["design"], role=r["role"], host=r["host"],
                       inst=r["inst"], recipe=r["recipe"], usage=r["usage"],
                       kind=r["kind"], target=r["target"],
                       target_id=r["target_id"], driver=drv,
                       driver_type=dtype,
                       cut_nets=";".join(cut),
                       cut_bits=";".join(map(str, cut_bits)),
                       cut_depths=";".join(map(str, r["cut_distances"])),
                       cut_leaf_total=int(r["cut_leaf_total"]),
                       cut_kind=r["cut_kind"],
                       selected_ratio=float(r["selected_ratio"]),
                       cut_truncated=int(r["cut_truncated"]),
                       n_patterns=int(r["n_patterns"]),
                       qid_binding_valid=int(val["valid"]),
                       qid_binding_issues=val["issues"],
                       reach_po=int(r["reach_po"]), reach_dff=int(r["reach_dff"]),
                       execution_id=exec_id)
            row.update({k: ev[k] for k in (
                "enum_complete", "enum_reason", "n_feasible", "n_infeasible",
                "n_forced", "n_undecided", "n_premise_feasible_known",
                "determinism_ratio", "functional_sufficiency",
                "sufficiency_reason", "query_status", "truth_table",
                "influence_status", "influence_mean", "influence_max",
                "n_valid_influence_inputs")})
            rows.append(row)
            for s in specs:
                qrows.append(dict(relation_id=row["relation_id"], qid=s["qid"],
                                  pattern=s["pattern"], prove=s["prove"],
                                  query_key=s["query_key"],
                                  status=res["statuses"][s["query_key"]]))
    rel = pd.DataFrame(rows)
    rel.to_csv(TAB6 / "r6_nonlocal_relations.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(qrows).to_csv(TAB6 / "r6_nonlocal_queries.csv", index=False,
                               encoding="utf-8-sig")
    info = dict(relations=len(rel), queries=int(total),
                proved=int((rel.functional_sufficiency == "proved").sum()),
                not_proved=int((rel.functional_sufficiency == "not_proved").sum()),
                inconclusive=int((rel.functional_sufficiency == "not_enumerated").sum()),
                qid_binding_valid=int(rel.qid_binding_valid.sum()),
                cut_size_counts=rel.cut_nets.str.count(";").add(1).value_counts().to_dict(),
                executions=execs, wall_s=round(time.perf_counter() - t0, 1))
    (TAB6 / "r6_nonlocal_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

