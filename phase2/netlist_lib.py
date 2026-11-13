# -*- coding: utf-8 -*-
"""
netlist_lib.py —— 结构化网表解析 / 依赖分析 / 合法性检查（第二块数据生成用）

只针对本仓库里那种"扁平门级 + 每行一条实例语句、以 ';' 结尾"的 Verilog，
用纯正则解析（足够稳，且能在 Windows 上秒级跑）。

核心约定：
  * 实例语句：`GATE_TYPE INST_NAME ( .PORT(net), .PORT(net), ... )`
  * **最后一个端口是输出**（在本仓库 5 个网表 + 库上逐一验证过；
    另外用"一个 net 只能有一个驱动"来自检）。

提供的检查（后面数据生成必须过的关）：
  * `lint()`：悬空输入 / 多驱动 / 输出未驱动 / 触发器数量 / 未识别语句
  * `tie_dangling()`：把悬空输入接到 1'b0（删木马后的标准修法），返回改动清单
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

COMMENT_RE = re.compile(r"//[^\n]*")
INST_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*\((?P<conns>.*)\)\s*$", re.S)
CONN_RE = re.compile(r"\.\s*([A-Za-z_]\w*)\s*\(\s*([^)]*)\s*\)")
IDENT_RE = re.compile(r"^[A-Za-z_]\w*$")
DECL_RE = re.compile(r"^\s*(input|output|inout|wire|reg)\b(?P<rest>.*)$", re.S)
MODULE_RE = re.compile(r"\bmodule\s+([A-Za-z_]\w*)\s*\((?P<ports>.*)\)\s*$", re.S)
LIB_MODULE_RE = re.compile(r"module\s+([A-Za-z_]\w*)\s*\((?P<ports>.*?)\)\s*;(?P<body>.*?)endmodule",
                           re.S)


RESERVED = {"reg", "wire", "signed", "unsigned", "input", "output", "inout", "logic"}


def _decl_names(rest: str) -> List[str]:
    rest = re.sub(r"\[[^\]]*\]", " ", rest)
    return [n for n in (x.strip() for x in re.split(r"[,\s]+", rest))
            if n and n not in RESERVED]


def load_library(lib_path: Path) -> Dict[str, Dict[str, List[str]]]:
    """从带真实实现的单元库（vali/verilog_lib.v）读出每种门的**输入/输出端口方向**。

    为什么非它不可：`SDFFSRX1_RS` 这类触发器有 `Q` 和 `QN` **两个输出**，
    "最后一个端口 = 输出"会把 `Q` 漏掉，于是所有由 `Q` 驱动的线都被误判成悬空。
    """
    text = Path(lib_path).read_text(encoding="utf-8", errors="replace")
    text = COMMENT_RE.sub("", text)
    out: Dict[str, Dict[str, List[str]]] = {}
    for m in LIB_MODULE_RE.finditer(text):
        gate = m.group(1)
        ins, outs = [], []
        for st in m.group("body").split(";"):
            mm = DECL_RE.match(st.strip())
            if not mm:
                continue
            names = _decl_names(mm.group("rest"))
            if mm.group(1) == "input":
                ins += names
            elif mm.group(1) == "output":
                outs += names
        if ins or outs:
            out[gate] = {"inputs": ins, "outputs": outs}
    return out



@dataclass
class Inst:
    gate: str
    name: str
    conns: List[Tuple[str, str]]        # [(port, net), ...]；**最后一个是输出**
    raw: str = ""

    @property
    def out_port(self) -> str:
        return self.conns[-1][0]

    @property
    def out_net(self) -> str:
        return self.conns[-1][1]

    @property
    def in_nets(self) -> List[str]:
        return [n for _p, n in self.conns[:-1]]


@dataclass
class Netlist:
    path: Path
    module: str = ""
    ports: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    wires: List[str] = field(default_factory=list)
    insts: List[Inst] = field(default_factory=list)
    assigns: List[Tuple[str, str]] = field(default_factory=list)
    head: str = ""
    port_decls: List[str] = field(default_factory=list)
    other: List[str] = field(default_factory=list)
    tail: str = ""
    tail_head: str = ""        # module 之前的 `timescale 之类
    lib: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)

    # ---- 端口方向（优先用单元库；库缺失时回落到"最后一个端口=输出"）----
    def outs(self, i: "Inst") -> List[Tuple[str, str]]:
        spec = self.lib.get(i.gate)
        if spec and spec.get("outputs"):
            o = [(p, n) for p, n in i.conns if p in spec["outputs"]]
            if o:
                return o
        return [i.conns[-1]]

    def ins(self, i: "Inst") -> List[Tuple[str, str]]:
        op = {p for p, _n in self.outs(i)}
        return [(p, n) for p, n in i.conns if p not in op]

    def drivers(self) -> Dict[str, str]:
        d: Dict[str, str] = {}
        for i in self.insts:
            for _p, n in self.outs(i):
                d.setdefault(n, i.name)
        for lhs, _rhs in self.assigns:
            d.setdefault(lhs, "assign")
        for p in self.inputs:
            d.setdefault(p, "PORT")
        return d

    def consumers(self) -> Dict[str, List[str]]:
        c: Dict[str, List[str]] = {}
        for i in self.insts:
            for _p, n in self.ins(i):
                c.setdefault(n, []).append(i.name)
        return c

    def dff_count(self) -> int:
        return sum(1 for i in self.insts
                   if "DFF" in i.gate.upper() or "LATCH" in i.gate.upper())

    def net_pool(self) -> List[str]:
        """可作 trigger 输入的候选：被驱动、非常量、非时钟/复位/扫描链。"""
        bad = re.compile(r"(clk|clock|rst|reset|test)", re.I)
        drv = self.drivers()
        return sorted(n for n in drv
                      if IDENT_RE.match(n) and not bad.search(n)
                      and not n.startswith("1'b"))


def _split_stmts(text: str) -> List[str]:
    """按 ';' 切分（这些网表里括号内没有 ';'，已在本仓库全部网表上验证）。"""
    out = []
    for chunk in text.split(";"):
        c = COMMENT_RE.sub("", chunk)
        if c.strip():
            out.append(c)
    return out


def parse_netlist(path: Path, lib: Dict[str, Dict[str, List[str]]] | None = None) -> Netlist:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    nl = Netlist(path=Path(path), lib=(lib or {}))
    for st in _split_stmts(text):
        s = st.strip()
        if not s:
            continue
        m = MODULE_RE.search(s)
        if m:
            pre = s[:m.start()].strip()          # 例：`timescale ...` 与 module 同处一个 chunk
            if pre:
                nl.tail_head = pre
            nl.module = m.group(1)
            nl.ports = [p.strip() for p in m.group("ports").replace("\n", " ").split(",")
                        if p.strip()]
            nl.head = s[m.start():]
            continue
        if s.startswith("endmodule") or s.startswith("`"):
            nl.tail += s + ";\n"
            continue
        m = DECL_RE.match(s)
        if m:
            kind = m.group(1)
            names = _decl_names(m.group("rest"))
            if kind == "input":
                nl.inputs += names
            elif kind == "output":
                nl.outputs += names
            else:
                nl.wires += names
            nl.port_decls.append(s)
            continue
        if s.startswith("assign"):
            # LHS 可能是**转义标识符**（如 `\test_point/TM`），所以 LHS 用非贪婪 .+?
            mm = re.match(r"assign\s+(.+?)\s*=\s*(.*)$", s, re.S)
            if mm:
                nl.assigns.append((mm.group(1).strip(), mm.group(2).strip()))
            else:
                nl.other.append(s)
            continue
        m = INST_RE.match(s)
        if m:
            # 注意：`.QN()` 这类**空连接**必须丢掉，否则会一起落到名为 "" 的假网上
            conns = [(p, v.strip()) for p, v in CONN_RE.findall(m.group("conns"))
                     if v.strip()]
            if conns:
                nl.insts.append(Inst(gate=m.group(1), name=m.group(2), conns=conns, raw=s))
                continue
        nl.other.append(s)
    return nl


def emit_netlist(nl: Netlist) -> str:
    """把（可能被修改过的）Netlist 写回 Verilog 文本。

    注意：net 名后面**必须留一个空格**。因为网表里有转义标识符（如 `\\test_point/DOUT`），
    Verilog 用"到空白为止"来界定转义标识符；写成 `.CK(\\test_point/DOUT)` 会把右括号
    也吞进标识符里 → yosys 报 syntax error。
    """
    body = "".join(f"  {d};\n" for d in nl.port_decls)
    for i in nl.insts:
        conns = ", ".join(f".{p}({n} )" for p, n in i.conns)
        body += f"{i.gate} {i.name} ( {conns} );\n"
    for lhs, rhs in nl.assigns:
        # 注意：parser2 的 fixassigns() 同样依赖"2 空格缩进 + 右值紧跟 ';'"的格式
        # （它做 3 次 split(' ',1) 再按 ' = ' 切），所以这里不能加多余空格
        body += f"  assign {lhs} = {rhs};\n"
    for o in nl.other:
        # 未识别语句也要保持 2 空格缩进：parser2 的 getprimlist/fixassigns 都靠它定位
        body += "  " + o.strip() + ";\n"
    pre = (nl.tail_head + ";\n") if nl.tail_head else ""
    return f"{pre}{nl.head};\n{body}endmodule\n"


CONST_RE = re.compile(r"^\d+'[bodhBODH][0-9a-fA-FxXzZ_]+$")


def lint(nl: Netlist) -> dict:
    """合法性检查：clean=True 表示无悬空输入 / 无多驱动 / 输出都被驱动。"""
    drv = nl.drivers()
    cons = nl.consumers()
    dangling = sorted({n for n in cons if n not in drv and IDENT_RE.match(n)})
    multi: Dict[str, List[str]] = {}
    for i in nl.insts:
        for _p, n in nl.outs(i):
            multi.setdefault(n, []).append(i.name)
    multi_l = sorted(n for n, v in multi.items() if len(v) > 1 and n not in nl.outputs)
    # 位向量端口的名字对不上（端口声明被剥掉了 [7:0]，而连接写的是 rec_dataH[0]）
    # → 用前缀匹配判断"这个输出端口是否被驱动"
    def _out_driven(o: str) -> bool:
        return o in drv or any(k.startswith(o + "[") for k in drv)
    undriven_out = sorted({o for o in nl.outputs if not _out_driven(o)})
    return {"dangling_inputs": dangling, "multi_driven": multi_l,
            "undriven_outputs": undriven_out,
            "n_dangling": len(dangling), "n_multi": len(multi_l),
            "n_undriven_out": len(undriven_out),
            "n_inst": len(nl.insts), "n_dff": nl.dff_count(), "n_other": len(nl.other),
            "module": nl.module,
            "clean": not dangling and not multi_l and not undriven_out}


def tie_dangling(nl: Netlist, value: str = "1'b0") -> List[dict]:
    """把悬空输入接到常量（默认 1'b0），返回改动清单。**就地修改 nl**。"""
    drv = nl.drivers()
    cons = nl.consumers()
    dang = {n for n in cons if n not in drv and IDENT_RE.match(n)}
    changes = []
    for i in nl.insts:
        in_ports = {p for p, _n in nl.ins(i)}
        for k, (p, n) in enumerate(i.conns):
            if p in in_ports and n in dang:
                i.conns[k] = (p, value)
                changes.append({"inst": i.name, "gate": i.gate, "port": p,
                                "was": n, "now": value})
    return changes


def learn_gate_templates(nls: List[Netlist]) -> Dict[str, List[str]]:
    """从真实实例里"学"每种门的端口顺序（用于生成新门时套用同样的模板）。"""
    tpl: Dict[str, List[str]] = {}
    for nl in nls:
        for i in nl.insts:
            tpl.setdefault(i.gate, [p for p, _n in i.conns])
    return tpl


def pick_gate(lib: Dict[str, dict], want_inputs: int, prefer: List[str]) -> str | None:
    """挑一个**输入端口数 = want_inputs** 的门类型；优先 prefer 列表里的。

    兼容两种传入：`lib`（{gate: {"inputs": [...], "outputs": [...]}}，
    来自 `load_library`）与 `templates`（{gate: [ports]}，来自 `learn_gate_templates`）。
    """
    def n_in(spec) -> int:
        if isinstance(spec, dict):
            return len(spec.get("inputs", []))
        return len(spec) - 1
    cand = [g for g, spec in lib.items() if n_in(spec) == want_inputs]
    for g in prefer:
        if g in cand:
            return g
    return cand[0] if cand else None
