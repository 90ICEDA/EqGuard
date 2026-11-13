"""Round-4 batches: cache-only re-verification, replay audit, two-input completion.

Plan is written before any query. Reuses the 00/11 queries already traced to
round-3 sidecars; only 01/10 are new for the 29 two-input relations.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import itertools
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
WORK = ROOT / "generate_trans/folds/hosts_bt31"
R3 = ROOT / "_p0pilot/round3_20261025"
R4 = ROOT / "_p0pilot/round4_20261025"
TAB3 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"
TAB4 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_chain_round4"
sys.path.insert(0, str(R3))
sys.path.insert(0, str(R4))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402
from r4_runner import digest, query_key, run_batch  # noqa: E402
from sat_evidence_v4 import evaluate_case_v4, normalize_cut  # noqa: E402


def load_netbits(design: str) -> dict:
    raw = R3 / "struct_raw" / (Path(design).stem + ".json")
    mods = json.loads(raw.read_text(encoding="utf-8"))["modules"]
    mod = next(iter(mods.values()))
    nb = {nm: tuple(b for b in info.get("bits", []) if isinstance(b, int))
          for nm, info in mod.get("netnames", {}).items()}
    for nm, p in mod.get("ports", {}).items():
        nb[nm] = tuple(b for b in p.get("bits", []) if isinstance(b, int))
    return nb


def pattern_rows(rel_row, qsub) -> list[dict]:
    k = int(rel_row.cut_size)
    if str(rel_row.get("source", "")) == "recovery":
        # round-3 recovery used all-1 then all-0, in that row order
        pats = ["1" * k, "0" * k]
    else:
        pats = ["".join(str(b) for b in p)
                for p in itertools.product([0, 1], repeat=k)]
    rows = []
    for i, (_, qr) in enumerate(qsub.reset_index(drop=True).iterrows()):
        rows.append(dict(pattern=pats[i // 2], prove=int(i % 2 == 0),
                         status=qr.status, query_key=qr.query_key))
    return rows


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-only", action="store_true")
    args = ap.parse_args()
    rel = pd.concat([
        pd.read_csv(TAB3 / "r3_recovery_relations.csv", encoding="utf-8-sig")
        .assign(source="recovery"),
        pd.read_csv(TAB3 / "r3_graded_relations.csv", encoding="utf-8-sig")
        .assign(source="graded")], ignore_index=True)
    q = pd.concat([
        pd.read_csv(TAB3 / "r3_recovery_queries.csv", encoding="utf-8-sig",
                    dtype={"pattern": str}).assign(source="recovery"),
        pd.read_csv(TAB3 / "r3_graded_queries.csv", encoding="utf-8-sig",
                    dtype={"pattern": str}).assign(source="graded")],
        ignore_index=True)
    sidecar = set()
    for p in (R3 / "logs").glob("*.keys.json"):
        sidecar.update(json.loads(p.read_text(encoding="utf-8")).values())
    q["in_sidecar"] = q.query_key.isin(sidecar)

    plan = dict(created=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                budget=dict(max_queries=384, query_timeout_s=5, wall_cap_min=30,
                            max_cacheonly=88, max_replay=24, max_two_input_new=116),
                cacheonly=0, replay=0, two_input_new=0, two_input_reuse=0,
                expected_total=0)
    # ---- A: cache-only queries (graded only) ----
    miss = q[(q.source == "graded") & (~q.in_sidecar)]
    plan["cacheonly"] = int(len(miss))
    # ---- B: replay sample (first 2 relations per design) ----
    rrel = rel[rel.source == "recovery"].sort_values(["design", "relation_id"])
    picked = []
    for _, g in rrel.groupby("design"):
        picked += list(g.head(2).relation_id)
    plan["replay"] = int(2 * len(picked))
    # ---- C: two-input completion ----
    two = rrel[rrel.cut_size == 2]
    plan["two_input_relations"] = int(len(two))
    plan["two_input_new"] = int(len(two) * 4)
    plan["two_input_reuse"] = int(len(two) * 4)
    plan["expected_total"] = (plan["cacheonly"] + plan["replay"] +
                              plan["two_input_new"])
    (TAB4 / "r4_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if args.plan_only:
        return 0

    t0 = time.perf_counter()
    deadline = t0 + plan["budget"]["wall_cap_min"] * 60
    ledger = []
    counts = dict(cache_hits=0, new_solves=0, retries=0, timeouts=0, errors=0)
    # ---------- A: re-verify cache-only graded queries ----------
    miss = q[(q.source == "graded") & (~q.in_sidecar)].copy()
    by_design = defaultdict(list)
    meta_of = {}
    for _, r in miss.iterrows():
        rr = rel[rel.relation_id == r.relation_id].iloc[0]
        qsub = q[q.relation_id == r.relation_id]
        prs = pattern_rows(rr, qsub)
        got = [p for p in prs if p["query_key"] == r.query_key]
        if not got:
            raise SystemExit(f"cannot map query to pattern: {r.query_key}")
        pr = got[0]
        nb = load_netbits(str(rr.design))
        canon = normalize_cut([c for c in str(rr.cut_nets).split(";") if c],
                              nb, str(rr.target))
        cut = [c["name"] for c in canon["canonical"]]
        key = query_key(WORK / "trans" / str(rr.design), cut, str(rr.target),
                        pr["pattern"], pr["prove"], 3)
        meta_of[r.query_key] = dict(design=str(rr.design), cut=cut,
                                    target=str(rr.target), pattern=pr["pattern"],
                                    prove=pr["prove"], before=r.status,
                                    key_match=int(key == r.query_key))
        if key != r.query_key:
            continue
        by_design[str(rr.design)].append(dict(
            cut=cut, target=str(rr.target), pattern=pr["pattern"],
            prove=pr["prove"], query_key=r.query_key,
            _ports=set(), relation_id=r.relation_id))
    a_rows = []
    for design, cases in by_design.items():
        if time.perf_counter() > deadline or counts["new_solves"] >= plan["budget"]["max_queries"]:
            break
        mods = json.loads((R3 / "struct_raw" / (Path(design).stem + ".json"))
                          .read_text(encoding="utf-8"))["modules"]
        ports = set(next(iter(mods.values()))["ports"].keys())
        for c in cases:
            c["_ports"] = ports
        res = run_batch(WORK / "trans" / design, P0.module_name(WORK / "trans" / design),
                        cases, "r4A_cacheonly", TAB4, force=True, timeout=3)
        counts["new_solves"] += res["new"]
        counts["timeouts"] += res["timeouts"]
        counts["errors"] += res["errors"]
        for c in cases:
            m = meta_of[c["query_key"]]
            after = res["statuses"][c["query_key"]]
            a_rows.append(dict(query_key=c["query_key"], design=design,
                               relation_id=c["relation_id"], cut_nets=";".join(c["cut"]),
                               target=c["target"], pattern=c["pattern"],
                               prove=c["prove"], key_match=m["key_match"],
                               status_before=m["before"], status_after=after,
                               same=int(after == m["before"]),
                               log=res["log"], run_id="r4A_cacheonly"))
    pa = pd.DataFrame(a_rows)
    if pa.empty:
        pa = pd.DataFrame(columns=["query_key", "design", "relation_id", "cut_nets",
                                   "target", "pattern", "prove", "key_match",
                                   "status_before", "status_after", "same",
                                   "log", "run_id"])
    missing_rows = [r for _, r in miss.iterrows() if r.query_key not in set(pa.query_key)]
    for r in missing_rows:
        m = meta_of[r.query_key]
        reason = ("not_run_key_mismatch" if m["key_match"] == 0
                  else "skipped_budget_or_wall")
        pa = pd.concat([pa, pd.DataFrame([dict(
            query_key=r.query_key, design=m["design"], relation_id=r.relation_id,
            cut_nets=";".join(m["cut"]), target=m["target"], pattern=m["pattern"],
            prove=m["prove"], key_match=m["key_match"], status_before=m["before"],
            status_after=reason, same=0, log="", run_id="")])],
            ignore_index=True)
    pa.to_csv(TAB4 / "r4_cacheonly_queries.csv", index=False, encoding="utf-8-sig")
    print(f"[A] planned={len(miss)} executed={len(pa)} "
          f"same={int(pa.same.sum())} key_match={int(pa.key_match.sum())}", flush=True)
    counts["new_solves"] += 0

    # ---------- B: replay audit with corrected pattern strings ----------
    b_rows = []
    for rid in picked:
        if time.perf_counter() > deadline or counts["new_solves"] >= plan["budget"]["max_queries"]:
            break
        rr = rel[rel.relation_id == rid].iloc[0]
        qsub = q[q.relation_id == rid]
        prs = pattern_rows(rr, qsub)
        nb = load_netbits(str(rr.design))
        canon = normalize_cut([c for c in str(rr.cut_nets).split(";") if c],
                              nb, str(rr.target))
        cut = [c["name"] for c in canon["canonical"]]
        mods = json.loads((R3 / "struct_raw" / (Path(str(rr.design)).stem + ".json"))
                          .read_text(encoding="utf-8"))["modules"]
        ports = set(next(iter(mods.values()))["ports"].keys())
        for st in ("proved", "refuted"):
            cand = [p for p in prs if p["status"] == st]
            if not cand:
                continue
            pr = cand[0]
            key = query_key(WORK / "trans" / str(rr.design), cut, str(rr.target),
                            pr["pattern"], pr["prove"], 5)
            case = dict(cut=cut, target=str(rr.target), pattern=pr["pattern"],
                        prove=pr["prove"], query_key=key, _ports=ports)
            res = run_batch(WORK / "trans" / str(rr.design),
                            P0.module_name(WORK / "trans" / str(rr.design)),
                            [case], f"r4B_{key[:10]}", TAB4, force=True, timeout=5)
            after = res["statuses"][key]
            counts["new_solves"] += res["new"]
            counts["timeouts"] += res["timeouts"]
            counts["errors"] += res["errors"]
            b_rows.append(dict(relation_id=rid, design=str(rr.design),
                               target=str(rr.target), cut_nets=";".join(cut),
                               pattern=pr["pattern"], prove=pr["prove"],
                               stored_key=pr["query_key"], replayed_key=key,
                               key_equal=int(key == pr["query_key"]),
                               cut_equal=int(cut == [c for c in str(rr.cut_nets).split(";") if c]),
                               stored_status=pr["status"], replayed_status=after,
                               status_equal=int(after == pr["status"]),
                               seq=1, timeout=5,
                               source_sha=digest(WORK / "trans" / str(rr.design)),
                               log=res["log"]))
    pb = pd.DataFrame(b_rows)
    pb.to_csv(TAB4 / "r4_replay_audit.csv", index=False, encoding="utf-8-sig")
    print(f"[B] selected={len(pb)} key_equal={int(pb.key_equal.sum())} "
          f"status_equal={int(pb.status_equal.sum())}", flush=True)

    # ---------- C: complete the 29 two-input relations ----------
    two = rrel[rrel.cut_size == 2].copy()
    c_rows, truth_rows, led = [], [], []
    for _, rr in two.iterrows():
        if time.perf_counter() > deadline or counts["new_solves"] >= plan["budget"]["max_queries"]:
            c_rows.append(dict(relation_id=rr.relation_id, design=str(rr.design),
                               target=rr.target, status="skipped_budget_or_wall",
                               new_queries=0))
            continue
        design = str(rr.design)
        v = WORK / "trans" / design
        nb = load_netbits(design)
        canon = normalize_cut([c for c in str(rr.cut_nets).split(";") if c],
                              nb, str(rr.target))
        cut = [c["name"] for c in canon["canonical"]]
        if not canon["ok"] or len(cut) != 2:
            c_rows.append(dict(relation_id=rr.relation_id, design=design,
                               target=rr.target, status="not_two_input_after_norm",
                               cut_canonical=";".join(cut), new_queries=0))
            continue
        qsub = q[q.relation_id == rr.relation_id]
        prs = pattern_rows(rr, qsub)
        old = {p["pattern"] + ":" + str(p["prove"]): p for p in prs}
        mods = json.loads((R3 / "struct_raw" / (Path(design).stem + ".json"))
                          .read_text(encoding="utf-8"))["modules"]
        ports = set(next(iter(mods.values()))["ports"].keys())
        pats = ["".join(str(b) for b in p) for p in itertools.product([0, 1], repeat=2)]
        keys = [query_key(v, cut, str(rr.target), p, prove, 5)
                for p in pats for prove in (1, 0)]
        # seed 00/11 from the round-3 sidecar-verified queries
        cache_path = TAB4 / "cache_v4" / f"{v.stem}.json"
        cache = (json.loads(cache_path.read_text(encoding="utf-8"))
                 if cache_path.exists() else {})
        seeded = 0
        for p in ("00", "11"):
            for prove in (1, 0):
                o = old.get(f"{p}:{prove}")
                if o is None:
                    continue
                k = query_key(v, cut, str(rr.target), p, prove, 5)
                if k == o["query_key"]:
                    cache[k] = dict(status=o["status"], run_id="r3_sidecar",
                                    origin="round3_verified_sidecar",
                                    log=str(rr.log), retryable=False)
                    seeded += 1
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        cases = [dict(cut=cut, target=str(rr.target), pattern=p, prove=prove,
                      query_key=k, _ports=ports)
                 for p, prove, k in zip([x for x in pats for _ in (1, 0)],
                                        [1, 0, 1, 0, 1, 0, 1, 0], keys)]
        res = run_batch(v, P0.module_name(v), cases, "r4C_two_input", TAB4,
                        force=False, timeout=5)
        counts["cache_hits"] += res["hits"]
        counts["new_solves"] += res["new"]
        counts["retries"] += res["retries"]
        counts["timeouts"] += res["timeouts"]
        counts["errors"] += res["errors"]
        stat = {i + 1: res["statuses"][keys[i]] for i in range(8)}
        ev = evaluate_case_v4(cut, pats, list(range(1, 9)), stat,
                              cut_meta=dict(original=[c for c in str(rr.cut_nets).split(";") if c]))
        row = dict(relation_id=rr.relation_id, design=design, role=rr.role,
                   host=rr.host, recipe=rr.recipe, kind=rr.kind, target=rr.target,
                   cut_canonical=";".join(cut), old_sufficiency=rr.functional_sufficiency,
                   seeded_queries=seeded, new_queries=res["new"],
                   cache_hits=res["hits"], run_id="r4C_two_input")
        row.update({k: ev[k] for k in (
            "enum_complete", "enum_reason", "enum_expected", "enum_observed",
            "n_feasible", "n_infeasible", "n_forced", "n_undecided",
            "n_premise_feasible_known", "determinism_ratio",
            "functional_sufficiency", "sufficiency_reason", "query_status",
            "truth_table", "influence_status", "influence_mean",
            "influence_max", "n_valid_influence_inputs")})
        c_rows.append(row)
        for i, p in enumerate(pats):
            for j, prove in enumerate((1, 0)):
                k = keys[2 * i + j]
                ent = json.loads(cache_path.read_text(encoding="utf-8")).get(k, {})
                truth_rows.append(dict(relation_id=rr.relation_id, design=design,
                                       target=rr.target, pattern=p, prove=prove,
                                       status=res["statuses"][k], query_key=k,
                                       origin=ent.get("origin", "r4C_new"),
                                       log=ent.get("log", ""),
                                       witness=ent.get("witness", "")))
    pc = pd.DataFrame(c_rows)
    pc.to_csv(TAB4 / "r4_two_input_relations.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(truth_rows).to_csv(TAB4 / "r4_two_input_truth.csv", index=False,
                                    encoding="utf-8-sig")
    print(f"[C] relations={len(pc)} proved={int((pc.functional_sufficiency == 'proved').sum())} "
          f"not_proved={int((pc.functional_sufficiency == 'not_proved').sum())} "
          f"hits={counts['cache_hits']} new={counts['new_solves']}", flush=True)

    led = []
    for cp in (TAB4 / "cache_v4").glob("*.json"):
        for key, e in json.loads(cp.read_text(encoding="utf-8")).items():
            if not (str(e.get("run_id", "")).startswith(("r4A", "r4B", "r4C"))
                    or e.get("origin")):
                continue
            led.append(dict(design=cp.stem, query_key=key, status=e.get("status"),
                            run_id=e.get("run_id", ""), origin=e.get("origin", "r4"),
                            log=e.get("log", ""), witness=e.get("witness", ""),
                            model=e.get("model", ""),
                            log_sha=e.get("log_sha", ""),
                            script_sha=e.get("script_sha", "")))
    pl = pd.DataFrame(led)
    pl.drop_duplicates(["design", "query_key"], inplace=True)
    pl.to_csv(TAB4 / "r4_query_ledger.csv", index=False, encoding="utf-8-sig")
    manifest = dict(
        plan=plan, wall_s=round(time.perf_counter() - t0, 1),
        counts=counts, queries_new=int(counts["new_solves"]),
        cache_hits=int(counts["cache_hits"]), retries=int(counts["retries"]),
        budget_ok=bool(counts["new_solves"] <= plan["budget"]["max_queries"]),
        A=dict(planned=int(len(miss)), rows=int(len(pa)),
               same=int(pa.same.sum()), key_match=int(pa.key_match.sum()),
               not_run=int((pa.status_after == "not_run_key_mismatch").sum())),
        B=dict(selected=int(len(pb)), key_equal=int(pb.key_equal.sum()),
               cut_equal=int(pb.cut_equal.sum()),
               status_equal=int(pb.status_equal.sum())),
        C=dict(relations=int(len(pc)),
               proved=int((pc.functional_sufficiency == "proved").sum()),
               not_proved=int((pc.functional_sufficiency == "not_proved").sum()),
               enum_complete=int(pc.enum_complete.sum()) if len(pc) else 0),
        ledger_rows=int(len(pl)), ledger_duplicate_rows=int(len(led) - len(pl)),
        allowed_roles=["train", "val"], test_used=False)
    (TAB4 / "r4_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2), flush=True)
    return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
