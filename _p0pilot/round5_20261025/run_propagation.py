"""Conditional propagation: one cut leaf -> frozen endpoint, other leaves fixed."""
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
TAB5 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5"
sys.path.insert(0, str(R3))
sys.path.insert(0, str(R5))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402
from r3_nets import build_index  # noqa: E402
from r5_runner import query_key, run_batch  # noqa: E402
from r5_evidence import statuses_by_qid  # noqa: E402
from sat_evidence_v4 import pattern_state  # noqa: E402


def main() -> int:
    rel = pd.read_csv(TAB5 / "r5_nonlocal_relations.csv", encoding="utf-8-sig")
    pick = []
    pick += rel[rel.functional_sufficiency == "proved"].head(2).relation_id.tolist()
    pick += rel[rel.functional_sufficiency != "proved"].sort_values(
        "determinism_ratio", ascending=False).head(2).relation_id.tolist()
    sel = rel[rel.relation_id.isin(pick)].copy()
    t0 = time.perf_counter()
    rows, execs, review = [], [], []
    total = 0
    for _, r in sel.iterrows():
        v = WORK / "trans" / r.design
        top = P0.module_name(v)
        mods = json.loads((R3 / "struct_raw" / f"{Path(r.design).stem}.json")
                          .read_text(encoding="utf-8"))["modules"]
        idx = build_index(next(iter(mods.values())))
        ports = set(idx["ports"].keys())
        cut = list(r.cut_nets.split(";"))
        cut_bits = list(map(int, r.cut_bits.split(";")))
        internal, internal_bit = cut[0], cut_bits[0]
        context = cut[1:]
        endpoint = str(r.target)
        cases, specs_all = [], []
        for ci, ctx in enumerate([tuple([0] * len(context)),
                                  tuple([1] * len(context))]):
            pats = ["".join(str(b) for b in list(ctx) + [x]) for x in (0, 1)]
            specs, qid = [], 0
            for pat in pats:
                for prove in (1, 0):
                    qid += 1
                    key = query_key(v, cut, cut_bits, endpoint, pat, prove, 5)
                    cases.append(dict(cut=cut, cut_bits=cut_bits, target=endpoint,
                                      pattern=pat, prove=prove, query_key=key,
                                      _ports=ports))
                    specs.append(dict(qid=qid, pattern=pat, prove=prove,
                                      query_key=key))
            specs_all.append((ctx, pats, specs))
        total += len(cases)
        exec_id = f"r5_prop_{Path(r.design).stem}_{int(t0)}_{len(rows)}"
        res = run_batch(v, top, cases, exec_id, TAB5, timeout=5)
        execs.append(dict(execution_id=exec_id, design=r.design,
                          queries=res["new"], timeouts=res["timeouts"],
                          errors=res["errors"], wall_s=res.get("wall_s", 0)))
        for ctx, pats, specs in specs_all:
            st = statuses_by_qid(specs, res["statuses"])
            states = [pattern_state(st[2 * pi + 1], st[2 * pi + 2])
                      for pi in range(2)]
            f0, f1 = states[0]["forcing"], states[1]["forcing"]
            feasible = [s["feasibility"] for s in states]
            if any(s["feasibility"] == "unknown" for s in states):
                cls = "unknown_query"
            elif all(s["feasibility"] == "infeasible" for s in states):
                cls = "context_infeasible"
            elif feasible == ["feasible", "feasible"] and f0 in (0, 1) and f1 in (0, 1) and f0 != f1:
                cls = "conditional_propagates"
            elif feasible == ["feasible", "feasible"] and f0 in (0, 1) and f1 in (0, 1) and f0 == f1:
                cls = "blocked_same_value"
            else:
                cls = "undetermined"
            rows.append(dict(pair_id=r.relation_id, design=r.design,
                             role=r.role, usage=r.usage, endpoint=endpoint,
                             internal_target=internal, internal_bit=internal_bit,
                             context=";".join(context),
                             context_pattern="".join(map(str, ctx)),
                             patterns=";".join(pats),
                             forcing_values=f"{f0};{f1}",
                             feasibility=";".join(feasible),
                             classification=cls, execution_id=exec_id))
            for pi in range(2):
                review.append(dict(pair_id=r.relation_id, design=r.design,
                                   endpoint=endpoint, cut=cut, cut_bits=cut_bits,
                                   context_pattern="".join(map(str, ctx)),
                                   pattern=pats[pi], prove=1,
                                   query_key=specs[2 * pi]["query_key"],
                                   original=res["statuses"][specs[2 * pi]["query_key"]]))
    return _review(rows, execs, review, total, t0)


def _review(rows, execs, review, total, t0) -> int:
    d = pd.DataFrame(rows)
    d.to_csv(TAB5 / "r5_propagation.csv", index=False, encoding="utf-8-sig")
    rev = []
    for rc in review:
        v = WORK / "trans" / rc["design"]
        top = P0.module_name(v)
        mods = json.loads((R3 / "struct_raw" / f"{Path(rc['design']).stem}.json")
                          .read_text(encoding="utf-8"))["modules"]
        ports = set(next(iter(mods.values()))["ports"].keys())
        cases = [dict(cut=rc["cut"], cut_bits=rc["cut_bits"], target=rc["endpoint"],
                      pattern=rc["pattern"], prove=rc["prove"],
                      query_key=rc["query_key"], _ports=ports)]
        exec_id = f"r5_review_{rc['query_key'][:10]}"
        res = run_batch(v, top, cases, exec_id, TAB5, timeout=5, force=True)
        after = res["statuses"][rc["query_key"]]
        rev.append(dict(pair_id=rc["pair_id"], design=rc["design"],
                        endpoint=rc["endpoint"],
                        context_pattern=rc["context_pattern"],
                        pattern=rc["pattern"], prove=rc["prove"],
                        original=rc["original"], re_solve=after,
                        agree=int(after == rc["original"]),
                        execution_id=exec_id))
    rv = pd.DataFrame(rev)
    rv.to_csv(TAB5 / "r5_propagation_review.csv", index=False, encoding="utf-8-sig")
    info = dict(pairs=int(d.pair_id.nunique()), propagation_queries=int(total),
                review_queries=len(rv), review_agree=int(rv.agree.sum()),
                classes=d.classification.value_counts().to_dict(),
                executions=execs, wall_s=round(time.perf_counter() - t0, 1))
    (TAB5 / "r5_propagation_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(d[["design", "endpoint", "internal_target", "context_pattern",
             "forcing_values", "classification"]].to_string(index=False), flush=True)
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
