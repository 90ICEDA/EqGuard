"""Independent re-run of 24 round-6 queries (16 prove=1 + 8 prove=0)."""
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
from r5_evidence import statuses_by_qid  # noqa: E402


def main() -> int:
    plan = json.loads((TAB6 / "r6_candidate_plan.json").read_text(encoding="utf-8"))
    orig = pd.read_csv(TAB6 / "r6_nonlocal_queries.csv", encoding="utf-8-sig")
    orig_st = dict(zip(orig.query_key, orig.status))
    frozen = plan["frozen"]
    picks = []
    for i, r in enumerate(frozen):
        pats = list(r["patterns"])
        picks.append((r, pats[0], 1))
    for r in frozen[:8]:
        picks.append((r, list(r["patterns"])[0], 0))
    t0 = time.perf_counter()
    rows = []
    for design, group in pd.DataFrame([p[0] for p in picks]).groupby("design", sort=False):
        v = WORK / "trans" / design
        top = P0.module_name(v)
        mods = json.loads((R6 / "struct_raw" / f"{Path(design).stem}.json")
                          .read_text(encoding="utf-8"))["modules"]
        idx = build_index(next(iter(mods.values())))
        ports = set(idx["ports"].keys())
        cases = []
        for r, pat, prove in picks:
            if r["design"] != design:
                continue
            cut = list(r["cut"])
            cut_bits = [idx["netbits"][c][0] for c in cut]
            k = query_key(v, cut, cut_bits, r["target"], pat, prove, 5)
            cases.append(dict(cut=cut, cut_bits=cut_bits, target=r["target"],
                              pattern=pat, prove=prove, query_key=k, _ports=ports))
        exec_id = f"r6_review_{Path(design).stem}_{int(t0)}"
        res = run_batch(v, top, cases, exec_id, TAB6 / "review", timeout=5)
        for c in cases:
            st = res["statuses"][c["query_key"]]
            rows.append(dict(design=design, target=c["target"],
                             pattern=c["pattern"], prove=c["prove"],
                             query_key=c["query_key"], original=orig_st.get(c["query_key"]),
                             review=st, agree=int(orig_st.get(c["query_key"]) == st),
                             execution_id=exec_id))
    d = pd.DataFrame(rows)
    d.to_csv(TAB6 / "r6_review.csv", index=False, encoding="utf-8-sig")
    info = dict(queries=len(d), agree=int(d.agree.sum()),
                disagree=int((1 - d.agree).sum()),
                original_status_counts=d.original.value_counts().to_dict(),
                review_status_counts=d.review.value_counts().to_dict(),
                wall_s=round(time.perf_counter() - t0, 1))
    (TAB6 / "r6_review_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())