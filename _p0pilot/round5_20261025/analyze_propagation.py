"""Derive conditional propagation edges from the measured truth tables.

No new candidate selection: all edges come from the frozen 4-bit cuts. Only a
small independent review of selected queries is executed.
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
from r5_runner import run_batch  # noqa: E402


def parse_tt(tt: str) -> dict:
    out = {}
    for item in str(tt).split(";"):
        p, feas, force = item.split(":")
        out[p] = (feas, force)
    return out


def main() -> int:
    rel = pd.read_csv(TAB5 / "r5_nonlocal_relations.csv", encoding="utf-8-sig")
    q = pd.read_csv(TAB5 / "r5_nonlocal_queries.csv", encoding="utf-8-sig",
                    dtype={"pattern": str})
    edges, summary = [], []
    for _, r in rel.iterrows():
        tt = parse_tt(r.truth_table)
        k = len(str(r.cut_nets).split(";"))
        n_prop = n_block = n_undet = n_infeas = 0
        for p0, p1 in itertools.combinations(sorted(tt), 2):
            diff = [i for i in range(k) if p0[i] != p1[i]]
            if len(diff) != 1:
                continue
            f0, f1 = tt[p0], tt[p1]
            if f0[0] == "infeasible" or f1[0] == "infeasible":
                n_infeas += 1
                continue
            if f0[1] in ("0", "1") and f1[1] in ("0", "1"):
                if f0[1] != f1[1]:
                    n_prop += 1
                    edges.append(dict(relation_id=r.relation_id, design=r.design,
                                      endpoint=r.target, internal_bit=diff[0],
                                      internal_target=str(r.cut_nets).split(";")[diff[0]],
                                      context_pattern="".join(
                                          p0[i] for i in range(k) if i != diff[0]),
                                      pattern_0=p0, value_0=int(f0[1]),
                                      pattern_1=p1, value_1=int(f1[1]),
                                      kind="propagates"))
                else:
                    n_block += 1
            else:
                n_undet += 1
        summary.append(dict(relation_id=r.relation_id, design=r.design,
                            endpoint=r.target,
                            functional_sufficiency=r.functional_sufficiency,
                            influence_status=r.influence_status,
                            n_prop_edges=n_prop, n_blocked_edges=n_block,
                            n_undetermined_edges=n_undet,
                            n_infeasible_pairs=n_infeas))
    ed = pd.DataFrame(edges)
    ed.to_csv(TAB5 / "r5_propagation_edges.csv", index=False, encoding="utf-8-sig")
    sd = pd.DataFrame(summary)
    sd.to_csv(TAB5 / "r5_propagation_summary.csv", index=False, encoding="utf-8-sig")
    print(sd.to_string(index=False), flush=True)
    print("total propagation edges", len(edges), flush=True)

    # independent review: up to 4 relations / 4 edges, both direction queries
    pick = sd[sd.n_prop_edges > 0].head(4).relation_id.tolist()
    rev = []
    t0 = time.perf_counter()
    for rid in pick:
        e = ed[ed.relation_id == rid].iloc[0]
        r = rel[rel.relation_id == rid].iloc[0]
        v = WORK / "trans" / r.design
        top = P0.module_name(v)
        mods = json.loads((R3 / "struct_raw" / f"{Path(r.design).stem}.json")
                          .read_text(encoding="utf-8"))["modules"]
        ports = set(next(iter(mods.values()))["ports"].keys())
        cut = str(r.cut_nets).split(";")
        cut_bits = list(map(int, r.cut_bits.split(";")))
        pairs = [(e.pattern_0, e.value_0), (e.pattern_1, e.value_1)]
        for pat, val in pairs:
            qrow = q[(q.relation_id == rid) & (q.pattern == pat) &
                     (q.prove == int(val))]
            if qrow.empty:
                continue
            key = qrow.iloc[0].query_key
            case = dict(cut=cut, cut_bits=cut_bits, target=r.target,
                        pattern=pat, prove=int(val), query_key=key, _ports=ports)
            exec_id = f"r5_edge_review_{key[:10]}"
            res = run_batch(v, top, [case], exec_id, TAB5, timeout=5, force=True)
            after = res["statuses"][key]
            rev.append(dict(relation_id=rid, design=r.design, endpoint=r.target,
                            pattern=pat, prove=int(val),
                            original=qrow.iloc[0].status, re_solve=after,
                            agree=int(after == qrow.iloc[0].status),
                            execution_id=exec_id))
    rv = pd.DataFrame(rev)
    rv.to_csv(TAB5 / "r5_propagation_edge_review.csv", index=False,
              encoding="utf-8-sig")
    info = dict(relations=len(sd), propagation_edges=int(len(edges)),
                relations_with_edges=int((sd.n_prop_edges > 0).sum()),
                blocked_edges=int(sd.n_blocked_edges.sum()),
                undetermined_edges=int(sd.n_undetermined_edges.sum()),
                review_queries=len(rv), review_agree=int(rv.agree.sum()),
                wall_s=round(time.perf_counter() - t0, 1))
    (TAB5 / "r5_propagation_edge_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
