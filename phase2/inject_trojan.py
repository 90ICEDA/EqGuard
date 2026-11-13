# -*- coding: utf-8 -*-
"""
inject_trojan.py —— 第二块：受控木马/合法对照的**注入器** + 干净基底构建

决策（已定）：
  D1 机制      = **组合触发 + 组合载荷**
  D2 功能      = **A 型（功能等价）**：载荷只驱动一条**没有扇出的新线** `<prefix>_payload_k`
                 → 原设计的所有输出/状态完全不变 → 可做**全量 CEC**
  D3 干净基底  = 从 infected 网表**删掉原有木马 + 把留下的悬空输入接到 1'b0**
  D5 实例维度  = 触发输入个数 / 触发树风格 / 载荷风格 / 载荷长度 / 插入锚点（组合覆盖）
  D6 合法对照  = rare_and / deep_xor / dup_logic / debug_gated（都"像木马但没木马语义"）

命名约定（**很重要**）：`parser2` 的标签来源是"实例名是否含 `trojan`"，
所以木马门的名字**必须**含 `Trojan`，对照门的名字**必须不含** `trojan`（大小写均可）。

用法：
  python phase2/inject_trojan.py build --hosts rs232t1000,s15850t100,s38417t300 \
      --out-dir generate_trans/hosts --instances 6 --controls 4
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase2 import netlist_lib as NL  # noqa: E402
from phase2.repair_hijack import repair as hijack_repair  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NETS = ROOT / "generate_trans" / "nets"
LIB_DEFAULT = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"

AND2_PREF = ["AND2X2", "AND2X1", "AND2X1_RS"]
NAND2_PREF = ["NAND2X0", "NAND2X1", "NAND2X1_RS", "NOR2X0"]
XOR2_PREF = ["XOR2X1", "XOR2X1_RS", "XNOR2X1"]
INV_PREF = ["INVX0", "INVX1_RS", "INVX8_S"]
MUX_PREF = ["MUX21X2", "MX2X1_RS"]


def _mk(nl: NL.Netlist, gate: str, name: str, nets):
    """按模板造一个实例（端口顺序照抄真实门的模板）。"""
    tpl = nl.lib.get(gate)
    if tpl is None:
        raise KeyError(f"库里没有 {gate}")
    ports = tpl["inputs"] + tpl["outputs"]
    if len(ports) != len(nets):
        raise ValueError(f"{gate} 需要 {len(ports)} 个端口，给了 {len(nets)}")
    return NL.Inst(gate=gate, name=name, conns=list(zip(ports, nets)))


def inject(nl: NL.Netlist, lib, spec: dict, rng: random.Random):
    """就地往 nl 里插一个块；返回 provenance 记录。"""
    tpl_of = lambda g: lib.get(g, {}).get("inputs", [])
    pool = nl.net_pool()
    if len(pool) < 12:
        raise RuntimeError("可用信号太少")
    kind = spec["kind"]
    prefix = spec["name_prefix"]
    new = []
    prov = {"kind": kind, "ctl_type": spec.get("ctl_type"), "prefix": prefix,
            "n_trig": spec.get("n_trig"), "trig_style": spec.get("trig_style"),
            "payload_style": spec.get("payload_style"),
            "payload_len": spec.get("payload_len"), "new_gates": []}

    # ---------- 合法对照 A：复制一段已有良性逻辑（冗余但无害）----------
    if kind == "control" and spec.get("ctl_type") == "dup_logic":
        cand = [i for i in nl.insts
                if "DFF" not in i.gate.upper() and len(lib.get(i.gate, {}).get("outputs", [])) == 1]
        for j, src in enumerate(rng.sample(cand, min(int(spec["payload_len"]), len(cand)))):
            op = lib[src.gate]["outputs"][0]
            conns = [(p, (f"{prefix}_dup{j}" if p == op else n)) for p, n in src.conns]
            new.append(NL.Inst(gate=src.gate, name=f"{prefix}DUP{j}", conns=conns))
        prov["new_gates"] = [i.name for i in new]
        nl.insts += new
        return prov

    # ---------- 合法对照：只造"触发样"的逻辑，不接载荷 ----------
    if kind == "control" and spec.get("ctl_type") == "deep_xor":
        g = NL.pick_gate(lib, 2, XOR2_PREF)
        cur = rng.sample(pool, 1)[0]
        for k in range(int(spec["payload_len"])):
            s = rng.sample(pool, 1)[0]
            w = f"{prefix}_x{k}"
            new.append(_mk(nl, g, f"{prefix}X{k}", [cur, s, w]))
            cur = w
        dead = f"{prefix}_dead"
        gi = NL.pick_gate(lib, 1, INV_PREF)
        new.append(_mk(nl, gi, f"{prefix}Buf", [cur, dead]))
        prov["new_gates"] = [i.name for i in new]
        nl.insts += new
        return prov

    # ---------- 触发树（木马与 rare_and 共用）----------
    n_trig = int(spec["n_trig"])
    tgts = rng.sample(pool, n_trig)
    gate_and = NL.pick_gate(lib, 2, AND2_PREF)
    gate_nand = NL.pick_gate(lib, 2, NAND2_PREF)
    gate_inv = NL.pick_gate(lib, 1, INV_PREF)
    style = spec["trig_style"]
    cur = tgts[0]
    for k in range(1, n_trig):
        w = f"{prefix}_t{k}"
        if style == "and":
            new.append(_mk(nl, gate_and, f"{prefix}T{k}", [cur, tgts[k], w]))
        elif style == "nand_inv":
            t = f"{prefix}_tn{k}"
            new.append(_mk(nl, gate_nand, f"{prefix}TN{k}", [cur, tgts[k], t]))
            new.append(_mk(nl, gate_inv, f"{prefix}TI{k}", [t, w]))
        elif style == "cmp":
            # E1 新族 ✓：两网 XOR 再取反 → 近似"相等比较"触发 ✓（活动概率更低 ✓）
            g_xor = NL.pick_gate(lib, 2, XOR2_PREF)
            t = f"{prefix}_tx{k}"
            new.append(_mk(nl, g_xor, f"{prefix}TX{k}", [cur, tgts[k], t]))
            new.append(_mk(nl, gate_inv, f"{prefix}TY{k}", [t, w]))
        else:  # mux2 风格：用 mux 当"选择器"，结构上更像控制逻辑
            g = NL.pick_gate(lib, 3, MUX_PREF) or gate_nand
            new.append(_mk(nl, g, f"{prefix}TM{k}", [cur, tgts[k], tgtor(tgts, k), w]))
        cur = w
    trig_wire = cur

    # ---------- 对照 rare_and：到此为止，接一条死线 ----------
    #  注意：ctl_type=="matched" 的对照**不走这里** —— 它要和木马一样建完整载荷，
    #  这样两边在结构上严格可比（负对照）。
    if kind == "control" and spec.get("ctl_type") != "matched":
        dead = f"{prefix}_dead"
        if spec.get("ctl_type") == "debug_gated":
            pass  # 触发信号池里已排除 test*；debug 变体仍接死线，仅记录类型
        new.append(_mk(nl, gate_inv, f"{prefix}D0", [trig_wire, dead]))
        prov["new_gates"] = [i.name for i in new]
        nl.insts += new
        return prov

    # ---------- 载荷（组合、只驱动死线 → 功能等价）----------
    pstyle = spec["payload_style"]
    plen = int(spec["payload_len"])
    if pstyle == "xor_chain":
        g = NL.pick_gate(lib, 2, XOR2_PREF)
        cur = trig_wire
        for k in range(plen):
            s = rng.choice([n for n in pool])
            w = f"{prefix}_p{k}"
            new.append(_mk(nl, g, f"{prefix}P{k}", [cur, s, w]))
            cur = w
        out = cur
    elif pstyle == "mux":
        g = NL.pick_gate(lib, 3, MUX_PREF)
        a = rng.sample(pool, 1)[0]
        cur = a
        for k in range(plen):
            w = f"{prefix}_p{k}"
            new.append(_mk(nl, g, f"{prefix}P{k}", [a, trig_wire, f"{prefix}_s{k}", w]))
            new.append(_mk(nl, gate_inv, f"{prefix}S{k}", [cur, f"{prefix}_s{k}"]))
            cur = w
        out = cur
    elif pstyle == "flip":
        # E1 新族 ✓：**单门载荷** —— 触发时把被劫持输出直接置 1 ✓（最极端的"硬翻转" ✓）
        out = trig_wire
    else:  # and_tree：触发 AND 上一簇信号
        g = gate_and
        cur = trig_wire
        for k in range(plen):
            s = rng.choice(pool)
            w = f"{prefix}_p{k}"
            new.append(_mk(nl, g, f"{prefix}P{k}", [cur, s, w]))
            cur = w
        out = cur
    # ---------- 载荷出口 ----------
    #   dead       : A 型（功能等价）—— 只驱动一条**没有扇出的新线**，原设计功能完全不变
    #   hijack_out : B 型（**条件性功能篡改**）—— 触发选通后**劫持一个真实输出端口**：
    #                把原驱动的输出改到 <Y>_orig，再用 MUX(sel=触发) 在 Y 上二选一。
    #                非触发时输出原值（隐蔽），触发时被载荷改写 ⇒ 功能真的变了。
    #                关键副作用：载荷的脉冲距离**归零**（它直接连到一个 PO）。
    if spec.get("payload_target") == "hijack_out":
        drv = {}
        for i in nl.insts:
            for _p, n in nl.outs(i):
                drv.setdefault(n, i)
        cands = sorted(o for o in nl.outputs if o in drv)
        if cands:
            Y = rng.choice(cands)
            I = drv[Y]
            I.conns = [(p, (Y + "_orig" if n == Y else n)) for p, n in I.conns]
            g_mux = NL.pick_gate(lib, 3, MUX_PREF)
            new.append(_mk(nl, g_mux, f"{prefix}HJ", [Y + "_orig", out, trig_wire, Y]))
            prov["payload_wire"] = Y
            prov["hijacked_output"] = Y
            prov["payload_target"] = "hijack_out"
            prov["new_gates"] = [i.name for i in new]
            nl.insts += new
            return prov
    # 死线（无扇出）→ 原设计功能完全不变
    dead = f"{prefix}_payload"
    new.append(_mk(nl, gate_inv, f"{prefix}PD", [out, dead]))
    prov["payload_wire"] = dead
    prov["payload_target"] = "dead"
    prov["new_gates"] = [i.name for i in new]
    nl.insts += new
    return prov


def tgtor(pool, k):
    return pool[(k + 1) % len(pool)]


# D5：6 个实例覆盖"触发规模 / 触发风格 / 载荷风格 / 载荷长度"四个维度
TROJAN_SPECS = [
    dict(kind="trojan", name_prefix="TrojanA", ops="injalpha",
         n_trig=2, trig_style="and", payload_style="xor_chain", payload_len=3),
    dict(kind="trojan", name_prefix="TrojanB", ops="injbeta",
         n_trig=3, trig_style="and", payload_style="and_tree", payload_len=3),
    dict(kind="trojan", name_prefix="TrojanC", ops="injgamma",
         n_trig=4, trig_style="nand_inv", payload_style="xor_chain", payload_len=4),
    dict(kind="trojan", name_prefix="TrojanD", ops="injdelta",
         n_trig=5, trig_style="and", payload_style="mux", payload_len=3),
    dict(kind="trojan", name_prefix="TrojanE", ops="injepsilon",
         n_trig=3, trig_style="mux", payload_style="xor_chain", payload_len=5),
    dict(kind="trojan", name_prefix="TrojanF", ops="injzeta",
         n_trig=4, trig_style="and", payload_style="xor_chain", payload_len=6),
    # 10.13 本轮补的两个"覆盖矩阵空白角"（不改 inject() 逻辑，只扩参数）
    #   G：触发输入数 6（现有最大 5）
    #   H：mux 触发 × and_tree 载荷（现有无此组合）
    dict(kind="trojan", name_prefix="TrojanG", ops="injeta",
         n_trig=6, trig_style="and", payload_style="xor_chain", payload_len=4),
    dict(kind="trojan", name_prefix="TrojanH", ops="injtheta",
         n_trig=2, trig_style="mux", payload_style="and_tree", payload_len=6),
    dict(kind="trojan", name_prefix="TrojanI", ops="injcmp",
         n_trig=3, trig_style="cmp", payload_style="xor_chain", payload_len=2),
    dict(kind="trojan", name_prefix="TrojanJ", ops="injflip",
         n_trig=2, trig_style="and", payload_style="flip", payload_len=0),
]
# D6：合法对照。**A0 修正**：主对照与木马"结构一一匹配"
#     —— 同样的 触发规模 / 触发风格 / 载荷风格 / 载荷长度 / 载荷→死线，
#        只是门名前缀是 `Ctl`（不含 trojan）且触发信号另抽一批。
#     这样"结构上无可区分"是**预期结果**（负对照），任何 AUC≠0.5 都说明夹带了伪影。
CONTROL_SPECS = [
    dict(kind="control", ctl_type="matched", name_prefix="CtlMA", ops="ctlmatcha",
         match="TrojanA", n_trig=2, trig_style="and", payload_style="xor_chain", payload_len=3),
    dict(kind="control", ctl_type="matched", name_prefix="CtlMB", ops="ctlmatchb",
         match="TrojanB", n_trig=3, trig_style="and", payload_style="and_tree", payload_len=3),
    dict(kind="control", ctl_type="matched", name_prefix="CtlMC", ops="ctlmatchc",
         match="TrojanC", n_trig=4, trig_style="nand_inv", payload_style="xor_chain", payload_len=4),
    dict(kind="control", ctl_type="matched", name_prefix="CtlMD", ops="ctlmatchd",
         match="TrojanD", n_trig=5, trig_style="and", payload_style="mux", payload_len=3),
    dict(kind="control", ctl_type="matched", name_prefix="CtlME", ops="ctlmatche",
         match="TrojanE", n_trig=3, trig_style="mux", payload_style="xor_chain", payload_len=5),
    dict(kind="control", ctl_type="matched", name_prefix="CtlMF", ops="ctlmatchf",
         match="TrojanF", n_trig=4, trig_style="and", payload_style="xor_chain", payload_len=6),
    # 非触发型补充：深 XOR 链（无触发树）/ 冗余复制逻辑
    dict(kind="control", ctl_type="deep_xor", name_prefix="CtrlX", ops="ctlxor",
         n_trig=0, trig_style=None, payload_style=None, payload_len=6),
    dict(kind="control", ctl_type="dup_logic", name_prefix="CtrlD", ops="ctldup",
         n_trig=0, trig_style=None, payload_style=None, payload_len=5),
    # 10.13 本轮：与新增木马一一匹配的负对照（rng key = match → 结构一一对应）
    dict(kind="control", ctl_type="matched", name_prefix="CtlMG", ops="ctlmatchg",
         match="TrojanG", n_trig=6, trig_style="and", payload_style="xor_chain", payload_len=4),
    dict(kind="control", ctl_type="matched", name_prefix="CtlMH", ops="ctlmatchh",
         match="TrojanH", n_trig=2, trig_style="mux", payload_style="and_tree", payload_len=6),
]


def rename_module(nl: NL.Netlist, new: str) -> None:
    """把模块名改成新名字（矩阵里的视图就是各自独立的模块名）。

    必须做：CEC 要把 golden 与 candidate 一起读进来，同名模块会报
    `Re-definition of module` → 必须让每个视图有自己的模块名。
    """
    old = nl.module
    nl.head = re.sub(r"\bmodule\s+" + re.escape(old) + r"\b", "module " + new,
                     nl.head, count=1)
    nl.module = new


def build_host(host: str, out_root: Path, lib, n_inst: int, n_ctl: int, seed: int):
    """产出一个 host 的：干净基底 + N 个木马实例 + M 个合法对照。"""
    hdir = out_root / host
    (hdir / "base").mkdir(parents=True, exist_ok=True)
    rows, prov_rows = [], []

    src = NL.parse_netlist(NETS / f"{host}.v", lib)
    lint0 = NL.lint(src)
    # **关键正确性点**：门类型必须来自"该 host 自己用到的族"
    # （rs232 用 `_RS` 族、s 系用非 `_RS` 族；混用 yosys 会无法解析）
    host_gates = {i.gate for i in src.insts}
    hlib = {g: lib[g] for g in host_gates if g in lib}
    arity = {}
    for g, spec in hlib.items():
        arity.setdefault(len(spec["inputs"]), 0)
        arity[len(spec["inputs"])] += 1
    print(f"[{host}] 可用门类型 {len(hlib)} 种（按输入端口数: {dict(sorted(arity.items()))}）")
    for need, name in ((1, "inv"), (2, "and/xor/nand"), (3, "mux")):
        if arity.get(need, 0) == 0:
            print(f"   [WARN] host 里没有 {need} 输入的门 → {name} 相关的注入会跳过")
    n_del = sum(1 for i in src.insts if "trojan" in i.name.lower())
    dff_del = src.dff_count() - sum(1 for i in src.insts
                                   if "trojan" not in i.name.lower()
                                   and ("DFF" in i.gate.upper() or "LATCH" in i.gate.upper()))
    # **用显式修复表还原被木马劫持的信号**（不用自动判据；表在 repair_hijack.py 里）
    rep = hijack_repair(src, host, NETS / f"{host}.v")
    lint1 = NL.lint(src)
    base_path = hdir / "base" / f"{host}_clean.v"
    rename_module(src, f"{host}_clean")
    base_path.write_text(NL.emit_netlist(src), encoding="utf-8")
    (hdir / "base" / f"{host}_clean_report.json").write_text(json.dumps({
        "host": host, "src": str(NETS / f"{host}.v"), "n_trojan_deleted": n_del,
        "n_dff_deleted": dff_del, "hijack_repair": rep,
        "lint_src": {k: v for k, v in lint0.items() if k != "dangling_inputs"},
        "lint_base": {k: v for k, v in lint1.items() if k != "dangling_inputs"},
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[{host}] clean base: 删木马 {n_del} 门（含 {dff_del} 个触发器）｜"
          f"最小修复 {rep['n_fixed']} 处（未解 {rep['n_unresolved']}）｜"
          f"base clean={lint1['clean']}（dangling={lint1['n_dangling']} "
          f"undriven_out={lint1['n_undriven_out']}）")

    for spec_list, cnt, kind in ((TROJAN_SPECS, n_inst, "trojan"),
                                 (CONTROL_SPECS, n_ctl, "control")):
        for spec in spec_list[:cnt]:
            # A'：`match` 让对照与对应木马**共用同一批触发/载荷信号**
            #（rng 种子相同 → 信号抽样顺序相同 → 结构完全一致，只有门名不同）
            rng_key = spec.get("match") or spec["name_prefix"]
            rng = random.Random(f"{host}-{rng_key}-{seed}")
            nl = NL.parse_netlist(base_path, hlib | {g: lib[g] for g in lib})  # 先按 host 族解析
            nl.lib = hlib                                                       # 注入只用 host 族的门
            try:
                prov = inject(nl, hlib, spec, rng)
            except Exception as exc:                   # noqa: BLE001
                print(f"   [SKIP] {host}/{spec['ops']}: {exc}")
                continue
            L = NL.lint(nl)
            view = f"{host}__{spec['ops']}_d1_s{seed}"
            rename_module(nl, view)          # ← 必须：否则 CEC 会报模块重定义
            (hdir / f"{view}.v").write_text(NL.emit_netlist(nl), encoding="utf-8")
            prov.update({"host": host, "view": view, "lint_after_inject": {
                k: v for k, v in L.items() if k != "dangling_inputs"}})
            prov_rows.append(prov)
            rows.append({
                "host": host, "view": view, "kind": kind,
                "ctl_type": spec.get("ctl_type") or "", "n_trig": spec.get("n_trig") or 0,
                "trig_style": spec.get("trig_style") or "",
                "payload_style": spec.get("payload_style") or "",
                "payload_len": spec.get("payload_len") or 0,
                "n_new_gates": len(prov["new_gates"]),
                "base_clean": bool(lint1["clean"]), "inject_clean": bool(L["clean"]),
                "netlist": str(hdir / f"{view}.v")})
    (hdir / "provenance.json").write_text(json.dumps(prov_rows, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="第二块：受控木马/对照注入 + 干净基底")
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--hosts", type=str,
                    default="rs232t1000,s15850t100,s35932t200,s38417t100,s38584t100")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "generate_trans" / "hosts")
    ap.add_argument("--instances", type=int, default=6)
    ap.add_argument("--controls", type=int, default=8)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--lib", type=Path, default=LIB_DEFAULT)
    args = ap.parse_args()

    lib = NL.load_library(args.lib)
    print(f"[lib] {args.lib} → {len(lib)} 种门")
    all_rows = []
    for h in [x for x in args.hosts.split(",") if x.strip()]:
        all_rows += build_host(h, args.out_dir, lib, args.instances, args.controls, args.seed)
    import pandas as pd
    df = pd.DataFrame(all_rows)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_dir / "instances.csv", index=False, encoding="utf-8-sig")
    print(f"\n[OK] {len(df)} 个视图 → {args.out_dir}")
    print(df.groupby(["host", "kind"]).size().to_string())
    print(f"[导出] {args.out_dir / 'instances.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
