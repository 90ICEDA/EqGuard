"""Low-cost round-4 corrections and legacy ledger audit (no SAT rerun)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
TAB4 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_chain_round4"
TAB5 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_nonlocal_round5"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def main() -> int:
    u = pd.read_csv(TAB4 / "r4_unified_relations.csv", encoding="utf-8-sig")
    tf = pd.read_csv(TAB4 / "r4_truth_functions.csv", encoding="utf-8-sig")
    ge = pd.read_csv(TAB4 / "r4_gate_explain.csv", encoding="utf-8-sig")
    d = u.merge(tf[["relation_id", "function_sig", "feasibility_sig"]],
                on="relation_id", how="left")
    d = d.merge(ge[["relation_id", "checked", "matched", "mismatched", "explained"]],
                on="relation_id", how="left")
    # feasibility variation within the same (gate, cut size), independent of pattern labels
    grp = d.groupby(["driver_type", "cut_size"])[
        "feasibility_sig"].nunique().rename("group_feasibility_count").reset_index()
    d = d.merge(grp, on=["driver_type", "cut_size"], how="left")
    d["output_function_matched"] = d.explained.apply(
        lambda x: "yes" if x == 1 else ("no" if x == 0 else "not_evaluated"))

    def truth_name(tt: str) -> str:
        names = {"0001": "AND2", "0111": "OR2", "0110": "XOR2",
                 "1110": "NAND2", "1000": "NOR2", "1001": "XNOR2"}
        vals = []
        for item in str(tt).split(";"):
            p, feas, force = item.split(":")
            if feas == "feasible" and force in ("0", "1"):
                vals.append(force)
            else:
                vals.append("-")
        return names.get("".join(vals), "custom_or_incomplete")

    d["truth_function_name"] = d.truth_table.map(truth_name)
    d["feasibility_varies_in_group"] = (d.group_feasibility_count > 1).astype(int)
    d["conditional_influence"] = (d.influence_status == "valid").astype(int)
    d["has_infeasible_pattern"] = d.feasibility_sig.str.contains(
        "infeasible", na=False).astype(int)

    def interp(r):
        if r.output_function_matched == "yes":
            return "direct_gate_function"
        if r.truth_function_name != "custom_or_incomplete":
            return f"not_direct_gate_function_observed_{r.truth_function_name}"
        if r.output_function_matched == "not_evaluated":
            return "not_evaluated_cut_arity_mismatch"
        return "not_direct_gate_function"

    d["interpretation"] = d.apply(interp, axis=1)
    d[["relation_id", "design", "target", "driver_type", "cut_size", "source",
       "output_function_matched", "truth_function_name", "has_infeasible_pattern",
       "feasibility_varies_in_group", "conditional_influence",
       "function_sig", "feasibility_sig", "interpretation"]].to_csv(
        TAB5 / "r5_round4_corrections.csv", index=False, encoding="utf-8-sig")
    print(d.groupby(["source", "interpretation"]).size().to_string(), flush=True)
    print("recovery function matched", int(((d.source != "graded") &
          (d.output_function_matched == "yes")).sum()), flush=True)
    print("recovery feasibility varies", int(((d.source != "graded") &
          (d.feasibility_varies_in_group == 1)).sum()), flush=True)
    print("recovery has infeasible pattern", int(((d.source != "graded") &
          (d.has_infeasible_pattern == 1)).sum()), flush=True)
    print("recovery influence valid", int(((d.source != "graded") &
          (d.conditional_influence == 1)).sum()), flush=True)
    g = d[d.target == "g26104"]
    print("\ng26104:\n", g[["design", "driver_type", "truth_table",
                            "truth_function_name", "interpretation"]]
          .to_string(index=False), flush=True)
    summary = dict(
        recovery_relations=int((d.source != "graded").sum()),
        recovery_output_function_matched=int(((d.source != "graded") &
            (d.output_function_matched == "yes")).sum()),
        recovery_feasibility_varies=int(((d.source != "graded") &
            (d.feasibility_varies_in_group == 1)).sum()),
        recovery_has_infeasible_pattern=int(((d.source != "graded") &
            (d.has_infeasible_pattern == 1)).sum()),
        recovery_influence_valid=int(((d.source != "graded") &
            (d.conditional_influence == 1)).sum()),
        graded_relations=int((d.source == "graded").sum()),
        graded_not_evaluated=int(((d.source == "graded") &
            (d.output_function_matched == "not_evaluated")).sum()),
        g26104_interpretation="NAND2 (1,1,1,0); driver is INVX0, so not the direct gate function",
        note="gate_explain checked=0 means not_evaluated, not unexplainable")
    (TAB5 / "r5_round4_corrections.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

    # ---- legacy ledger audit: batch hash vs current file, per-query log presence ----
    led = pd.read_csv(TAB4 / "r4_query_ledger.csv", encoding="utf-8-sig")
    rows = []
    for _, r in led.iterrows():
        qlog = TAB4 / str(r.log)
        actual_q = sha(qlog)
        recorded = str(r.log_sha) if not pd.isna(r.log_sha) else ""
        batch_dir = qlog.parent
        batch_log = batch_dir / "batch.sat.log"
        actual_b = sha(batch_log)
        if not qlog.exists():
            status = "missing_query_log"
        elif recorded and actual_b == recorded:
            status = "batch_hash_match"
        else:
            status = "per_query_log_present_batch_hash_mismatch"
        rows.append(dict(design=r.design, query_key=r.query_key, run_id=r.run_id,
                         status=status, query_log=str(r.log),
                         query_log_sha=actual_q, recorded_batch_sha=recorded,
                         current_batch_sha=actual_b))
    la = pd.DataFrame(rows)
    la.to_csv(TAB5 / "r5_legacy_ledger_audit.csv", index=False, encoding="utf-8-sig")
    print("\nlegacy ledger:\n", la.status.value_counts().to_string(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
