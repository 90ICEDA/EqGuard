"""Regenerate round-12 models from raw snapshots and exact local mappings."""
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
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
T12 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round12"
T13 = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_pair_round13"
sys.path.insert(0, str(ROOT / "_p0pilot/round10_20261025"))
sys.path.insert(0, str(ROOT / "_p0pilot/round12_20261025"))
import native as N  # noqa: E402
from audit_blockers import load_raw  # noqa: E402
from run_round12 import eq_code  # noqa: E402
from polarity_test import inv_code  # noqa: E402


def main() -> int:
    plan = json.loads((T12 / "plan.json").read_text(encoding="utf-8"))
    q = pd.read_csv(T12 / "queries.csv", encoding="utf-8-sig")
    rows = []
    for pair, item in enumerate(plan["selected"]):
        a, _, _ = load_raw(item["source_view"])
        b, _, _ = load_raw(item["partner"])
        ca, sa = N.emit(a, "left_design", item["source_nets"])
        combos = list(itertools.product(*[s["alternatives"] for s in item["slots"]]))
        for r in q[q.pair_index == pair].itertuples():
            code_kind = "inv" if r.kind == "polarity_check" else "eq"
            actual = (ROOT / r.folder / "model.v").read_text(encoding="utf-8")
            actual_text_sha = hashlib.sha256(actual.encode()).hexdigest()
            hit = None
            for combo in combos:
                try:
                    cb, sb = N.emit(b, "right_design", list(combo))
                except (KeyError, ValueError):
                    continue
                code = (inv_code(ca, sa, cb) if code_kind == "inv"
                        else eq_code(ca, sa, cb))
                if hashlib.sha256(code.encode()).hexdigest() == actual_text_sha:
                    hit = list(combo)
                    break
            rows.append(dict(pair_index=pair, folder=r.folder, kind=r.kind,
                             model_sha_raw=r.model_sha,
                             model_sha_text=actual_text_sha,
                             regenerated=int(hit is not None),
                             mapping=";".join(hit) if hit else "",
                             combinations_tried=len(combos)))
    out = pd.DataFrame(rows)
    out.to_csv(T13 / "model_regeneration.csv", index=False, encoding="utf-8-sig")
    info = dict(queries=len(out), regenerated=int(out.regenerated.sum()),
                failed=int((1 - out.regenerated).sum()),
                by_kind=out.groupby("kind").regenerated.agg(["sum", "count"])
                .to_dict("index"))
    (T13 / "model_regeneration_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())