"""Replay a deterministic subset of existing cone/DFF candidates with `proc -noopt`.

Purpose: validate (a) that the constant-error workaround restores queries, and
(b) that a replay reproduces the saved statuses on logs that were accepted.
Only train/val designs are used.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
sys.path.insert(0, str(ROOT / "_p0pilot/round2_20261025"))
import sat_functional_relations as P0  # noqa: E402
from extract_r2 import load_module, build_index, parse_blocks  # noqa: E402

WORK = ROOT / "generate_trans/folds/hosts_bt31"
OUT = ROOT / "_p0pilot/round2_20261025/extraction"


def build(v: Path, top: str, cases: list[dict], timeout: int, ports: set[str]) -> str:
    lines = [f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten",
             "proc -noopt", f"select -module {top}"]
    renamed, rlines = {}, []

    def ref(nm: str) -> str:
        if nm in ports:
            return P0.sat_ref(nm)
        if nm in renamed:
            return renamed[nm]
        safe = f"fp_{len(renamed)}"
        renamed[nm] = safe
        rlines.append(f"rename {P0.sat_ref(nm)} {safe}")
        return safe

    for c in cases:
        c["_refs"] = {nm: ref(nm) for nm in c["cut"]}
        c["_tref"] = ref(c["target"])
    lines += rlines
    if renamed:
        lines.append("setattr -set keep 1 " + " ".join(f"w:{x}" for x in renamed.values()))
    lines += ["techmap -autoproc -map phase2/ys/sat_cells_map.v", "opt -fast"]
    qid = 0
    for c in cases:
        c["_qids"] = []
        s1 = " ".join(f"-set {c['_refs'][nm]} 1" for nm in c["cut"])
        s0 = " ".join(f"-set {c['_refs'][nm]} 0" for nm in c["cut"])
        for sets, prove in ((s1, 1), (s1, 0), (s0, 1), (s0, 0)):
            qid += 1
            c["_qids"].append(qid)
            lines += [f"log QRY{qid:05d}",
                      f"sat -seq 1 {sets} -prove {c['_tref']} {prove} -timeout {timeout}"]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--inst", required=True)
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--timeout", type=int, default=3)
    ap.add_argument("--tag", default="replay")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    design = f"{a.host}__{a.inst}_d1_s42__{a.recipe}.v"
    csv = pd.read_csv(ROOT / "_p0pilot/functional_relations_agnostic.csv",
                      encoding="utf-8-sig").fillna("")
    d = csv[(csv.design == design) & csv.kind.isin(["cone", "dff_next"])].copy()
    d = d.sort_values(["kind", "target"]).reset_index(drop=True)
    if len(d) > a.n:
        step = len(d) / a.n
        d = d.iloc[[int(i * step) for i in range(a.n)]].reset_index(drop=True)
    v = WORK / "trans" / design
    top = P0.module_name(v)
    raw = OUT / "struct_raw" / f"{v.stem}.json"
    if not raw.exists():
        s0 = "\n".join([f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten",
                        "proc -noopt", f'write_json "{P0.wsl(raw)}"']) + "\n"
        P0.run_yosys(s0, OUT / "struct_raw" / f"{v.stem}.struct.log")
    idx = build_index(load_module(raw, top))
    cases = []
    for _, r in d.iterrows():
        cut = [x for x in str(r["cut_nets"]).split(";") if x]
        if not cut:
            continue
        cases.append(dict(cut=cut, target=str(r["target"]), kind=r["kind"],
                          saved=[r[f"sat_q{i}"] for i in range(1, 5)]))
    if not cases:
        print("no replay cases", flush=True)
        return 0
    script = build(v, top, cases, a.timeout, set(idx["ports"]))
    out = P0.run_yosys(script, OUT / f"{a.tag}__{v.stem}.sat.log", timeout=1800)
    st = parse_blocks(out)
    rows, agree, definite = [], 0, 0
    for c in cases:
        got = [st.get(q, "no_result") for q in c["_qids"]]
        same = sum(g == s for g, s in zip(got, c["saved"]))
        agree += same
        definite += sum(g in ("proved", "refuted") for g in got)
        rows.append(dict(design=design, host=a.host, recipe=a.recipe, kind=c["kind"],
                         target=c["target"], cut_nets=";".join(c["cut"]),
                         saved=";".join(c["saved"]), replay=";".join(got),
                         identical=bool(got == c["saved"]), n_same=same,
                         n_definite=sum(g in ("proved", "refuted") for g in got)))
    d2 = pd.DataFrame(rows)
    d2.to_csv(OUT / f"replay_{a.tag}_{a.host}_{a.inst}_{a.recipe}.csv",
              index=False, encoding="utf-8-sig")
    print(d2.to_string(index=False), flush=True)
    print(f"cases={len(cases)} saved_all_unknown={int((d2.saved == 'unknown;unknown;unknown;unknown').sum())} "
          f"exact_agreement_cases={int(d2.identical.sum())} query_agreement={agree}/{4*len(cases)} "
          f"definite_values={definite}/{4*len(cases)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
