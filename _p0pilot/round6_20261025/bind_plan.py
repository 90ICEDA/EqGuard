"""Bind the frozen plan hash to actual execution ids and query counts."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import hashlib
import json
from pathlib import Path

ROOT = Path(_eqguard_path(''))
TAB6 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_expand_round6"


def main() -> int:
    plan = json.loads((TAB6 / "r6_candidate_plan.json").read_text(encoding="utf-8"))
    sha = plan.pop("plan_sha256")
    check = hashlib.sha256(json.dumps(plan, ensure_ascii=False,
                                      sort_keys=True).encode()).hexdigest()
    mani = json.loads((TAB6 / "r6_nonlocal_manifest.json").read_text(encoding="utf-8"))
    rev = json.loads((TAB6 / "r6_review_manifest.json").read_text(encoding="utf-8"))
    out = dict(created=plan["created"], plan_sha256=sha,
               plan_hash_recheck=check, plan_hash_ok=int(check == sha),
               frozen_relations=plan["relations"],
               expected_queries=plan["expected_queries"],
               actual_expansion_queries=mani["queries"],
               review_queries=rev["queries"],
               total_solves=mani["queries"] + rev["queries"],
               executions=mani["executions"],
               review_execution_note="separate out_root review/cache; no overwrite",
               joint_pilot=dict(budget=16, used=0,
                                status="not_completed; conditional wording retained"))
    (TAB6 / "r6_plan_binding.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())