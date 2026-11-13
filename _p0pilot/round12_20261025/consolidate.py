"""Consolidate round-12 evidence without inventing any successful pair."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
T12 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round12"
T11 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round11"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pair_of(folder: Path):
    parts = folder.relative_to(T12).parts
    if parts[0] == "pairs":
        return int(parts[1])
    if parts[0] == "polarity":
        return int(parts[1].split("_")[0][1:])
    if parts[0] == "retry_u58":
        return 2
    return None


def main() -> int:
    if (T12 / "queries.csv").exists():
        raise RuntimeError("refuse to overwrite queries.csv")
    plan = json.loads((T12 / "plan.json").read_text(encoding="utf-8"))
    rows = []
    for qlog in sorted(T12.rglob("*.query.log")):
        folder = qlog.parent
        qid = int(qlog.name.split(".")[0])
        lines = qlog.read_text(encoding="utf-8", errors="replace").splitlines()
        args = lines[0]
        text = "\n".join(lines[1:])
        status = ("proved" if "no model found: SUCCESS" in text else
                  "refuted" if "model found: FAIL" in text else "unknown")
        m = re.search(r"delta(?:_inv)?\[(\d+)\]", args)
        rows.append(dict(
            pair_index=pair_of(folder),
            kind=("polarity_check" if "polarity" in folder.parts
                  else "boundary_equivalence"),
            pattern=m.group(1) if m else "", prove=0, args=args, status=status,
            timeout=False, query_id=qid, folder=str(folder.relative_to(ROOT)),
            model_sha=sha(folder / "model.v"),
            script_sha=hashlib.sha256((folder / "run.ys").read_text(
                encoding="utf-8").encode()).hexdigest(),
            log_sha=sha(folder / "run.log"),
            witness=str((folder / f"{qid}.model.json").relative_to(ROOT))
            if (folder / f"{qid}.model.json").exists() else "",
            batch_id=12))
    if len(rows) != 17:
        raise RuntimeError(f"expected 17 queries, found {len(rows)}")
    d = pd.DataFrame(rows).sort_values(["pair_index", "query_id"])
    d.to_csv(T12 / "queries.csv", index=False, encoding="utf-8-sig")
    binding = []
    for r in d.itertuples():
        f = ROOT / r.folder
        qlog = f / f"{r.query_id}.query.log"
        ok = (sha(f / "model.v") == r.model_sha
              and hashlib.sha256((f / "run.ys").read_text(
                  encoding="utf-8").encode()).hexdigest() == r.script_sha
              and sha(f / "run.log") == r.log_sha
              and qlog.read_text(encoding="utf-8").splitlines()[0] == r.args)
        binding.append(dict(folder=r.folder, query_id=r.query_id, ok=int(ok)))
    pd.DataFrame(binding).to_csv(T12 / "binding_audit.csv", index=False,
                                 encoding="utf-8-sig")

    status = {i: d[d.pair_index == i] for i in range(4)}
    outcomes = []
    for i, item in enumerate(plan["selected"]):
        part = status[i]
        proved = part[part.status == "proved"]
        failed = part[part.status != "proved"]
        outcomes.append(dict(
            pair_index=i, relation_id=item["relation_id"], role=item["role"],
            source_view=item["source_view"], partner_view=item["partner"],
            status="boundary_not_proved" if len(failed) else "no_queries",
            failed_slot=int(failed.iloc[-1]["pattern"]) if len(failed) else None,
            partial_slot_proofs=int(len(proved)), queries=len(part)))
    pd.DataFrame(outcomes).to_csv(T12 / "outcomes.csv", index=False,
                                  encoding="utf-8-sig")
    cov = pd.read_csv(T11 / "pair_coverage_40.csv", encoding="utf-8-sig")
    cov["round12_action"] = ""
    for item in plan["selected"]:
        cov.loc[cov.relation_id == item["relation_id"], "round12_action"] = "mapping_attempted"
    cov.to_csv(T12 / "pair_coverage_40_round12.csv", index=False,
               encoding="utf-8-sig")
    vp = json.loads((T11 / "validated_pairs_cumulative.json").read_text(
        encoding="utf-8"))
    (T12 / "validated_pairs_cumulative_round12.json").write_text(
        json.dumps(dict(pairs=vp, count=len(vp), round12_new=0,
                        note="no new complete pair; existing 11 unchanged"),
                   ensure_ascii=False, indent=2), encoding="utf-8")
    audit = json.loads((T12 / "blocker_audit.json").read_text(encoding="utf-8"))
    ss = {}
    for r in audit:
        for view, snap, sh in ((r["source_view"], r["source_snapshot"], r["source_sha"]),
                               (r["partner"], r["partner_snapshot"], r["partner_sha"])):
            if view and snap:
                ss[view] = dict(view=view, snapshot=snap, source_sha=sh)
    pd.DataFrame(ss.values()).to_csv(T12 / "source_snapshots.csv", index=False,
                                     encoding="utf-8-sig")
    manifest = dict(
        plan_sha256=plan["plan_sha256"], created=plan["created"],
        selected=len(plan["selected"]), complete_pairs=0,
        partial_slot_proofs=int((d.status == "proved").sum()),
        queries=len(d), statuses=d.status.value_counts().to_dict(),
        correspondence_queries=len(d), table_queries=0, review_queries=0,
        total_queries=len(d), budget=plan["budget"],
        all_binding_ok=int(pd.DataFrame(binding).ok.all()),
        blockers_audited=29, category_counts={
            "temporary_alias_correspondence_unproved": 18,
            "boundary_correspondence_unproved": 1,
            "candidate_mapping_incomplete": 8,
            "local_alias_unavailable": 2},
        training_runs=0, test_used=False,
        note=("mapping-only; 5 partial slot proofs are not full pairs; "
              "no table or review was run because no boundary-complete pair"))
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