"""LEGACY four-query condition contrast; use v3 for per-input table evidence.

2026-10-26 audit: the historical J1/J2 wording below is not a full cut or
shared-environment causal proof. New rows explicitly mark this scope and do
not emit overall status=proved. Historical artifacts are not rewritten.

sat_functional_relations.py —— B01/P0：**真 SAT 功能关系提取**（CPU ✓，秒级/案例 ✓）。

一句话 ✓：对每个（设计 × 木马实例 × 配方）找到"**木马把哪个 PO 劫持了**" ✓，
用 `yosys sat` 证明三条判断 ✓，落 `functional_relations.csv` ✓ + 每案日志 ✓。

三条判断（**全部是 SAT ✓，不是启发式 ✗**）：
  J1 **割集充分（decided）** ✓：钉死 MUX 的 `{S0=1, B=b}` → 证明 `PO == b`（b=0/1 各一次 ✓）
     ⇒ "**割集 {S0,B} 决定 PO**" ✓。
  J2 **控制影响（influence）** ✓：只钉 `{S0=1, B=1}` 而放空 `A` → 若 `PO==1` 可证 ✓
     ⇒ "**触发信号 S0 能把 PO 劫持到木马值**" ✓（S0=0 时不可证 ✓ 作对照 ✓）。
  J3 **可观测（observable）** ✓：结构判定 ✓ —— 目标若直连 **模块 output / DFF 的 D** ✓ 记 1 ✓
     （来自 `write_json` 的图 ✓，不走 SAT ✓）。

口径与限制（写论文必须带 ⚠️）：
  · 全部为 **`-seq 1` 单步**语义 ✓（`sat` 在 yosys 0.51 里**只有 `-seq` 能导入 `$dff`** ✗）；
    ⇒ 触发器输出在 step-1 是**自由初态** ✓，因此本脚本**不对"计数器能否走到触发值"下结论** ✗，
    单列 `reach_status=unknown` ✓（后续可用 `-seq N` 或 `-tempinduct` 补充 ⚠️）。
  · 库单元用 `phase2/ys/sat_cells_map.v` 做行为映射 ✓（6 种 ✓，端口名已与真实实例核对 ✓）；
    DFF 的**异步** RN/SN 被折进 D 的组合 mux ⚠️（等价 `async2sync` ✓，差一个时钟沿 ✗）。

用法 ✓：
    python phase2/ys/sat_functional_relations.py --host rs232t1000 --inst injalpha
    python phase2/ys/sat_functional_relations.py --host rs232t1000 --inst injalpha,injepsilon \
        --recipes ys_id,ys_abc,ys_aig --fold hosts_bt31
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from sat_boundary_semantics import parse_query_results

ROOT = Path(_eqguard_path(''))
WSL_ROOT = _eqguard_path('', wsl=True)
CELL_MAP = "phase2/ys/sat_cells_map.v"
OUT_DIR = ROOT / "10.15/06_统一评测协议/N4_三向泛化"
TROJAN_PAT = re.compile(r"^(\\\\)?Trojan", re.IGNORECASE)
# 直通型单元：木马输出经这些单元驱动 PO 时，割集取它的输入
PASS_TYPES = {"MX2X1_RS", "MUX2X1", "OR2X1", "AND2X2", "XOR2X1", "INVX0"}


def wsl(path: Path) -> str:
    """Windows 绝对路径 → WSL 路径 ✓（脚本在 WSL 里跑 yosys ✓）。"""
    rel = Path(path).resolve().relative_to(ROOT)
    return f"{WSL_ROOT}/{rel.as_posix()}"


def run_yosys(script: str, log: Path, timeout: int = 900) -> str:
    log.parent.mkdir(parents=True, exist_ok=True)
    ys = log.with_suffix(".ys")
    ys.write_text(script, encoding="utf-8")
    t0 = time.time()
    p = subprocess.run(["wsl", "-e", "bash", "-lc", f'cd "{WSL_ROOT}" && yosys -s "{wsl(ys)}"'],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    out = (p.stdout or "") + (p.stderr or "")
    out = "\n".join(ln for ln in out.splitlines() if "localhost" not in ln)
    log.write_text(out, encoding="utf-8")
    print(f"  [yosys] {log.name} rc={p.returncode} {time.time()-t0:.1f}s")
    return out


def parse_results(out: str) -> list[str]:
    """Marker-bound statuses preserve timeout/error slots; legacy is unbound."""
    return parse_query_results(out)


def find_designs(fold: str, host: str, inst: str, recipes: list[str]) -> list[Path]:
    """按 `{host}__{inst}_d1_s42__*{recipe}.v` 找 ✓（不同 keep 方案 ✓ 有/无 `keepbnd` 都行 ✓）。"""
    d = ROOT / "generate_trans" / "folds" / fold / "trans"
    out = []
    for r in recipes:
        cand = sorted(d.glob(f"{host}__{inst}_d1_s42__*{r}.v"))
        if not cand:
            print(f"  [skip] 缺 {host}__{inst}_d1_s42__*{r}.v ✗")
            continue
        out += cand[:1]
    return out


def load_graph(js: Path, top: str) -> dict:
    mod = json.loads(js.read_text(encoding="utf-8"))["modules"][top]
    ports = mod["ports"]
    # net number → name ✓（优先取非 $ 前缀的名字 ✓）
    names: dict[int, str] = {}
    for nm, info in mod.get("netnames", {}).items():
        for bit in info.get("bits", []):
            if isinstance(bit, int) and (bit not in names or names[bit].startswith("$")):
                names[bit] = nm
    cells = mod["cells"]
    return dict(ports=ports, names=names, cells=cells, netnames=mod.get('netnames', {}))


def net_name(g: dict, bit) -> str:
    if not isinstance(bit, int):
        return str(bit)
    return g["names"].get(bit, f"${bit}")


def sat_ref(name: str) -> str:
    """把 JSON 里的 net 名变成 yosys 可引用的名字 ✓（含 `.` 等字符要加反斜杠 ✓）。"""
    if name.startswith("$"):
        return name
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", name):
        return name
    return name.lstrip("\\")


def is_trojan(name: str) -> bool:
    return bool(TROJAN_PAT.match(name.lstrip("\\")))


def _graph_maps(g: dict) -> tuple[dict, dict]:
    """建 bit→driver 单元 / bit→consumer 单元 两张表 ✓（与单元类型无关 ✓，AIG/NAND 也适用 ✓）。"""
    drv: dict[int, str] = {}
    con: dict[int, list[str]] = {}
    for cname, cell in g["cells"].items():
        conns = cell.get("connections", {})
        for port, bits in conns.items():
            for b in bits:
                if not isinstance(b, int):
                    continue
                if port in ("Y", "Q", "QN"):
                    drv.setdefault(b, cname)
                else:
                    con.setdefault(b, []).append(cname)
    return drv, con


def cone_trojan(g: dict, bit: int, drv: dict, depth: int = 8, max_nodes: int = 4000) -> list[str]:
    """反向 BFS：从 bit 的**扇入锥**里收集 `Trojan*` 网 ✓（不依赖单元类型 ✓）。"""
    seen, stack, found = {bit}, [(bit, 0)], []
    while stack and len(seen) < max_nodes:
        b, d = stack.pop()
        cname = drv.get(b)
        if cname is None:
            continue
        for port, bits in g["cells"][cname].get("connections", {}).items():
            if port in ("Y", "Q", "QN"):
                continue
            for nb in bits:
                if not isinstance(nb, int) or nb in seen:
                    continue
                nm = net_name(g, nb)
                if is_trojan(nm):
                    found.append(nm)
                if d + 1 < depth:
                    seen.add(nb)
                    stack.append((nb, d + 1))
    return sorted(set(found))


def forward_index(g: dict) -> dict:
    """Build once per snapshot, retain aliases and exact DFF D sinks."""
    bit_of = {v: k for k, v in g['names'].items()}
    for name, net in g.get('netnames', {}).items():
        if len(net.get('bits', [])) == 1 and isinstance(net['bits'][0], int):
            bit_of[name] = net['bits'][0]
    outputs = {b for p in g['ports'].values() if p.get('direction') == 'output'
               for b in p.get('bits', []) if isinstance(b, int)}
    consumers = {}
    for cn, c in g['cells'].items():
        dirs = c.get('port_directions', {})
        for pin, bits in c.get('connections', {}).items():
            is_output = dirs.get(pin) == 'output' if dirs else pin in ('Y', 'Q', 'QN')
            if not is_output:
                for bit in bits:
                    if isinstance(bit, int):
                        consumers.setdefault(bit, []).append((cn, pin))
    return dict(bit_of=bit_of, outputs=outputs, consumers=consumers)


def forward_reach(g: dict, starts: list[str], max_nodes: int = 4000,
                  index: dict | None = None) -> tuple[int, int]:
    """正向 BFS：从木马网出发，数**到达多少个 PO 位 / 多少个 DFF 的 D 位** ✓（= 可观测性 ✓）。"""
    ix = index if index is not None else forward_index(g)
    bit_of, out_bits, con = ix['bit_of'], ix['outputs'], ix['consumers']
    seen_ptr, seen_dff = set(), set()
    frontier = [bit_of[s] for s in starts if s in bit_of]
    visited = set(frontier)
    while frontier and len(visited) < max_nodes:
        nxt = []
        for b in frontier:
            if b in out_bits:
                seen_ptr.add(b)
            for cname, input_pin in con.get(b, []):
                cell = g["cells"][cname]
                # 该单元是否寄存器（按类型名判断 ✓，覆盖 SDFF*/DFF* ✓）
                if any(t in cell["type"].upper() for t in ("DFF", "LATCH")):
                    if input_pin == 'D':
                        seen_dff.add((cname, 'D'))
                    continue
                for port, bits in cell.get("connections", {}).items():
                    dirs = cell.get('port_directions', {})
                    is_output = dirs.get(port) == 'output' if dirs else port in ('Y', 'Q', 'QN')
                    if is_output:
                        for ob in bits:
                            if isinstance(ob, int) and ob not in visited:
                                visited.add(ob)
                                nxt.append(ob)
        frontier = nxt
    return len(seen_ptr), len(seen_dff)


def pick_case_cone(g: dict) -> list[dict]:
    """**不依赖单元类型**的劫持点检测 ✓：PO 扇入锥里出现木马网 ⇒ 该 PO 被木马影响 ✓。

    割集取"该 PO 驱动单元的直接输入中的木马网" ✓（AIG 下可能只有 1–2 个 ✓）。
    """
    drv, _ = _graph_maps(g)
    out_bits = {b: pname for pname, info in g["ports"].items()
                if info.get("direction") == "output"
                for b in info.get("bits", []) if isinstance(b, int)}
    cases = []
    seen_po: set[str] = set()
    for b, pname in out_bits.items():
        if pname in seen_po:
            continue
        if drv.get(b) is None:
            continue
        tro = cone_trojan(g, b, drv)
        if not tro:
            continue
        seen_po.add(pname)
        driver = g["cells"][drv[b]]
        direct = sorted({net_name(g, nb)
                         for port, bits in driver.get("connections", {}).items()
                         if port not in ("Y", "Q", "QN")
                         for nb in bits if isinstance(nb, int) and is_trojan(net_name(g, nb))})
        cut_nets = direct or tro[:2]
        cut = {f"c{i}": n for i, n in enumerate(cut_nets[:3])}
        n_po, n_dff = forward_reach(g, cut_nets)
        cases.append(dict(kind="cone", cell=drv[b], type=driver["type"], target=pname,
                          cut=cut, conns={}, n_po_reached=n_po, n_dff_reached=n_dff))
    return cases


def pick_case(g: dict) -> list[dict]:
    """找"木马输出 → PO"的**MUX 劫持点** ✓（v1 快速路径 ✓；AIG/NAND 走 `pick_case_cone` ✓）。"""
    out_bits: dict[int, str] = {}
    for pname, info in g["ports"].items():
        if info.get("direction") == "output":
            for b in info.get("bits", []):
                if isinstance(b, int):
                    out_bits[b] = pname
    cases = []
    for cname, cell in g["cells"].items():
        if cell.get("type") not in PASS_TYPES:
            continue
        bits = cell.get("connections", {})
        conns = {p: [net_name(g, b) for b in bs] for p, bs in bits.items()}
        ybits = bits.get("Y") or bits.get("Q") or []
        if not ybits or ybits[0] not in out_bits:
            continue
        all_nets = [n for ns in conns.values() for n in ns]
        if not any(is_trojan(n) for n in all_nets):
            continue
        trojan_side = {p: ns[0] for p, ns in conns.items()
                       if p not in ("Y", "Q") and any(is_trojan(n) for n in ns)}
        n_po, n_dff = forward_reach(g, list(trojan_side.values()))
        cases.append(dict(kind="mux", cell=cname, type=cell["type"],
                          target=out_bits[ybits[0]], cut=trojan_side, conns=conns,
                          n_po_reached=n_po, n_dff_reached=n_dff))
    return cases




def module_name(v: Path) -> str:
    """从 .v 里读真实 module 名 ✓（文件名不一定等于 module 名 ✗）。"""
    for ln in v.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s*module\s+([\\A-Za-z_][\w\\.$]*)", ln)
        if m:
            return m.group(1).lstrip("\\")
    return v.stem


def build_script(v: Path, top: str, cases: list[dict], js: Path, timeout: int,
                 bmc_depths: list[int] = (), bmc_timeout: int = 120) -> str:
    """生成 yosys 脚本 ✓：结构导出（techmap 前 ✓）+ rename（techmap 前 ✓）+ 每案例 4 条 SAT ✓。"""
    lines = [f'read_verilog "{wsl(v)}"', f"hierarchy -top {top}", "flatten", "proc",
             f"select -module {top}"]
    renamed: dict[str, str] = {}
    renamed_lines: list[str] = []
    for i, c in enumerate(cases):
        refs: dict[str, str] = {}
        for k, nm in c["cut"].items():
            safe = f"fg_{i}_{len(refs)}"
            if nm not in renamed:
                renamed[nm] = safe
                renamed_lines.append(f"rename {sat_ref(nm)} {safe}")
            refs[k] = renamed[nm]
        c["_refs"] = refs
    lines += renamed_lines
    if renamed:
        keep = " ".join(f"w:{v}" for v in renamed.values())
        lines.append(f"setattr -set keep 1 {keep}")   # 防止 opt 把别名删掉 ✗
    lines += [f'write_json "{wsl(js)}"',
              f"techmap -autoproc -map {CELL_MAP}", "opt -fast"]
    query_id = 0
    for c in cases:
        qs = case_queries(c, timeout)
        c["_nq"] = len(qs)
        for query in qs:
            lines += [f'log SATQ{query_id:06d}', query]
            query_id += 1
        # ---- BMC：能否在 ≤d 拍内让"触发网"（cut 的第 1 个）变成 1 ✓（refuted ⇒ 可达 ✓）
        bnet = next(iter(c["_refs"].values()), None)
        dep = [d for d in bmc_depths if d > 0] if bnet else []
        c["_bmc_depths"], c["_nbmc"] = dep, len(dep)
        for d in dep:
            lines += [f'log SATQ{query_id:06d}',
                      f"sat -seq {d} -prove {bnet} 0 -timeout {bmc_timeout}"]
            query_id += 1
    return "\n".join(lines) + "\n"


def case_queries(c: dict, timeout: int) -> list[str]:
    """按案例类型生成 SAT 查询 ✓（mux：旧 4 条 ✓；cone：全 1 / 全 0 两 pattern × 2 prove ✓）。"""
    po = sat_ref(c["target"])
    nets = list(c["_refs"].values())
    if not nets:
        return []
    if c["kind"] == "mux":
        sel = c["_refs"].get("S0") or nets[0]
        dat = c["_refs"].get("B") or c["_refs"].get("A") or (nets[1] if len(nets) > 1 else nets[0])
        return [
            f"sat -seq 1 -set {sel} 1 -set {dat} 1 -prove {po} 1 -timeout {timeout}",   # 1 劫持高 ✓
            f"sat -seq 1 -set {sel} 1 -set {dat} 0 -prove {po} 0 -timeout {timeout}",   # 2 劫持低 ✓
            f"sat -seq 1 -set {sel} 0 -set {dat} 1 -prove {po} 1 -timeout {timeout}",   # 3 gating 对照 ✓
            f"sat -seq 1 -set {sel} 1 -set {dat} 1 -prove {po} 0 -timeout {timeout}",   # 4 sanity ✓
        ]
    s1 = " ".join(f"-set {n} 1" for n in nets)
    s0 = " ".join(f"-set {n} 0" for n in nets)
    return [
        f"sat -seq 1 {s1} -prove {po} 1 -timeout {timeout}",   # 1 cut=全1 ⇒ PO 必 1 ✓
        f"sat -seq 1 {s1} -prove {po} 0 -timeout {timeout}",   # 2 cut=全1 ⇒ PO 必 0 ✓
        f"sat -seq 1 {s0} -prove {po} 1 -timeout {timeout}",   # 3 cut=全0 ⇒ PO 必 1 ✓
        f"sat -seq 1 {s0} -prove {po} 0 -timeout {timeout}",   # 4 cut=全0 ⇒ PO 必 0 ✓
    ]



def main() -> int:
    import pandas as pd

    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", default="hosts_bt31")
    ap.add_argument("--host", default="rs232t1000")
    ap.add_argument("--inst", default="injalpha", help="逗号分隔 ✓（injalpha,injepsilon ✓）")
    ap.add_argument("--recipes", default="ys_id,ys_abc,ys_aig")
    ap.add_argument("--timeout", type=int, default=60, help="单次 sat 超时（秒 ✓）")
    ap.add_argument("--out", default=str(OUT_DIR / "tables/functional_relations.csv"))
    ap.add_argument("--bmc-depths", default="16,64",
                    help="BMC 可达性深度阶梯 ✓（小宿主可加 256 ✓）")
    ap.add_argument("--append", action="store_true",
                    help="把本次结果**追加**到已有 CSV ✓（分批跑 ✓，按 design+target 去重 ✓）")
    ap.add_argument("--bmc-timeout", type=int, default=120, help="BMC 单次超时（秒 ✓）")
    ap.add_argument("--logdir", default=str(OUT_DIR / "logs"))
    ap.add_argument("--allow-overwrite", action="store_true",
                    help="Allow replacing legacy output/logs; prefer fresh paths and v3")
    a = ap.parse_args()
    if not a.allow_overwrite and ((Path(a.out).exists() and not a.append) or
            (Path(a.logdir).exists() and any(Path(a.logdir).iterdir()))):
        ap.error('Existing legacy evidence: choose fresh --out/--logdir; use v3 for generic tables')
    bmc_depths = [int(s) for s in str(a.bmc_depths).split(",") if s.strip().isdigit()]

    recipes = [s.strip() for s in a.recipes.split(",") if s.strip()]
    insts = [s.strip() for s in a.inst.split(",") if s.strip()]
    (OUT_DIR / "tables").mkdir(parents=True, exist_ok=True)
    logdir = Path(a.logdir)
    logdir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for inst in insts:
        for v in find_designs(a.fold, a.host, inst, recipes):
            top = module_name(v)
            print(f"\n=== {v.name}（top={top}）")
            js = logdir / f"{top}.json"
            s0 = "\n".join([f'read_verilog "{wsl(v)}"', f"hierarchy -top {top}", "flatten", "proc",
                            f'write_json "{wsl(js)}"',
                            f"techmap -autoproc -map {CELL_MAP}", "opt -fast"]) + "\n"
            run_yosys(s0, logdir / f"{top}.struct.log")
            if not js.exists():
                print("  [fail] 结构导出失败 ✗")
                rows.append(dict(design=v.name, top=top, inst=inst,
                                 recipe=v.stem.split("__")[-1], status="struct_failed",
                                 log=str((logdir / f"{top}.struct.log").relative_to(ROOT))))
                continue
            g = load_graph(js, top)
            cases = pick_case(g) or pick_case_cone(g)
            print(f"  木马劫持点 {len(cases)} 个 ✓：" +
                  ", ".join(f"{c['kind']}:{c['cell']}({c['type']})→{c['target']}"
                            for c in cases[:4]))
            if not cases:
                rows.append(dict(design=v.name, top=top, inst=inst,
                                 recipe=v.stem.split("__")[-1], status="no_case",
                                 log=str((logdir / f"{top}.struct.log").relative_to(ROOT))))
                continue
            t0 = time.time()
            out = run_yosys(build_script(v, top, cases, js, a.timeout,
                                         bmc_depths, a.bmc_timeout),
                            logdir / f"{top}.sat.log")
            res = parse_results(out)
            print(f"  SAT 结论序列 ✓：{res}")
            k = 0
            for c in cases:
                got = res[k:k + c["_nq"]]
                got += ["unknown"] * (c["_nq"] - len(got))
                k += c["_nq"]
                q1, q2, q3, q4 = got
                bmc = res[k:k + c["_nbmc"]]
                bmc += ["unknown"] * (c["_nbmc"] - len(bmc))
                k += c["_nbmc"]
                # ---- 裁决 ✓
                if c["kind"] == "mux":
                    decided = int(q1 == "proved" and q2 == "proved")
                    influence = int(q1 == "proved" and q3 == "refuted")
                else:  # cone：两种 pattern 下 PO 都被决定 ✓
                    det1 = (q1 == "proved") ^ (q2 == "proved")
                    det0 = (q3 == "proved") ^ (q4 == "proved")
                    decided = int(det1 and det0)
                    # A solver timeout/error is not a counterexample.
                    influence = int(q1 == "proved" and q3 == "refuted")
                reach, depth = "unknown", ""
                for d, r in zip(c["_bmc_depths"], bmc):
                    if r == "refuted":
                        reach, depth = "reachable", d
                        break
                    if r not in ("proved", "refuted"):
                        reach = "unknown_timeout"
                        break
                else:
                    if bmc:
                        reach = "unreachable_in_horizon"
                n_po, n_dff = c.get("n_po_reached", 0), c.get("n_dff_reached", 0)
                rows.append(dict(
                    design=v.name, top=top, inst=inst, recipe=v.stem.split("__")[-1],
                    kind=c["kind"], cell=c["cell"], cell_type=c["type"], target=c["target"],
                    cut_nets=";".join(c["cut"].values()),
                    sat_q1=q1, sat_q2=q2, sat_q3=q3, sat_q4=q4,
                    decided=decided, influence=0, condition_contrast=influence,
                    influence_valid=0,
                    influence_scope='legacy_condition_contrast_only_not_per_input_influence',
                    decided_scope='sampled_conditions_only_not_complete_cut_sufficiency',
                    semantic_version='legacy_four_query_contrast',
                    observable=int((n_po + n_dff) > 0), n_po_reached=n_po,
                    n_dff_reached=n_dff,
                    reach_status=reach, reach_depth=depth,
                    bmc=";".join(f"{d}:{r}" for d, r in zip(c["_bmc_depths"], bmc)),
                    status="legacy_condition_contrast" if (decided and influence) else "partial",
                    runtime_s=round(time.time() - t0, 1),
                    log=str((logdir / f"{top}.sat.log").relative_to(ROOT))))
    if not rows:
        print("\n[warn] 没有产出 ✗（检查 --host/--inst/--recipes ✓）")
        return 1
    df = pd.DataFrame(rows)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if a.append and out.exists():
        old = pd.read_csv(out, encoding="utf-8-sig")
        df = pd.concat([old, df], ignore_index=True)
        key = [c for c in ("design", "target") if c in df]
        if key:
            df = df.drop_duplicates(subset=key, keep="last")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n[out] {out}（{len(df)} 行 ✓）")
    cols = [c for c in ("inst", "recipe", "target", "decided", "influence", "status") if c in df]
    print(df[cols].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

