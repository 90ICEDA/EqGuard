"""Re-run the 24 replay-audit queries with corrected recovery pattern order."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import json
import sys
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
from r4_batches import load_netbits, pattern_rows  # noqa: E402
from r4_runner import digest, query_key, run_batch  # noqa: E402
from sat_evidence_v4 import normalize_cut  # noqa: E402


def main() -> int:
    rel = pd.read_csv(TAB3 / "r3_recovery_relations.csv", encoding="utf-8-sig")
    rel["source"] = "recovery"
    q = pd.read_csv(TAB3 / "r3_recovery_queries.csv", encoding="utf-8-sig",
                    dtype={"pattern": str})
    rrel = rel.sort_values(["design", "relation_id"])
    picked = []
    for _, g in rrel.groupby("design"):
        picked += list(g.head(2).relation_id)
    rows = []
    for rid in picked:
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
            res = run_batch(WORK / "trans" / str(rr.design),
                            P0.module_name(WORK / "trans" / str(rr.design)),
                            [dict(cut=cut, target=str(rr.target),
                                  pattern=pr["pattern"], prove=pr["prove"],
                                  query_key=key, _ports=ports)],
                            f"r4Bfix_{key[:10]}", TAB4, force=True, timeout=5)
            after = res["statuses"][key]
            rows.append(dict(relation_id=rid, design=str(rr.design),
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
    d = pd.DataFrame(rows)
    d.to_csv(TAB4 / "r4_replay_audit.csv", index=False, encoding="utf-8-sig")
    mpath = TAB4 / "r4_manifest.json"
    m = json.loads(mpath.read_text(encoding="utf-8"))
    m["B"] = dict(selected=int(len(d)), key_equal=int(d.key_equal.sum()),
                  cut_equal=int(d.cut_equal.sum()),
                  status_equal=int(d.status_equal.sum()))
    m["queries_new"] = int(m.get("queries_new", 0) + len(d))
    m["counts"]["new_solves"] = int(m["counts"].get("new_solves", 0) + len(d))
    m["budget_ok"] = bool(m["queries_new"] <= 384)
    m["note"] = "B re-run after fixing recovery pattern order (11/00, not product order)"
    mpath.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(d.to_string(index=False), flush=True)
    print("key_equal", int(d.key_equal.sum()), "status_equal", int(d.status_equal.sum()),
          "queries_new_total", m["queries_new"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
