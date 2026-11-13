"""Independent re-solve (`-noincr`) of a fixed sample of recovery queries.

Also dumps CNF for two small rs232 queries, so UNSAT claims have a saved
problem that can be re-solved outside yosys.
"""
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
TAB = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables/sat_valid_round3"
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402
from r3_sat import parse_blocks  # noqa: E402


def main() -> int:
    rel = pd.read_csv(TAB / "r3_recovery_relations.csv", encoding="utf-8-sig")
    q = pd.read_csv(TAB / "r3_recovery_queries.csv", encoding="utf-8-sig")
    cut_of = dict(zip(rel.relation_id, rel.cut_nets))
    q["cut_nets"] = q.relation_id.map(cut_of)
    rel = rel.sort_values(["design", "relation_id"])
    picked = []
    for _, g in rel.groupby("design"):
        picked += list(g.head(2).relation_id)
    picked = set(picked)
    sel = q[q.relation_id.isin(picked)].copy()
    # one proved and one refuted query per relation
    rows = []
    for rid, g in sel.groupby("relation_id"):
        for st in ("proved", "refuted"):
            sub = g[g.status == st]
            if len(sub):
                rows.append(sub.iloc[0])
    sel = pd.DataFrame(rows)
    print("selected queries", len(sel), "relations", sel.relation_id.nunique(), flush=True)

    out = []
    cnf_done = 0
    for _, r in sel.iterrows():
        design = r["design"]
        v = WORK / "trans" / design
        top = P0.module_name(v)
        lines = [f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten",
                 "proc -noopt", f"select -module {top}"]
        renamed = {}

        def ref(nm):
            if nm in renamed:
                return renamed[nm]
            safe = f"fr_{len(renamed)}"
            renamed[nm] = safe
            lines.append(f"rename {P0.sat_ref(nm)} {safe}")
            return safe

        cut = [c for c in str(r["cut_nets"]).split(";") if c]
        refs = [ref(c) for c in cut]
        tref = ref(str(r["target"]))
        lines.append("setattr -set keep 1 " + " ".join(f"w:{x}" for x in renamed.values()))
        lines += ["techmap -autoproc -map phase2/ys/sat_cells_map.v", "opt -fast"]
        pattern = str(r["pattern"])
        sets = " ".join(f"-set {rf} {b}" for rf, b in zip(refs, pattern))
        shows = " ".join(f"-show {x}" for x in refs) + f" -show {tref}"
        cnf = ""
        if design.startswith("rs232") and cnf_done < 2:
            cnf_dir = R3 / "cnf" / v.stem
            cnf_dir.mkdir(parents=True, exist_ok=True)
            cnf = f" -dump_cnf {P0.wsl(cnf_dir / f'q{cnf_done + 1:05d}.cnf')}"
            cnf_done += 1
        lines += ["log QRY00001",
                  f"sat -seq 1 {sets} -prove {tref} {int(r['prove'])} "
                  f"-timeout 5 {shows}{cnf}"]
        log = R3 / "logs" / f"resolve_{v.stem}__{r['relation_id']}__{r['pattern']}_{int(r['prove'])}.sat.log"
        txt = P0.run_yosys("\n".join(lines) + "\n", log, timeout=1800)
        st, _ = parse_blocks(txt)
        out.append(dict(relation_id=r["relation_id"], design=design,
                        target=r["target"], pattern=r["pattern"],
                        prove=int(r["prove"]), original=r["status"],
                        re_solve=st.get(1, "no_result"),
                        agree=int(st.get(1, "no_result") == r["status"])))
    d = pd.DataFrame(out)
    d.to_csv(TAB / "r3_resolve_check.csv", index=False, encoding="utf-8-sig")
    print(d.to_string(index=False), flush=True)
    print("agreement", int(d.agree.sum()), "/", len(d), flush=True)
    cnf_files = list((R3 / "cnf").rglob("*.cnf")) if (R3 / "cnf").exists() else []
    info = dict(queries=len(d), agreement=int(d.agree.sum()),
                cnf_files=len(cnf_files),
                cnf_bytes={p.name: p.stat().st_size for p in cnf_files})
    (TAB / "r3_resolve_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
