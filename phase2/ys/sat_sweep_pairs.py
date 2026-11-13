"""sat_sweep_pairs.py —— **B05b：SAT sweeping 式跨实现配对**（**不看名字匹配** ✓）。

三步 ✓（与任务书 "SAT sweeping 或等价检查" 对齐 ✓）：
  1. **候选生成（名字无关 ✓）**：对两个实现做 **K 组随机输入**的**组合仿真** ✓
     （`SDFF*` 输出当自由输入 ✓，与 `-seq 1` 口径一致 ✓）→ 每个 net 得 K-bit **签名** ✓
     → **签名相同** 的跨设计 net 对 = 候选 ✓（常数签名剔除 ✗）。
  2. **对齐标签**：把候选对**在两侧统一改名**为 `sw_<i>` ✓ —— 名字只作为"交给证明器的标签" ✓
     **不参与匹配** ✓（匹配早已由签名完成 ✓）。
  3. **SAT 证明**：`equiv_make` + `equiv_simple -undef` + `equiv_induct -undef -seq 4` ✓
     → `proved` ✓ / `differ` ✗（有反例 ⇒ 签名撞车 ✓，说明 K 不够或确实不同 ✓）。

输出 ✓：`node_pairs_sweep.csv`
  `host, inst, pair, net_a, net_b, sig_hex, status ∈ {proved, differ, unknown}, log`

⚠️ 语义 ✓：`proved` = 两 net **组合等价（DFF 输出自由 ✓）** ✓；不覆盖"寄存器初值"✗（与 BMC 口径一致 ✓）。
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
import random
import re
import subprocess
import time
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
WSL_ROOT = _eqguard_path('', wsl=True)
BASE = ROOT / "10.15/06_统一评测协议/N4_三向泛化"
LOGS = BASE / "logs"
OUT_CSV = BASE / "tables/node_pairs_sweep.csv"

FUNCS = {
    "AND2X2": ("IN1", "IN2"), "OR2X1": ("IN1", "IN2"), "XOR2X1": ("IN1", "IN2"),
    "NAND2X1": ("IN1", "IN2"), "NOR2X1": ("IN1", "IN2"),
    "INVX0": ("IN",), "INVX1": ("IN",),
}
MUXES = {"MX2X1_RS": ("A", "B", "S0"), "MUX2X1": ("A", "B", "S0")}


def wsl(p: Path) -> str:
    return f"{WSL_ROOT}/{Path(p).resolve().relative_to(ROOT).as_posix()}"


def struct_json(v: Path) -> Path:
    """生成**干净**的结构 JSON ✓（无 rename ✗）—— 旧 JSON 可能被 SAT 脚本改名污染 ✗。"""
    top = v.stem
    for ln in v.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s*module\s+([\\A-Za-z_][\w\\.$]*)", ln)
        if m:
            top = m.group(1).lstrip("\\")
            break
    out = LOGS / "struct" / f"{top}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    ys = out.with_suffix(".prep.ys")
    ys.write_text("\n".join([f'read_verilog "{wsl(v)}"', f"hierarchy -top {top}",
                             "flatten", "proc", f'write_json "{wsl(out)}"']) + "\n",
                  encoding="utf-8")
    subprocess.run(["wsl", "-e", "bash", "-lc",
                    f'cd "{WSL_ROOT}" && yosys -q -s "{wsl(ys)}"'],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out


def decl_wires(v: Path) -> set[str]:
    """解析 .v 里**真正声明过的 wire** ✓（JSON 里有些名字只是单元引脚连接 ✗，rename 会 `not found` ✗）。"""
    out: set[str] = set()
    for ln in v.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\s*wire\s+(?:\[[^\]]*\]\s*)?(\\?[^\s;,]+)", ln)
        if m:
            out.add(m.group(1).lstrip("\\"))
    return out


def load_json(js: Path):
    d = json.loads(js.read_text(encoding="utf-8"))
    top = list(d["modules"])[0]
    mod = d["modules"][top]
    names: dict[int, str] = {}
    for nm, info in mod.get("netnames", {}).items():
        for b in info.get("bits", []):
            if isinstance(b, int) and (b not in names or names[b].startswith("$")):
                names[b] = nm
    return top, mod, names


def simulate(mod: dict, names: dict, k: int, seed: int) -> tuple[dict[int, int], int]:
    """K 组随机模式的**组合仿真** ✓（迭代到不动点 ✓，DFF 输出/输入端口 = 自由 ✓）。"""
    rng = random.Random(seed)
    mask = (1 << k) - 1
    val: dict[int, int] = {}
    # 自由位 = 输入端口位 + 寄存器输出位
    free = set()
    for pinfo in mod["ports"].values():
        if pinfo.get("direction") == "input":
            free.update(b for b in pinfo.get("bits", []) if isinstance(b, int))
    for cell in mod["cells"].values():
        if "DFF" in cell.get("type", "").upper() or "LATCH" in cell.get("type", "").upper():
            for port, bits in cell.get("connections", {}).items():
                if port in ("Q", "QN"):
                    free.update(b for b in bits if isinstance(b, int))
    for b in free:
        val[b] = rng.getrandbits(k)
    for _ in range(64):                     # 不动点迭代 ✓（深度 ≤ 64 足够 ✓）
        changed = 0
        for cell in mod["cells"].values():
            t = cell.get("type", "").upper()
            conns = cell.get("connections", {})
            if "DFF" in t or "LATCH" in t:
                continue
            if t in FUNCS:
                ins, ok = [], True
                for p in FUNCS[t]:
                    bs = [x for x in (conns.get(p) or []) if isinstance(x, int)]
                    if not bs or val.get(bs[0]) is None:
                        ok = False
                        break
                    ins.append(val[bs[0]])
                if not ok:
                    continue
                a = ins[0]
                if t.startswith("AND") or t.startswith("NAND"):
                    r = a & ins[1] if len(ins) > 1 else a
                    if t.startswith("NAND"):
                        r = (~r) & mask
                elif t.startswith("OR") or t.startswith("NOR"):
                    r = a | ins[1] if len(ins) > 1 else a
                    if t.startswith("NOR"):
                        r = (~r) & mask
                elif t.startswith("XOR"):
                    r = a ^ ins[1] if len(ins) > 1 else a
                else:                        # INV
                    r = (~a) & mask
                outs = conns.get("Q") or conns.get("QN") or []
                for ob in outs:
                    if isinstance(ob, int) and val.get(ob) != r:
                        val[ob] = r
                        changed += 1
            elif t in MUXES:
                a_, b_, s_ = (conns.get(p) or [None] for p in MUXES[t])
                bs = [x for x in (a_ + b_ + s_) if isinstance(x, int)]
                if len(bs) < 3 or any(val.get(x) is None for x in bs):
                    continue
                A, B, S = val[bs[0]], val[bs[1]], val[bs[2]]
                r = (S & B) | ((~S) & mask & A)
                for ob in (conns.get("Y") or []):
                    if isinstance(ob, int) and val.get(ob) != r:
                        val[ob] = r
                        changed += 1
        if not changed:
            break
    return val, mask


def simulate_seq(mod: dict, names: dict, k: int, seed: int, cycles: int) -> tuple[dict[int, int], int]:
    """**k 拍顺序仿真** ✓（输入按**端口名**共享激励 ✓、FF 初值统一 0 ✓、SE 强制 0 ✓）。

    与组合版的关键差别 ✓：木马锥依赖计数器 ✗ → 必须两侧走**同一条状态轨迹** ✓ 才能让签名可比 ✓。
    签名 = 每拍值拼接（`cycles × k` bit ✓）。
    """
    rng = random.Random(seed)
    mask = (1 << k) - 1
    # 输入端口位（名字 → 位）✓ 两侧同名 → 同激励 ✓
    in_bits: dict[tuple[str, int], int] = {}
    for pname, pinfo in mod["ports"].items():
        if pinfo.get("direction") != "input":
            continue
        for i, b in enumerate([x for x in pinfo.get("bits", []) if isinstance(x, int)]):
            in_bits[(pname, i)] = b
    # 寄存器：Q/QN ← D，SE 强制 0（功能模式 ✓）
    dffs = []
    for cell in mod["cells"].values():
        t = cell.get("type", "").upper()
        if "DFF" in t or "LATCH" in t:
            c = cell.get("connections", {})
            d = [x for x in (c.get("D") or []) if isinstance(x, int)]
            q = [x for x in (c.get("Q") or []) if isinstance(x, int)]
            qn = [x for x in (c.get("QN") or []) if isinstance(x, int)]
            sbits = [x for x in (c.get("SE") or []) if isinstance(x, int)]
            dffs.append((d[:1], q[:1], qn[:1], sbits[:1]))
    val: dict[int, int] = {}
    sig: dict[int, int] = {}
    for _, q, qn, _s in dffs:                    # 初值 0 ✓（两侧一致 ✓）
        for b in q:
            val[b] = 0
        for b in qn:
            val[b] = mask

    def gv(b):
        """取位值 ✓：JSON 里常量是字符串 `"0"/"1"` ✗ → 必须当常量 ✓（否则整片网算不出来 ✗）。"""
        if isinstance(b, int):
            return val.get(b)
        s = str(b)
        if s in ("1", "1'b1"):
            return mask
        if s in ("0", "1'b0"):
            return 0
        return 0

    def comb() -> None:
        for _ in range(128):
            changed = 0
            for cell in mod["cells"].values():
                t = cell.get("type", "").upper()
                if "DFF" in t or "LATCH" in t:
                    continue
                conns = cell.get("connections", {})
                if t in FUNCS:
                    ins, ok = [], True
                    for p in FUNCS[t]:
                        bs = [x for x in (conns.get(p) or [])
                              if isinstance(x, int) or str(x) in ("0", "1")]
                        if not bs or gv(bs[0]) is None:
                            ok = False
                            break
                        ins.append(gv(bs[0]))
                    if not ok:
                        continue
                    a = ins[0]
                    if t.startswith("AND") or t.startswith("NAND"):
                        r = a & ins[1] if len(ins) > 1 else a
                        if t.startswith("NAND"):
                            r = (~r) & mask
                    elif t.startswith("OR") or t.startswith("NOR"):
                        r = a | ins[1] if len(ins) > 1 else a
                        if t.startswith("NOR"):
                            r = (~r) & mask
                    elif t.startswith("XOR"):
                        r = a ^ ins[1] if len(ins) > 1 else a
                    else:
                        r = (~a) & mask
                    for ob in (conns.get("Q") or conns.get("QN") or []):
                        if isinstance(ob, int) and val.get(ob) != r:
                            val[ob] = r
                            changed += 1
                elif t in MUXES:
                    got = []
                    ok = True
                    for p in MUXES[t]:
                        bs = [x for x in (conns.get(p) or [])
                              if isinstance(x, int) or str(x) in ("0", "1")]
                        if not bs or gv(bs[0]) is None:
                            ok = False
                            break
                        got.append(gv(bs[0]))
                    if not ok:
                        continue
                    A, B, S = got
                    r = (S & B) | ((~S) & mask & A)
                    for ob in (conns.get("Y") or []):
                        if isinstance(ob, int) and val.get(ob) != r:
                            val[ob] = r
                            changed += 1
            if not changed:
                break

    for cyc in range(cycles):
        for (pname, i), b in in_bits.items():     # 共享激励 ✓（同名端口同名位 → 同值 ✓）
            val[b] = random.Random(f"{seed}|{pname}|{i}|{cyc}").getrandbits(k)
        comb()
        for b in list(val):                      # 记录签名 ✓
            sig[b] = ((sig.get(b, 0) << k) | (val[b] & mask)) & ((1 << (k * cycles)) - 1)
        nxt = {}
        for d, q, qn, _s in dffs:                # 上升沿：Q ← D（SE=0 ✓）
            if d and q:
                nxt[q[0]] = val.get(d[0], 0)
        for d, q, qn, _s in dffs:
            for b in q:
                if b in nxt:
                    val[b] = nxt[b]
            for b in qn:
                if q and q[0] in nxt:
                    val[b] = (~nxt[q[0]]) & mask
    return sig, mask

def scope_nets(mod: dict, names: dict, hops: int = 3) -> set[int]:
    """**结构作用域** ✓：木马网 ±hops 跳内的位（只用于**限定曝光范围** ✓，不参与匹配 ✗）。"""
    bit_of = {}
    for b, n in names.items():
        bit_of.setdefault(n, b)
    con, drv = {}, {}
    for cell in mod["cells"].values():
        for port, bits in cell.get("connections", {}).items():
            for b in bits:
                if not isinstance(b, int):
                    continue
                if port in ("Y", "Q", "QN"):
                    drv.setdefault(b, cell.get("type"))
                else:
                    con.setdefault(b, []).append(cell)
    start = [b for b, n in names.items() if "trojan" in n.lower()]
    seen = set(start)
    frontier = list(start)
    for _ in range(hops):
        nxt = []
        for b in frontier:
            for cell in con.get(b, []):
                for port, bits in cell.get("connections", {}).items():
                    for ob in bits:
                        if isinstance(ob, int) and ob not in seen:
                            seen.add(ob)
                            nxt.append(ob)
            # 反向：驱动该位的单元输入
            for cell in mod["cells"].values():
                if any(isinstance(x, int) and x == b
                       for port, bits in cell.get("connections", {}).items()
                       if port in ("Y", "Q", "QN") for x in bits):
                    for port, bits in cell.get("connections", {}).items():
                        if port in ("Y", "Q", "QN"):
                            continue
                        for ib in bits:
                            if isinstance(ib, int) and ib not in seen:
                                seen.add(ib)
                                nxt.append(ib)
        frontier = nxt
    return seen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="rs232t1000")
    ap.add_argument("--inst", default="injalpha")
    ap.add_argument("--pairs", default="ys_id:ys_abc,ys_id:ys_opt")
    ap.add_argument("--k", type=int, default=256, help="仿真模式数 ✓（签名宽度 ✓）")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--max-pairs", type=int, default=600)
    ap.add_argument("--per-sig", type=int, default=2)
    ap.add_argument("--cycles", type=int, default=8, help="顺序仿真的拍数 ✓（FF 初值 0 ✓）")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--host-fold", default="hosts_bt31")
    ap.add_argument("--out", default=str(OUT_CSV))
    a = ap.parse_args()

    rows = []
    for pr in [s for s in a.pairs.split(",") if ":" in s]:
        ra, rb = [x.strip() for x in pr.split(":")]
        tdir = ROOT / "generate_trans" / "folds" / a.host_fold / "trans"
        va = sorted(tdir.glob(f"{a.host}__{a.inst}_d1_s42__*{ra}.v"))
        vb = sorted(tdir.glob(f"{a.host}__{a.inst}_d1_s42__*{rb}.v"))
        if not (va and vb):
            print(f"[skip] {pr} 缺 .v ✗")
            continue
        fa = [struct_json(va[0])]
        fb = [struct_json(vb[0])]
        topA, modA, nA = load_json(fa[0])
        topB, modB, nB = load_json(fb[0])
        t0 = time.time()
        vA, mask = simulate_seq(modA, nA, a.k, a.seed, a.cycles)
        vB, _ = simulate_seq(modB, nB, a.k, a.seed, a.cycles)
        scA, scB = scope_nets(modA, nA), scope_nets(modB, nB)
        print(f"  [{pr}] sim {time.time()-t0:.1f}s｜A nets={len(nA)} scope={len(scA)}"
              f"｜B nets={len(nB)} scope={len(scB)}")

        # ---- 候选：签名相同（常数剔除 ✓）+ 两侧都在作用域内 ✓
        norm = lambda x: str(x).strip().lstrip("\\\\")
        portA = {norm(x) for x in modA["ports"]}
        portB = {norm(x) for x in modB["ports"]}
        dwA, dwB = decl_wires(va[0]), decl_wires(vb[0])
        dwA = {str(x).strip().lstrip("\\\\") for x in dwA}
        dwB = {str(x).strip().lstrip("\\\\") for x in dwB}
        wiresA = {nm for nm, inf in modA.get("netnames", {}).items()
                  if len(inf.get("bits", [])) == 1 and norm(nm) in dwA}
        wiresB = {nm for nm, inf in modB.get("netnames", {}).items()
                  if len(inf.get("bits", [])) == 1 and norm(nm) in dwB}
        bucketA: dict[int, list[str]] = {}
        for b, s in vA.items():
            nm = norm(nA.get(b))
            if nm is None or b not in scA or nm in portA or nm not in wiresA:
                continue
            if s in (0, mask):
                continue
            if "trojan" not in nm.lower():      # A 侧**只以木马网为锚** ✓（限定范围 ✓，匹配仍靠签名 ✓）
                continue
            lst = bucketA.setdefault(s, [])
            if nm not in lst:
                lst.append(nm)
        for s in bucketA:                      # 木马网优先 ✓（只是排序 ✓，不参与匹配 ✗）
            bucketA[s].sort(key=lambda x: (0 if "trojan" in x.lower() else 1, x))

        bnets = []
        for b, s in vB.items():
            nm = norm(nB.get(b))
            if nm is None or b not in scB or nm in portB or nm not in wiresB:
                continue
            bnets.append((s, nm))
        bnets.sort(key=lambda t: (0 if "trojan" in t[1].lower() else 1, t[1]))

        cand, seen, used_a, used_b = [], set(), set(), set()
        for s, nmb in bnets:
            if nmb in used_b:                  # B 侧同一网也只能用一次 ✓（否则第二次 rename 必报 not found ✗）
                continue
            for nma in bucketA.get(s, [])[: a.per_sig]:
                if (nma, nmb) in seen or nma in used_a:
                    continue
                seen.add((nma, nmb))
                used_a.add(nma)                 # 同一 A 网只能改一次名 ✓
                used_b.add(nmb)
                cand.append((nma, nmb, s))
                if len(cand) >= a.max_pairs:
                    break
            if len(cand) >= a.max_pairs:
                break
        print(f"  [{pr}] 候选对 {len(cand)} ✓（签名 k={a.k} ✓、每签名≤{a.per_sig} ✓、"
              f"**未用名字匹配** ✓）")
        if not cand:
            rows.append(dict(host=a.host, inst=a.inst, pair=pr, net_a="", net_b="",
                             sig_hex="", status="no_candidate", log=""))
            continue
        rows += prove_pairs(a, pr, va[0], vb[0], topA, topB, cand)
    if not rows:
        print("\n[warn] 无结果 ✗")
        return 1
    df = pd.DataFrame(rows)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        old = pd.read_csv(out, encoding="utf-8-sig")
        df = pd.concat([old, df], ignore_index=True).drop_duplicates(
            subset=["host", "inst", "pair", "net_a", "net_b"], keep="last")
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n[out] {out}（{len(df)} 行 ✓）")
    print(df["status"].value_counts().to_string())
    return 0


def ref(nm: str) -> str:
    """yosys 可引用的名字 ✓（简单名直接 ✓；含 `.` 加反斜杠 ✓）。"""
    return nm if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", nm) else "\\" + nm.lstrip("\\")


def prove_pairs(a, pr, fa: Path, fb: Path, topA: str, topB: str, cand) -> list[dict]:
    """**每对单独一次 yosys** ✓（避免批量改名互相踩踏 ✗；代价 = N 次启动 ≈0.3 s/次 ✓）。"""
    rows = []
    for i, (na, nb, s) in enumerate(cand):
        sw = f"sw_{i}"
        lines = [f'read_verilog "{wsl(fa)}"', f'read_verilog "{wsl(fb)}"',
                 f"select -module {topA}", f"rename {ref(na)} {sw}",
                 f"select -module {topB}", f"rename {ref(nb)} {sw}",
                 f"equiv_make {topA} {topB} equiv", "select -module equiv",
                 "equiv_simple -undef", "equiv_induct -undef -seq 4", "equiv_status"]
        ys = LOGS / "pairwise" / f"{a.host}_{a.inst}_{pr.replace(':', '__')}_{i:04d}.ys"
        ys.parent.mkdir(parents=True, exist_ok=True)
        ys.write_text("\n".join(lines) + "\n", encoding="utf-8")
        t0 = time.time()
        try:
            p = subprocess.run(["wsl", "-e", "bash", "-lc",
                                f'cd "{WSL_ROOT}" && timeout {a.timeout} yosys -s "{wsl(ys)}"'],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=a.timeout + 60)
            out = (p.stdout or "") + (p.stderr or "")
        except subprocess.TimeoutExpired:
            out = "TIMEOUT"
        wall = round(time.time() - t0, 2)
        if f"for \\{sw}: success!" in out or f"for \\{sw}: success!" in out.replace("\\\\", "\\"):
            st = "proved"
        elif f"for \\{sw}: failed" in out:
            st = "differ"
        else:
            st = "unknown"
        if st != "proved" and "Trying to prove" in out:
            m = re.search(r"Trying to prove \$equiv for \\+sw_\d+:\s*(success!|failed)", out)
            st = "proved" if (m and m.group(1) == "success!") else ("differ" if m else st)
        rows.append(dict(host=a.host, inst=a.inst, pair=pr, net_a=na, net_b=nb,
                         sig_hex=f"{s:x}"[:16], status=st, wall_s=wall,
                         log=str(ys.with_suffix(".log").relative_to(ROOT))))
        (ys.with_suffix(".log")).write_text(out, encoding="utf-8")
    n_ok = sum(1 for r in rows if r["status"] == "proved")
    print(f"  [{pr}] 证明 {n_ok}/{len(rows)} proved ✓")
    return rows



if __name__ == "__main__":
    raise SystemExit(main())


