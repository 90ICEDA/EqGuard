"""sat_functional_relations_agnostic.py -- label-agnostic P0 (pilot).

与 `sat_functional_relations.py` 的区别：
  * 候选生成**不看 `Trojan*` 名字**；
  * mux：target=PO，cut = S0/A/B（真实引脚）；
  * cone：target=PO，cut = 该 PO 驱动门的全部输入网（最多 3 条）；
  * `--max-cases` 限制每 design 的 case 数。

复用原脚本的 struct 导出 / rename / SAT 查询 / 解析。
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import re
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import sat_functional_relations as P0  # noqa: E402

_ORIG_CASE_QUERIES = P0.case_queries
MUX_TYPES = {"MUX2X1", "MX2X1_RS"}


def _sat_ref2(name: str) -> str:
    """比原 sat_ref 更稳：含 `.`/`[` 等字符的名字加反斜杠（yosys 可引用）。"""
    if str(name).startswith("$"):
        return str(name)
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", str(name)):
        return str(name)
    return "\\" + str(name).lstrip("\\")


def pick_mux_agnostic(g: dict) -> list[dict]:
    cases, seen = [], set()
    for cname, cell in g["cells"].items():
        if cell.get("type") not in MUX_TYPES:
            continue
        bits = cell.get("connections", {})
        ybits = bits.get("Y") or bits.get("Q") or []
        if not ybits:
            continue
        target = P0.net_name(g, ybits[0])
        if not target or target in seen:
            continue
        conns = {p: [P0.net_name(g, b) for b in bs] for p, bs in bits.items()}
        cut = {p: conns[p][0] for p in ("S0", "A", "B")
               if p in conns and conns[p] and conns[p][0]}
        if not cut:
            continue
        seen.add(target)
        cases.append(dict(kind="mux", cell=cname, type=cell["type"],
                          target=target, cut=cut, conns=conns,
                          n_po_reached=0, n_dff_reached=0))
    return cases


def pick_gate_agnostic(g: dict) -> list[dict]:
    """组合门 target=输出网，cut=输入网（不带名字；mux 由 pick_mux 单独处理）。"""
    cases = []
    for cn, cell in g["cells"].items():
        typ = str(cell.get("type", "")).upper()
        if "DFF" in typ or "LATCH" in typ or cell.get("type") in MUX_TYPES:
            continue
        conns = {p: [P0.net_name(g, b) for b in bs]
                 for p, bs in cell.get("connections", {}).items()}
        out = None
        for p in ("Y", "Q", "QN"):
            if p in conns and conns[p] and conns[p][0]:
                out = conns[p][0]
                break
        if not out:
            continue
        cut = []
        for p, ns in conns.items():
            if p.upper() in ("Y", "Q", "QN", "CK", "CLK"):
                continue
            for n in ns:
                if n and n != out and n not in cut:
                    cut.append(n)
        if not cut:
            continue
        cutd = {f"c{i}": n for i, n in enumerate(cut[:3])}
        cases.append(dict(kind="gate", cell=cn, type=cell["type"], target=out,
                          cut=cutd, conns=conns, seq=1,
                          n_po_reached=0, n_dff_reached=0))
    return cases


def pick_cone_agnostic(g: dict) -> list[dict]:
    drv, _ = P0._graph_maps(g)
    out_bits = {b: p for p, info in g["ports"].items()
                if info.get("direction") == "output"
                for b in info.get("bits", []) if isinstance(b, int)}
    cases, seen = [], set()
    for b, pname in out_bits.items():
        if pname in seen or drv.get(b) is None:
            continue
        driver = g["cells"][drv[b]]
        conns = {p: [P0.net_name(g, nb) for nb in bits] for p, bits in
                 driver.get("connections", {}).items()}
        typ = str(driver.get("type", "")).upper()
        if "DFF" in typ or "LATCH" in typ:
            continue                      # 组合逻辑 P0：DFF 的 seq 语义仍未解
        nets = [ns[0] for p, ns in conns.items()
                if p not in ("Y", "Q", "QN", "CK", "CLK") and ns]
        nets = [n for n in nets if n]
        if not nets:
            continue
        seen.add(pname)
        cut = {f"c{i}": n for i, n in enumerate(nets[:3])}
        cases.append(dict(kind="cone", cell=drv[b], type=driver["type"],
                          target=pname, cut=cut, conns=conns, seq=1,
                          n_po_reached=0, n_dff_reached=0))
    return cases


def pick_dff_next_agnostic(g: dict) -> list[dict]:
    """M2：DFF 的 next-state D 作为 target，cut = D 驱动门的输入（组合 SAT）。"""
    drvm = {}
    for cn, c in g["cells"].items():
        for p, bits in c.get("connections", {}).items():
            if str(p).upper() in ("Y", "Q", "QN"):
                for b in bits:
                    if isinstance(b, int):
                        drvm[P0.net_name(g, b)] = (cn, c)
    cases = []
    for cn, c in g["cells"].items():
        typ = str(c.get("type", "")).upper()
        if "DFF" not in typ and "LATCH" not in typ:
            continue
        conns = {p: [P0.net_name(g, b) for b in bs]
                 for p, bs in c.get("connections", {}).items()}
        d = (conns.get("D") or [None])[0]
        q = (conns.get("Q") or conns.get("QN") or [None])[0]
        if not d or not q:
            continue
        drv = drvm.get(d)
        if not drv:
            continue
        _dcn, dc = drv
        dt = str(dc.get("type", "")).upper()
        if "DFF" in dt or "LATCH" in dt:
            continue
        dconns = {p: [P0.net_name(g, b) for b in bs]
                  for p, bs in dc.get("connections", {}).items()}
        cut = []
        for p, ns in dconns.items():
            if p.upper() in ("Y", "Q", "QN", "CK", "CLK"):
                continue
            for n in ns:
                if n and n != d and n not in cut:
                    cut.append(n)
        if not cut:
            continue
        cutd = {f"c{i}": n for i, n in enumerate(cut[:3])}
        cases.append(dict(kind="dff_next", cell=cn, type=c["type"], target=d,
                          q=q, cut=cutd, conns=conns, seq=1,
                          n_po_reached=0, n_dff_reached=0))
    return cases


def build_script_agnostic(v, top, cases, js, timeout, ports, bmc_depths=(), bmc_timeout=120):
    """在 P0 build_script 基础上：**target 若是内部网也 rename+keep**，避免 opt 后找不到。"""
    lines = [f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten", "proc",
             f"select -module {top}"]
    renamed = {}
    rlines = []

    def add_rename(nm):
        if nm in renamed:
            return renamed[nm]
        safe = f"fg_{len(renamed)}"
        renamed[nm] = safe
        rlines.append(f"rename {P0.sat_ref(nm)} {safe}")
        return safe

    for c in cases:
        c["_refs"] = {k: add_rename(nm) for k, nm in c["cut"].items()}
        t = c["target"]
        if t in renamed:
            c["_pref"] = renamed[t]
        elif t in ports:
            c["_pref"] = None
        else:
            c["_pref"] = add_rename(t)
    lines += rlines
    if renamed:
        lines.append("setattr -set keep 1 " + " ".join(f"w:{x}" for x in renamed.values()))
    lines += [f'write_json "{P0.wsl(js)}"', f"techmap -autoproc -map {P0.CELL_MAP}", "opt -fast"]
    query_id = 0
    for c in cases:
        qs = case_queries_agnostic(c, timeout)
        c["_nq"] = len(qs)
        c["_nbmc"] = 0
        for query in qs:
            lines += [f'log SATQ{query_id:06d}', query]
            query_id += 1
    return "\n".join(lines) + "\n"


def case_queries_agnostic(c: dict, timeout: int) -> list[str]:
    """gate / dff_next 用组合 4 查询（target 用 rename+keep 后的 _pref）；mux 保留原语义。"""
    kind = c.get("kind")
    if kind in ("dff_next", "gate"):
        po = c.get("_pref") or ("\\" + str(c["target"]).lstrip(chr(92)))
        nets = list(c["_refs"].values())
        if not nets:
            return []
        s1 = " ".join(f"-set {n} 1" for n in nets)
        s0 = " ".join(f"-set {n} 0" for n in nets)
        return [
            f"sat -seq 1 {s1} -prove {po} 1 -timeout {timeout}",
            f"sat -seq 1 {s1} -prove {po} 0 -timeout {timeout}",
            f"sat -seq 1 {s0} -prove {po} 1 -timeout {timeout}",
            f"sat -seq 1 {s0} -prove {po} 0 -timeout {timeout}",
        ]
    if kind == "mux" and c.get("_pref"):
        po = c["_pref"]
        nets = list(c["_refs"].values())
        if not nets:
            return []
        sel = c["_refs"].get("S0") or nets[0]
        dat = c["_refs"].get("B") or c["_refs"].get("A") or (nets[1] if len(nets) > 1 else nets[0])
        return [
            f"sat -seq 1 -set {sel} 1 -set {dat} 1 -prove {po} 1 -timeout {timeout}",
            f"sat -seq 1 -set {sel} 1 -set {dat} 0 -prove {po} 0 -timeout {timeout}",
            f"sat -seq 1 -set {sel} 0 -set {dat} 1 -prove {po} 1 -timeout {timeout}",
            f"sat -seq 1 -set {sel} 1 -set {dat} 1 -prove {po} 0 -timeout {timeout}",
        ]
    return _ORIG_CASE_QUERIES(c, timeout)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", default="hosts_bt31")
    ap.add_argument("--host", default="s38584t100")
    ap.add_argument("--inst", default="injalpha")
    ap.add_argument("--recipes", default="ys_abc")
    ap.add_argument("--max-cases", type=int, default=20)
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--bmc-timeout", type=int, default=20)
    ap.add_argument("--bmc-depths", default="")
    ap.add_argument("--only-dff", action="store_true",
                    help="只跑 DFF 的 next-state D 锥（M2 试点）")
    ap.add_argument("--comb-cases", type=int, default=10,
                    help="每 design 取多少个组合 mux/PO case")
    ap.add_argument("--dff-cases", type=int, default=5,
                    help="每 design 取多少个 DFF next-state case")
    ap.add_argument("--gate-cases", type=int, default=80,
                    help="每 design 取多少个组合门 target case")
    ap.add_argument("--mux-cases", type=int, default=20,
                    help="每 design 取多少个 mux case（全部 mux，不限 PO）")
    ap.add_argument("--dff-order", choices=["name", "obs"], default="obs",
                    help="DFF 抽样顺序：name=按遍历/名字；obs=按 Q→PO/DFF 可观测性排序")
    ap.add_argument("--out", default=str(ROOT / "_p0pilot/agnostic.csv"))
    ap.add_argument("--logdir", default=str(ROOT / "_p0pilot/agnostic_logs"))
    ap.add_argument("--allow-overwrite", action="store_true",
                    help="Explicitly allow replacing legacy output/logs")
    a = ap.parse_args()
    if not a.allow_overwrite and (Path(a.out).exists() or
            (Path(a.logdir).exists() and any(Path(a.logdir).iterdir()))):
        ap.error('Existing evidence: choose fresh --out/--logdir')
    logdir = Path(a.logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    bmc_depths = [int(s) for s in str(a.bmc_depths).split(",") if s.strip().isdigit()]
    recipes = [s.strip() for s in a.recipes.split(",") if s.strip()]
    insts = [s.strip() for s in a.inst.split(",") if s.strip()]
    P0.case_queries = case_queries_agnostic      # monkey-patch: DFF cone uses -seq 2
    P0.sat_ref = _sat_ref2

    rows: list[dict] = []
    def sample(cases: list, n: int) -> list:
        if n <= 0:
            return []
        if len(cases) <= n:
            return cases
        step = len(cases) / n
        return [cases[int(i * step)] for i in range(n)]
    for inst in insts:
        vs = P0.find_designs(a.fold, a.host, inst, recipes)
        canon = [x for x in vs if "keep" not in x.name]
        if canon:
            vs = canon
        for v in vs:
            top = P0.module_name(v)
            print(f"\n=== {v.name} (top={top})")
            js_raw = logdir / f"{top}.struct_raw.json"
            js_sat = logdir / f"{top}.sat.json"
            s0 = "\n".join([
                f'read_verilog "{P0.wsl(v)}"', f"hierarchy -top {top}", "flatten", "proc",
                f'write_json "{P0.wsl(js_raw)}"',
                f"techmap -autoproc -map {P0.CELL_MAP}", "opt -fast"]) + "\n"
            if not (js_raw.exists() and js_raw.stat().st_mtime >= v.stat().st_mtime):
                P0.run_yosys(s0, logdir / f"{top}.struct.log")
            else:
                print(f"  [cache] struct raw reused: {js_raw.name}")
            g = P0.load_graph(js_raw, top)
            dff = pick_dff_next_agnostic(g)
            if a.dff_order == "obs":
                dff.sort(key=lambda c: -(c.get("n_po_reached", 0) + c.get("n_dff_reached", 0)))
            dff = sample(dff, a.dff_cases)
            mux = pick_mux_agnostic(g)
            mux.sort(key=lambda c: -(c.get("n_po_reached", 0) + c.get("n_dff_reached", 0)))
            mux = sample(mux, a.mux_cases)
            gate = pick_gate_agnostic(g)
            gate.sort(key=lambda c: -(c.get("n_po_reached", 0) + c.get("n_dff_reached", 0)))
            gate = sample(gate, a.gate_cases)
            if a.only_dff:
                raw = dff
            else:
                raw = mux + gate + sample(pick_cone_agnostic(g), a.comb_cases) + dff
            cases, seen_t = [], set()
            for c in raw:
                if c["target"] in seen_t:
                    continue
                seen_t.add(c["target"])
                cases.append(c)
            print(f"  [cases] total={len(cases)} -> cap {a.max_cases}")
            cases = cases[:max(1, a.max_cases)]
            if not cases:
                print("  [skip] no cases")
                continue
            for c in cases:
                net = c.get("q") if c.get("kind") == "dff_next" else c.get("target")
                if net:
                    npo, ndff = P0.forward_reach(g, [net])
                    c["n_po_reached"], c["n_dff_reached"] = npo, ndff
            t0 = time.time()
            out = P0.run_yosys(build_script_agnostic(
                v, top, cases, js_sat, a.timeout, set(g["ports"].keys()), bmc_depths, a.bmc_timeout),
                logdir / f"{top}.sat.log")
            res = P0.parse_results(out)
            dt = time.time() - t0
            print(f"  [sat] cases={len(cases)} elapsed={dt:.1f}s per_case={dt/max(len(cases),1):.1f}s")
            k, n_proved = 0, 0
            for c in cases:
                got = res[k:k + c["_nq"]]
                got += ["unknown"] * (c["_nq"] - len(got))
                k += c["_nq"]
                q1, q2, q3, q4 = got
                bmc = res[k:k + c["_nbmc"]]
                bmc += ["unknown"] * (c["_nbmc"] - len(bmc))
                k += c["_nbmc"]
                if c["kind"] == "mux":
                    decided = int(q1 == "proved" and q2 == "proved")
                    influence = int(q1 == "proved" and q3 == "refuted")
                else:
                    decided = int(((q1 == "proved") ^ (q2 == "proved")) and
                                  ((q3 == "proved") ^ (q4 == "proved")))
                    influence = int(q1 == "proved" and q3 == "refuted")
                status = "legacy_condition_contrast" if (decided and influence) else "partial"
                n_proved += int(status == "proved")
                rows.append(dict(design=v.name, top=top, inst=inst,
                                 recipe=v.stem.split("__")[-1], kind=c["kind"],
                                 cell=c["cell"], cell_type=c["type"], target=c["target"],
                                 cut_nets=";".join(c["cut"].values()),
                                 q_net=c.get("q", ""),
                                 sat_q1=q1, sat_q2=q2, sat_q3=q3, sat_q4=q4,
                                 decided=decided, influence=0, condition_contrast=influence,
                                 influence_valid=0,
                                 influence_scope='legacy_condition_contrast_only_not_per_input_influence',
                                 decided_scope='sampled_conditions_only_not_complete_cut_sufficiency',
                                 semantic_version='legacy_four_query_contrast',
                                 n_po_reached=c.get("n_po_reached", 0),
                                 n_dff_reached=c.get("n_dff_reached", 0),
                                 status=status, runtime_s=round(dt, 1),
                                 log=str((logdir / f"{top}.sat.log").relative_to(ROOT))))
            print(f"  [out] proved={n_proved}/{len(cases)}")
    if rows:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
        print(f"\n[out] {out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
