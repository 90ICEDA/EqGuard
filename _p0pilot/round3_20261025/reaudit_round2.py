"""Re-audit round-2 graded relations with the corrected state model.

Reads the saved round-2 SAT logs and CSV only; no new queries.
Outputs a per-relation legacy-vs-corrected status table and a per-query table.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import itertools
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "_p0pilot/round3_20261025"))
from sat_evidence import evaluate_case  # noqa: E402

EXT = ROOT / "_p0pilot/round2_20261025/extraction"
OUT = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"


def parse_blocks(out: str) -> dict[int, str]:
    blocks: dict[int, list[str]] = {}
    cur = None
    for line in out.splitlines():
        m = re.match(r"^QRY(\d{5})$", line.strip())
        if m:
            cur = int(m.group(1))
            blocks[cur] = []
            continue
        if cur is None:
            continue
        if "no model found: SUCCESS" in line:
            blocks[cur].append("proved")
        elif "model found: FAIL" in line:
            blocks[cur].append("refuted")
        elif "TIMEOUT" in line:
            blocks[cur].append("timeout")
        elif line.startswith("ERROR"):
            blocks[cur].append("error")
    return {k: (v[0] if v else "no_result") for k, v in blocks.items()}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    for name in ("graded_graded_main.csv", "graded_graded_val_ysid.csv"):
        d = pd.read_csv(EXT / name, encoding="utf-8-sig")
        d = d[pd.to_numeric(d["n_patterns"], errors="coerce").fillna(0) > 0]
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    logs = {}
    rows, qrows = [], []
    for _, r in d.iterrows():
        logp = ROOT / str(r["log"])
        if str(r["log"]) not in logs:
            logs[str(r["log"])] = parse_blocks(
                logp.read_text(encoding="utf-8", errors="replace")) if logp.exists() else {}
        statuses = logs[str(r["log"])]
        cut = [x for x in str(r["cut_nets"]).split(";") if x]
        patterns = list(itertools.product([0, 1], repeat=len(cut)))
        qids = [int(x) for x in str(r["query_ids"]).split(";") if x]
        assert len(qids) == 2 * len(patterns), (r["design"], len(qids), len(patterns))
        new = evaluate_case(cut, patterns, qids, statuses,
                            structure=str(r.get("cut_structure", "unknown")))
        row = dict(design=r["design"], role=r["role"], kind=r["kind"],
                   target=r["target"], target_id=f"{r['design']}|{r.get('driver','')}|{r['target']}",
                   cut_nets=r["cut_nets"], cut_size=len(cut),
                   legacy_status=r["status"], corrected_sufficiency=new["functional_sufficiency"],
                   sufficiency_reason=new["sufficiency_reason"],
                   n_patterns=new["n_patterns"], n_feasible=new["n_feasible"],
                   n_infeasible=new["n_infeasible"], n_undecided=new["n_undecided"],
                   n_forced=new["n_forced"], determinism_ratio=new["determinism_ratio"],
                   query_status=new["query_status"],
                   influence_status=new["influence_status"],
                   influence_mean=new["influence_mean"], influence_max=new["influence_max"],
                   n_valid_influence_inputs=new["n_valid_influence_inputs"],
                   influence_per_input=new["influence_per_input"],
                   forcing_patterns=new["forcing_patterns"], log=r["log"])
        rows.append(row)
        for i, pat in enumerate(patterns):
            for j, direction in ((0, 1), (1, 0)):
                qid = qids[2 * i + j]
                qrows.append(dict(design=r["design"], target=r["target"],
                                  pattern="".join(str(b) for b in pat),
                                  prove=direction, query_id=qid,
                                  raw_status=statuses.get(qid, "no_result")))
    rel = pd.DataFrame(rows)
    rel.to_csv(OUT / "round2_reaudit_relations.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(qrows).to_csv(OUT / "round2_reaudit_queries.csv", index=False,
                               encoding="utf-8-sig")
    print(rel[["design", "target", "legacy_status", "corrected_sufficiency",
               "n_feasible", "n_forced", "n_undecided", "influence_status",
               "influence_mean"]].to_string(index=False), flush=True)
    print("\nlegacy vs corrected:\n",
          pd.crosstab(rel["legacy_status"], rel["corrected_sufficiency"]).to_string(),
          flush=True)
    print("\nlegacy complete but not proved:",
          int(((rel.legacy_status == "complete") &
               (rel.corrected_sufficiency != "proved")).sum()), flush=True)
    info = dict(relations=len(rel), queries=len(qrows),
                legacy_complete=int((rel.legacy_status == "complete").sum()),
                corrected_proved=int((rel.corrected_sufficiency == "proved").sum()),
                corrected_not_proved=int((rel.corrected_sufficiency == "not_proved").sum()),
                influence_valid=int((rel.influence_status == "valid").sum()),
                influence_not_applicable=int((rel.influence_status == "not_applicable").sum()))
    (OUT / "round2_reaudit_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
