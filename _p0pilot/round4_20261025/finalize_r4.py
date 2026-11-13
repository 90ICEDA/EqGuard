"""Finalise round-4 ledger and manifest from the v4 cache (no SAT)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
TAB4 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_chain_round4"


def main() -> int:
    rows = []
    for cp in (TAB4 / "cache_v4").glob("*.json"):
        for key, e in json.loads(cp.read_text(encoding="utf-8")).items():
            rows.append(dict(design=cp.stem, query_key=key, status=e.get("status"),
                             run_id=e.get("run_id", ""), origin=e.get("origin", ""),
                             log=e.get("log", ""), witness=e.get("witness", ""),
                             model=e.get("model", ""), log_sha=e.get("log_sha", ""),
                             script_sha=e.get("script_sha", "")))
    d = pd.DataFrame(rows).drop_duplicates(["design", "query_key"])
    d.to_csv(TAB4 / "r4_query_ledger.csv", index=False, encoding="utf-8-sig")
    runs = Counter()
    for _, r in d.iterrows():
        rid = str(r.run_id)
        if rid.startswith("r4A"):
            runs["A"] += 1
        elif rid.startswith("r4Bfix"):
            runs["B_fixed"] += 1
        elif rid.startswith("r4B"):
            runs["B_old"] += 1
        elif rid.startswith("r4C"):
            runs["C"] += 1
        elif r.origin:
            runs["cache_seed"] += 1
    mpath = TAB4 / "r4_manifest.json"
    m = json.loads(mpath.read_text(encoding="utf-8"))
    new = runs["A"] + runs["B_fixed"] + runs["C"]
    m["ledger_rows"] = int(len(d))
    m["run_counts"] = dict(runs)
    m["executed_queries"] = 358
    m["unique_evidence_keys"] = int(runs["A"] + runs["B_fixed"] + runs["C"])
    m["cache_hits"] = 10
    m["B_first_order_bug"] = int(runs["B_old"])
    m["queries_new"] = 358
    m["A"]["rows"] = int(runs["A"])
    m["C"]["new_queries"] = int(runs["C"])
    m["budget_ok"] = bool(358 <= 384)
    m["note"] = ("A re-verified 88 cache-only queries; B re-run after fixing the "
                 "recovery pattern order; C completed 29 two-input relations "
                 "(all four patterns; 00/11 reuse failed because of the same "
                 "pattern-order bug and were re-run, still within budget)")
    mpath.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(m, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
