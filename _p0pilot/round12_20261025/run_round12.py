"""Round-12 bounded mapping: correspondence, full tables, reviews."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import itertools
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
T12 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round12"
sys.path.insert(0, str(ROOT / "_p0pilot/round10_20261025"))
sys.path.insert(0, str(ROOT / "_p0pilot/round9_20261025"))
sys.path.insert(0, str(ROOT / "_p0pilot/round12_20261025"))
import native as N  # noqa: E402
from run_pilot import truth, table_wrapper  # noqa: E402
from boundary_repr import COLS, summarize  # noqa: E402
from audit_blockers import load_raw  # noqa: E402

N.OUT = T12
N.ROWS = []
N.MODULES = {}
N.START = time.monotonic()


def eq_code(ca, sa, cb):
    return ca + "\n" + cb + f'''\nmodule check(input [{sa['width']-1}:0] env,output [4:0] delta,output observation_diff);
wire [4:0] a,b;wire [{len(sa['obs'])-1}:0] oa,ob;
left_design l(env,a,oa);right_design r(env,b,ob);assign delta=a^b;assign observation_diff=|(oa^ob);endmodule
'''


def kind_used(kind):
    return sum(1 for q in N.ROWS if q.get("kind") == kind)


def checkpoint(name, outcomes, tables):
    pd.DataFrame(N.ROWS).to_csv(T12 / f"checkpoint_{name}_queries.csv",
                                 index=False, encoding="utf-8-sig")
    (T12 / f"checkpoint_{name}.json").write_text(json.dumps(dict(
        queries=len(N.ROWS), outcomes=outcomes, tables=len(tables),
        time=time.strftime("%Y-%m-%dT%H:%M:%S%z")), ensure_ascii=False,
        indent=2), encoding="utf-8")


def main() -> int:
    if (T12 / "queries.csv").exists():
        raise RuntimeError("round12 queries.csv already exists; refuse to overwrite")
    plan = json.loads((T12 / "plan.json").read_text(encoding="utf-8"))
    sha = plan.pop("plan_sha256")
    assert hashlib.sha256(json.dumps(plan, ensure_ascii=False,
                                     sort_keys=True).encode()).hexdigest() == sha
    context = json.loads((ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/"
                          "sat_pair_round11/aligned_context.json").read_text(
                              encoding="utf-8"))
    assert context["context_id"] == plan["context_id"]
    selected = plan["selected"]
    outcomes, tables, sync = [], [], []
    completed = 0

    for i, item in enumerate(selected):
        base = dict(pair_index=i, relation_id=item["relation_id"],
                    role=item["role"], source_view=item["source_view"],
                    partner_view=item["partner"], context_id=context["context_id"])
        if completed >= 2:
            outcomes.append(dict(**base, status="not_attempted_complete_cap"))
            continue
        if kind_used("boundary_equivalence") >= plan["budget"]["correspondence_max"]:
            outcomes.append(dict(**base, status="not_attempted_correspondence_budget"))
            continue
        try:
            a, ainfo, apath = load_raw(item["source_view"])
            b, binfo, bpath = load_raw(item["partner"])
            ca, sa = N.emit(a, "left_design", item["source_nets"])
        except (ValueError, KeyError, FileNotFoundError) as e:
            outcomes.append(dict(**base, status="model_or_mapping_error",
                                 detail=str(e)))
            continue
        mapped = [slot["source"] for slot in item["slots"]]
        failed = None
        try:
            for j, slot in enumerate(item["slots"]):
                accepted = False
                for attempt, name in enumerate(slot["alternatives"]):
                    if kind_used("boundary_equivalence") >= plan["budget"]["correspondence_max"]:
                        raise RuntimeError("correspondence budget")
                    mapped[j] = name
                    cb, sb = N.emit(b, "right_design", mapped)
                    q = N.run(T12 / "pairs" / str(i) / f"slot{j}_try{attempt}",
                              eq_code(ca, sa, cb),
                              [dict(pair_index=i, kind="boundary_equivalence",
                                    pattern=str(j), prove=0, partner_net=name,
                                    args=f"-prove delta[{j}] 0")])[0]
                    if q["status"] == "proved":
                        accepted = True
                        sync.append(dict(pair_index=i, slot=j, source=slot["source"],
                                         partner=name, status="proved",
                                         folder=q["folder"], query_id=q["query_id"]))
                        break
                    sync.append(dict(pair_index=i, slot=j, source=slot["source"],
                                     partner=name, status=q["status"],
                                     folder=q["folder"], query_id=q["query_id"]))
                if not accepted:
                    failed = j
                    break
        except RuntimeError:
            outcomes.append(dict(**base, status="correspondence_budget_pending"))
            checkpoint("after_budget", outcomes, tables)
            break
        if failed is not None:
            outcomes.append(dict(**base, status="boundary_not_proved",
                                 failed_slot=failed))
            checkpoint("after_boundary", outcomes, tables)
            continue
        cb, sb = N.emit(b, "right_design", mapped)
        if (sa["ports"], sa["states"], sa["obs"]) != (sb["ports"], sb["states"], sb["obs"]):
            outcomes.append(dict(**base, status="state_or_interface_mismatch",
                                 mapped_nets=mapped))
            continue
        po = N.run(T12 / "pairs" / str(i) / "PO_D", eq_code(ca, sa, cb),
                   [dict(pair_index=i, kind="PO_D_equivalence", pattern="all",
                         prove=0, args="-prove observation_diff 0")])[0]
        if po["status"] != "proved":
            outcomes.append(dict(**base, status="PO_D_not_proved",
                                 global_equivalence=po["status"],
                                 mapped_nets=mapped))
            continue
        if kind_used("aligned_source") + 64 > plan["budget"]["tables_max"]:
            outcomes.append(dict(**base, status="table_budget_pending",
                                 mapped_nets=mapped))
            continue
        measured = []
        for side, code, mod, spec, view in (
                ("source", ca, "left_design", sa, item["source_view"]),
                ("partner", cb, "right_design", sb, item["partner"])):
            qs = [dict(pair_index=i, kind="aligned_" + side, pattern=p, prove=v,
                       args=f"-set pattern 4'b{''.join(reversed(p))} "
                            f"-set premise 1 -prove target {v}")
                  for p in map("".join, itertools.product("01", repeat=4))
                  for v in (1, 0)]
            rr = N.run(T12 / "pairs" / str(i) / side,
                       table_wrapper(code, mod, spec), qs)
            t = truth(rr)
            measured.append(t)
            desc, per = summarize(t, 4)
            tables.append(dict(pair_index=i, side=side, view=view,
                               relation_id=item["relation_id"],
                               context_id=context["context_id"], truth=t,
                               features=desc, inputs=per,
                               source_sha=N.sha(N.WORK / "trans" / f"{view}.v")))
        fa, ia = summarize(measured[0], 4)
        fb, ib = summarize(measured[1], 4)
        good = (measured[0] == measured[1]
                and not any(v[0] == "unknown" for v in measured[0].values()))
        outcomes.append(dict(
            **base, status="paired_validated" if good else "table_mismatch_or_unknown",
            mapped_nets=mapped, global_equivalence=po["status"],
            feature_max_abs_diff=max(abs(fa[c] - fb[c]) for c in COLS),
            input_stats_equal=ia == ib,
            source_sha=ainfo["source_sha"], partner_sha=binfo["source_sha"],
            source_snapshot=str(apath.relative_to(ROOT)),
            partner_snapshot=str(bpath.relative_to(ROOT))))
        if good:
            completed += 1
        checkpoint("after_pair", outcomes, tables)
    checkpoint("before_reviews", outcomes, tables)

    # Bounded independent reviews: 8 per validated pair, including all five slots.
    reviews = []
    review_candidates = []
    for i in range(len(selected)):
        if not any(o.get("pair_index") == i and o.get("status") == "paired_validated"
                   for o in outcomes):
            continue
        boundary = [q for q in N.ROWS if q.get("pair_index") == i
                    and q.get("kind") == "boundary_equivalence"
                    and q.get("status") == "proved"]
        po = [q for q in N.ROWS if q.get("pair_index") == i
              and q.get("kind") == "PO_D_equivalence"]
        src = [q for q in N.ROWS if q.get("pair_index") == i
               and q.get("kind") == "aligned_source" and q.get("pattern") == "0000"
               and q.get("prove") == 1]
        par = [q for q in N.ROWS if q.get("pair_index") == i
               and q.get("kind") == "aligned_partner" and q.get("pattern") == "0000"
               and q.get("prove") == 1]
        review_candidates += boundary[:5] + po[:1] + src[:1] + par[:1]
    for i, q in enumerate(review_candidates[:plan["budget"]["review_max"]]):
        if len(N.ROWS) >= plan["budget"]["total_max"]:
            break
        folder = ROOT / q["folder"]
        code = (folder / "model.v").read_text(encoding="utf-8")
        rr = N.run(T12 / "reviews" / str(i), code, [dict(
            pair_index=q["pair_index"], kind="review", pattern=q["pattern"],
            prove=q["prove"], args=q["args"], original_status=q["status"])])[0]
        reviews.append(dict(pair_index=q["pair_index"], kind=q["kind"],
                            original=q["status"], review=rr["status"],
                            agree=int(q["status"] == rr["status"]),
                            folder=rr["folder"]))
    pd.DataFrame(reviews).to_csv(T12 / "reviews.csv", index=False,
                                 encoding="utf-8-sig")
    pd.DataFrame(N.ROWS).to_csv(T12 / "queries.csv", index=False,
                                encoding="utf-8-sig")
    pd.DataFrame(outcomes).to_csv(T12 / "outcomes.csv", index=False,
                                  encoding="utf-8-sig")
    pd.DataFrame(sync).to_csv(T12 / "correspondence.csv", index=False,
                              encoding="utf-8-sig")
    (T12 / "aligned_tables.json").write_text(
        json.dumps(tables, ensure_ascii=False, indent=2), encoding="utf-8")
    (T12 / "context.json").write_text(json.dumps(context, ensure_ascii=False,
                                                  indent=2), encoding="utf-8")
    # Verify every saved query is bound to model/script/log and its exact args.
    binding = []
    for q in N.ROWS:
        f = ROOT / q["folder"]
        qlog = f / f"{q['query_id']}.query.log"
        ok = (f.exists() and (f / "model.v").exists()
              and (f / "run.ys").exists() and (f / "run.log").exists()
              and qlog.exists())
        ok = ok and N.sha(f / "model.v") == q["model_sha"]
        ok = ok and hashlib.sha256((f / "run.ys").read_text(
            encoding="utf-8").encode()).hexdigest() == q["script_sha"]
        ok = ok and N.sha(f / "run.log") == q["log_sha"]
        ok = ok and qlog.read_text(encoding="utf-8").splitlines()[0] == q["args"]
        binding.append(dict(query_id=q["query_id"], folder=q["folder"], ok=int(ok)))
    pd.DataFrame(binding).to_csv(T12 / "binding_audit.csv", index=False,
                                 encoding="utf-8-sig")
    manifest = dict(
        plan_sha256=sha, created=plan["created"], selected=len(selected),
        statuses=pd.Series([o["status"] for o in outcomes]).value_counts().to_dict(),
        complete_pairs=int((pd.Series([o["status"] for o in outcomes])
                            == "paired_validated").sum()),
        correspondence_queries=kind_used("boundary_equivalence"),
        table_queries=kind_used("aligned_source") + kind_used("aligned_partner"),
        po_d_queries=kind_used("PO_D_equivalence"),
        review_queries=len(reviews), review_agree=int(sum(r["agree"] for r in reviews)),
        total_queries=len(N.ROWS), budget=plan["budget"],
        all_binding_ok=int(pd.DataFrame(binding).ok.all()),
        training_runs=0, test_used=False,
        note=("conditional correspondence only; no label transfer, no hidden embedding, "
              "no global full-circuit equivalence beyond observed PO/D"))
    (T12 / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False,
                                                   indent=2), encoding="utf-8")
    (T12 / "pair_acceptance_policy.json").write_text(json.dumps(dict(
        training_approved=False, training_loader_compatible=False,
        old_P1_proved_is_locator_only=True,
        same_temporary_name_is_not_a_correspondence=True,
        correspondence_failure_is_not_feature_instability=True,
        labels_must_not_be_transferred=True,
        graph_coverage_gain_not_claimed=True), indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())