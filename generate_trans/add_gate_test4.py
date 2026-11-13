#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
equiv_rewrite_netlist.py v1.0.0 (label-blind rewrite + transformation matrix)

v1.0.0（分任务4）新增：
  - 4 种机制不同的 operator family：
      decomp   : De Morgan / 混合门族 / 带反相器的分解（rule bucket = decomp）
      balance  : 同族结合律重结合（rule bucket = balance，优先浅树）
      refactor : 1:1 / 1:2 局部结构重构（rule bucket = refactor）
      resub    : 基于网表上下文的 resubstitution（不使用规则表；复用已有等价/取反/除数逻辑）
    另有 compose 组合算子：--chain decomp,refactor 或 --depth N（depth = chain 长度）。
  - view 级元数据补齐 edit_count / gate_expansion / depth_change / composition_depth / operator_chain
    / 逐步 step_stats / 规则表达式 provenance / 文件 SHA1 与 freeze 标签。
  - rule_mode：legacy（默认，decomp 与旧版行为完全一致）/ partitioned（按机制纯度选规则，矩阵实验用）。
  - pipeline 修复：QN 等互补输出端口、总线位选、规则形参可绑定预校验、重写主循环尝试上限、
    溯源链在门被消除后可解析、元数据 CSV 表头安全升级。

功能：
1. 从 orig/ 目录读取原始网表，生成 label-blind 等价变换视图
2. 自动生成日志文件
3. 从 add_location.txt 读取特定位置的分解规则
4. 输出 mapping JSON、view-level metadata CSV、节点对齐明细 CSV

注：
- --in 只需传文件名，脚本会从 orig/ 目录查找
- --out 的父目录会被忽略，一律写入 --view-root（默认 trans/）
- mapping JSON 和 view_metadata CSV 里的 src/dst 都是纯文件名

用法：
    python add_gate_test4.py --lib verilog_lib.v --map map.txt --rules rule_expand1.txt \
        --seed 42 --in rs232t1000.v --out rs232t1000tr42.v --mapping-out rs232t1000tr42.JSON \
        --operator-family decomp --rule-mode legacy --max-rewrites 50

    python add_gate_test4.py --lib verilog_lib.v --map map.txt --rules rule_expand1.txt \
        --seed 42 --in rs232t1000.v --out rs232t1000__decomp-refactor_d2_s42.v \
        --chain decomp,refactor --rule-mode partitioned --max-rewrites 50
"""

import argparse
import ast
import copy
import io
import json
import random
import re
import tokenize
import sys
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Union
from datetime import datetime

Width = Optional[Tuple[int, int]]  # (msb, lsb) or None

# -----------------------------
# Data models
# -----------------------------

@dataclass
class Decl:
    name: str
    width: Width = None

@dataclass
class Assign:
    lhs: str
    rhs: str

@dataclass
class Instance:
    cell: str
    name: str
    conns: Dict[str, str]  # port -> net/const

@dataclass
class ModuleNetlist:
    name: str
    ports: List[str]
    decl_order: List[Tuple[str, List[Decl]]] = field(default_factory=list)
    assigns: List[Assign] = field(default_factory=list)
    instances: List[Instance] = field(default_factory=list)


# -----------------------------
# Utilities: strip python comments safely
# -----------------------------

def strip_py_comments(text: str) -> str:
    """Remove # comments while preserving strings, using tokenize."""
    out = []
    tokgen = tokenize.generate_tokens(io.StringIO(text).readline)
    for tok_type, tok_str, _, _, _ in tokgen:
        if tok_type == tokenize.COMMENT:
            continue
        out.append(tok_str)
    return "".join(out)

def load_py_dict_from_file(path: Path, var_name_hint: str) -> dict:
    """
    Files are like:
      self.gate_equivalences = { ... }
    We'll:
      - remove comments
      - find the first '{' and matching last '}' and literal_eval that dict
    """
    raw = path.read_text(encoding="utf-8", errors="ignore")
    raw = strip_py_comments(raw)
    # locate dict literal
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise ValueError(f"Cannot find dict literal in {path}")
    dtext = raw[start:end+1]
    try:
        return ast.literal_eval(dtext)
    except Exception as e:
        raise ValueError(f"Failed to parse dict in {path}: {e}")

# -----------------------------
# Parse verilog_lib.v (cell port order)
# -----------------------------

LIB_MOD_RE = re.compile(r"module\s+(?P<name>\w+)\s*\((?P<ports>[^;]*?)\)\s*;", re.S)

def parse_lib_info(lib_text: str) -> Tuple[Dict[str, List[str]], Dict[str, Set[str]], Dict[str, List[str]]]:
    """Parse verilog_lib.v and return:
    - lib_ports:  cell -> port list (as declared in module header)
    - lib_outs:   cell -> set of output port names (parsed from output declarations)

    NOTE: We intentionally do NOT assume the output port is the last port in the header.
    Many libs keep outputs in the middle or use names like S/CO, etc.
    """
    lib_ports: Dict[str, List[str]] = {}
    lib_outs: Dict[str, Set[str]] = {}
    lib_ins: Dict[str, List[str]] = {}

    # Get header port order
    for m in LIB_MOD_RE.finditer(lib_text):
        name = m.group("name")
        ports_raw = m.group("ports")
        ports = [p.strip() for p in ports_raw.replace("\n", " ").split(",") if p.strip()]
        lib_ports[name] = ports

    # Parse module bodies for 'output' declarations
    # This is a lightweight Verilog parser good enough for typical cell libs.
    mod_re = re.compile(r"module\s+(?P<name>\w+)\b.*?;(?P<body>.*?)endmodule", re.S)
    decl_re = re.compile(r"^\s*output\b(?P<payload>[^;]*);", re.M)

    def _decl_names(payload: str) -> List[str]:
        payload = " ".join(payload.replace("\n", " ").split())
        # remove ranges like [3:0]
        payload = re.sub(r"\[[^\]]+\]", "", payload).strip()
        # remove keywords like reg/wire/signed
        payload = re.sub(r"\b(reg|wire|signed)\b", "", payload).strip()
        return [x.strip() for x in payload.split(",") if x.strip()]

    for mm in mod_re.finditer(lib_text):
        name = mm.group("name")
        body = mm.group("body")
        outs: Set[str] = set()
        for dm in decl_re.finditer(body):
            outs.update(_decl_names(dm.group("payload")))
        if outs:
            lib_outs[name] = outs
        else:
            lib_outs[name] = set()

        # Derive ordered input port lists from header order minus outputs
    for cell, ports in lib_ports.items():
        outs = lib_outs.get(cell, set())
        lib_ins[cell] = [p for p in ports if p not in outs]

    return lib_ports, lib_outs, lib_ins
# -----------------------------
# Parse gate-level netlist (robust for multiline decl/inst)
# -----------------------------

RE_TIMESCALE = re.compile(r"^\s*`timescale\s+(\S+)\s*$", re.M)
RE_MODULE_HDR = re.compile(r"module\s+(\w+)\s*\((.*?)\)\s*;", re.S)
RE_BUS = re.compile(r"\[(\d+)\s*:\s*(\d+)\]")
RE_ASSIGN_STMT = re.compile(r"^\s*assign\s+(.+?)\s*=\s*(.+?)\s*$", re.S)
RE_DECL_STMT = re.compile(r"^\s*(input|output|wire)\s+(.+?)\s*$", re.S)

def _split_names(list_text: str) -> List[str]:
    return [x.strip() for x in list_text.split(",") if x.strip()]

def _parse_decl_payload(payload: str) -> List[Decl]:
    payload = " ".join(payload.replace("\n", " ").split())
    m = RE_BUS.search(payload)
    width: Width = None
    if m:
        width = (int(m.group(1)), int(m.group(2)))
        payload = RE_BUS.sub("", payload).strip()
    names = _split_names(payload)
    return [Decl(name=n, width=width) for n in names]

def parse_gatelevel_verilog(text: str) -> Tuple[str, ModuleNetlist]:
    timescale = "1ns/100ps"
    m_ts = RE_TIMESCALE.search(text)
    if m_ts:
        timescale = m_ts.group(1)

    m_hdr = RE_MODULE_HDR.search(text)
    if not m_hdr:
        raise ValueError("Cannot find module header.")
    mod_name = m_hdr.group(1)
    ports_raw = m_hdr.group(2)
    ports = [p.strip() for p in ports_raw.replace("\n", " ").split(",") if p.strip()]
    mod = ModuleNetlist(name=mod_name, ports=ports)

    # only parse inside module body
    body = text[m_hdr.end():]
    body = body.split("endmodule")[0]
    body = re.sub(r"//.*?\n", "\n", body)           # 剔除单行注释 //
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S) # 剔除块注释 /* */

    # split by ';' into statements
    stmts = [s.strip() for s in body.split(";") if s.strip()]

    inst_re = re.compile(r"^\s*(\w+)\s+(\w+)\s*\((.*)\)\s*$", re.S)
    pin_re  = re.compile(r"\.(\w+)\s*\(\s*([^\)]+?)\s*\)")

    for st in stmts:
        # decl?
        md = RE_DECL_STMT.match(st)
        if md:
            kind = md.group(1)
            decls = _parse_decl_payload(md.group(2))
            mod.decl_order.append((kind, decls))
            continue

        # assign?
        ma = RE_ASSIGN_STMT.match(st)
        if ma:
            mod.assigns.append(Assign(lhs=ma.group(1).strip(), rhs=ma.group(2).strip()))
            continue

        # instance?
        mi = inst_re.match(st)
        if mi:
            cell, name, pinblob = mi.group(1), mi.group(2), mi.group(3)
            pinblob = " ".join(pinblob.replace("\n", " ").split())
            conns = {pm.group(1): pm.group(2).strip() for pm in pin_re.finditer(pinblob)}
            if conns:
                mod.instances.append(Instance(cell=cell, name=name, conns=conns))
            continue

    return timescale, mod


# -----------------------------
# Style formatter (rs232-like)
# -----------------------------

def _wrap_comma_list(items: List[str], first_indent: str, cont_indent: Optional[str] = None, width: int = 79) -> str:
    if cont_indent is None:
        cont_indent = " " * len(first_indent)
    lines: List[str] = []
    cur = first_indent
    for i, it in enumerate(items):
        suf = "," if i != len(items) - 1 else ""
        tok = it + suf
        tentative = (cur + tok) if cur == first_indent else (cur + " " + tok)
        if len(tentative) > width:
            lines.append(cur.rstrip())
            cur = cont_indent + tok
        else:
            cur = tentative
    lines.append(cur.rstrip())
    return "\n".join(lines)

def _fmt_decl_stmt(kind: str, decls: List[Decl]) -> str:
    """Try to mimic rs232 style: bus decl in its own stmt if it was that way originally."""
    buses = [d for d in decls if d.width]
    singles = [d for d in decls if not d.width]
    out: List[str] = []

    def emit(width_txt: str, names: List[str]) -> None:
        if not names:
            return
        head = f"  {kind} {width_txt}".rstrip() + " "
        out.append(_wrap_comma_list(names, head, " " * len(head)) + ";")

    for w in sorted({d.width for d in buses}, key=lambda x: (-x[0], x[1])):  # type: ignore
        msb, lsb = w  # type: ignore
        emit(f"[{msb}:{lsb}]", [d.name for d in buses if d.width == w])
    emit("", [d.name for d in singles])
    return "\n".join(out)

def _fmt_assigns(assigns: List[Assign]) -> str:
    return "\n".join([f"  assign {a.lhs} = {a.rhs};" for a in assigns]) if assigns else ""

def _fmt_instance(inst: Instance, lib_ports: Dict[str, List[str]], width: int = 79) -> str:
    order = lib_ports.get(inst.cell, [])
    ports = list(inst.conns.keys())

    def sort_key(p: str):
        return (0, order.index(p)) if p in order else (1, p)

    ports_sorted = sorted(ports, key=sort_key)
    pairs = [f".{p}({inst.conns[p]})" for p in ports_sorted]

    head = f"{inst.cell} {inst.name} ( "
    cont = " " * len(head)
    lines: List[str] = []
    cur = head

    for i, tok in enumerate(pairs):
        tok2 = tok + ("," if i != len(pairs) - 1 else "")
        tentative = cur + tok2 if cur == head else cur + " " + tok2
        if len(tentative) > width:
            lines.append(cur.rstrip())
            cur = cont + tok2
        else:
            cur = tentative
    lines.append(cur.rstrip() + " );")
    return "\n".join(["  " + lines[0]] + ["  " + ln for ln in lines[1:]])

def emit_verilog(timescale: str, mod: ModuleNetlist, lib_ports: Dict[str, List[str]]) -> str:
    out: List[str] = []
    out.append(f"`timescale {timescale}")
    out.append("")
    out.append(f"module {mod.name} (")
    out.append(_wrap_comma_list(mod.ports, "  ", "  "))
    out.append("  );")

    for kind, decls in mod.decl_order:
        out.append(_fmt_decl_stmt(kind, decls))

    out.append("")
    a = _fmt_assigns(mod.assigns)
    if a:
        out.append(a)
        out.append("")

    for inst in mod.instances:
        out.append(_fmt_instance(inst, lib_ports))

    out.append("")
    out.append("endmodule")
    out.append("")
    return "\n".join(out)


# -----------------------------
# Equivalent expression AST
# -----------------------------

@dataclass
class ExprCall:
    fn: str
    args: List["Expr"]  # ExprCall | str (var/const)

Expr = Union[ExprCall, str]  # str used for var names like 'A' or const like 1'b0


def parse_equiv_expr(s: str) -> Expr:
    """Parse expressions like INV(NAND2(A,B)) into an AST."""
    s = s.strip()

    # if no '(' => leaf
    if "(" not in s:
        return s

    # parse function call
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)$", s)
    if not m:
        # fallback: treat as leaf
        return s
    fn = m.group(1)
    inside = m.group(2).strip()

    # split args by commas respecting parentheses depth
    args: List[str] = []
    depth = 0
    cur = []
    for ch in inside:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        args.append("".join(cur).strip())

    return ExprCall(fn=fn, args=[parse_equiv_expr(a) for a in args if a])


# -----------------------------
# Gate typing + port binding
# -----------------------------

OUTPUT_PORT_CANDIDATES = ["Y", "Q", "ZN", "Z", "Q_N", "S", "SUM", "SO", "S0", "CO", "COUT", "C1"]

def simplify_cell(cell: str, gate_simplification: Dict[str, str]) -> str:
    # exact match first
    if cell in gate_simplification:
        return gate_simplification[cell]
    # try strip suffix variants
    c2 = cell.replace("_RS", "")
    if c2 in gate_simplification:
        return gate_simplification[c2]
    # try partial match by prefix key (conservative)
    for k, v in gate_simplification.items():
        if k in cell:
            return v
    return cell

def is_sequential_simple(simple_type: str) -> bool:
    return simple_type in {"DFF", "SDFFSR"}

def pick_output_port(inst: Instance,
                    lib_ports: Dict[str, List[str]],
                    lib_outs: Dict[str, Set[str]]) -> Optional[str]:
    """Pick the output port of an instance robustly.

    Priority:
      1) If instance connections contain a known output-ish name (OUTPUT_PORT_CANDIDATES), use it.
      2) If the library declares output ports for this cell, choose:
           - the one that appears in OUTPUT_PORT_CANDIDATES if possible
           - otherwise if only 1 output, use it
           - otherwise fall back to the first declared output in header order
      3) As a last resort, fall back to the last header port (legacy behavior).
    """
    # 1) direct by common names
    for p in OUTPUT_PORT_CANDIDATES:
        if p in inst.conns:
            return p

    ports = lib_ports.get(inst.cell, [])

    # 2) from library output declarations
    outs = lib_outs.get(inst.cell, set())
    if outs:
        # prefer a candidate output name
        for p in OUTPUT_PORT_CANDIDATES:
            if p in outs and p in ports:
                return p
            if p in outs:
                return p
        # single output
        if len(outs) == 1:
            return next(iter(outs))
        # fall back to first output in header order
        for p in ports:
            if p in outs:
                return p
        # or arbitrary
        return next(iter(outs))

    # 3) legacy
    if ports:
        return ports[-1]
    return None

def bind_formals(simple_type: str, inst: Instance, lib_ports: Dict[str, List[str]], lib_outs: Dict[str, Set[str]]) -> Dict[str, str]:
    """
    根据规则文件映射变量。
    逻辑：
    1. 提取所有输入端口，按库中的声明顺序排列。
    2. 默认按顺序绑定 A, B, C, D, E, F。
    3. 针对 MUX, ISOLAND, LSDN, HADD 等特殊规则进行名称校准。
    """
    conns = inst.conns
    bound: Dict[str, str] = {}
    st = simple_type

    # 1. 获取输入端口列表（排除输出端口，保留库定义的原始顺序）
    out_ports = lib_outs.get(inst.cell, set())
    all_ports = lib_ports.get(inst.cell, [])
    # 过滤掉输出端口，剩下的按顺序作为输入映射源
    input_ports = [p for p in all_ports if p in conns and p not in out_ports]

    # 2. 基础映射：将第1-6个输入分别映射为 A, B, C, D, E, F
    # 这解决了绝大多数组合逻辑门（AND, OR, AOI, OAI）的问题
    for i, p_name in enumerate(input_ports):
        if i < 6:
            formal_char = chr(ord('A') + i)
            bound[formal_char] = conns[p_name]

    # 3. 针对规则文件中的特殊变量名进行增强映射
    
    # 别名映射：很多规则使用 'IN' 代替 'A' (如 NBUFF, BUF)
    if "A" in bound:
        bound["IN"] = bound["A"]

    # MUX2 映射：规则需要 A, B, S
    if st == "MUX2":
        # 尝试寻找选择信号 S
        for p in conns:
            if p.upper() in {"S", "S0", "SEL", "SE"}:
                bound["S"] = conns[p]
        # 如果没找到叫 S 的端口，通常 MUX 的最后一个输入是 S
        if "S" not in bound and len(input_ports) >= 3:
            bound["S"] = conns[input_ports[-1]]
            # 重新修正 A, B（取前两个）
            bound["A"] = conns[input_ports[0]]
            bound["B"] = conns[input_ports[1]]

    # ISOLAND / LSDNEN / LSDN 映射：规则需要 D, ISO, ENB
    if st in {"ISOLAND", "LSDNEN", "LSDN"}:
        # D 通常映射自 A (第一个输入)
        if "A" in bound: bound["D"] = bound["A"]
        # 寻找 ISO 或 ENB
        for p in conns:
            p_up = p.upper()
            if "ISO" in p_up: bound["ISO"] = conns[p]
            if "ENB" in p_up: bound["ENB"] = conns[p]

    # HADD 映射：规则需要 A0, B0, C1
    if st == "HADD":
        # 如果端口名本身就叫 A0, B0... 直接对应
        for p in ["A0", "B0", "C1"]:
            if p in conns: bound[p] = conns[p]
        # 否则按顺序：A0=第1个, B0=第2个, C1=第3个
        if "A0" not in bound and len(input_ports) >= 1: bound["A0"] = conns[input_ports[0]]
        if "B0" not in bound and len(input_ports) >= 2: bound["B0"] = conns[input_ports[1]]
        if "C1" not in bound and len(input_ports) >= 3: bound["C1"] = conns[input_ports[2]]

    # DFF / SDFFSR 映射：需要 D, CLK, SI, SE, RSTB...
    if st in {"DFF", "SDFFSR"}:
        for p in conns:
            p_up = p.upper()
            
            # --- 1. 识别时钟 CLK ---
            if p_up in {"CLK", "CK", "CP", "CLOCK"}:
                bound["CLK"] = conns[p]
            
            # --- 2. 识别数据 D ---
            elif p_up in {"D", "IN", "DATA"}:
                bound["D"] = conns[p]
            
            # --- 3. 识别扫描信号 SI / SE ---
            elif p_up in {"SI", "SDI", "SCANIN"}:
                bound["SI"] = conns[p]
            elif p_up in {"SE", "SCANEN", "SENA"}:
                bound["SE"] = conns[p]
                
            # --- 4. 识别复位/置位 RSTB / SETB ---
            elif p_up in {"RSTB", "RN", "CDN", "RESET", "RESETB", "RST"}:
                bound["RSTB"] = conns[p]
            elif p_up in {"SETB", "SN", "SDN", "SET", "PREB", "PRESET"}:
                bound["SETB"] = conns[p]
            
            # --- 5. 识别输出 Q ---
            elif p_up in {"Q", "OUT"}:
                bound["Q"] = conns[p]

        # 兜底逻辑：如果规则里用了 CLK 但没搜到，尝试取所有输入里的最后一个
        if "CLK" not in bound:
            # 这里的 input_ports 是前面提取出来的输入列表
            if input_ports:
                bound["CLK"] = conns[input_ports[-1]]

    # 4. 清理无效绑定并返回
    return {k: v for k, v in bound.items() if v}

def collect_declared_wires(mod: ModuleNetlist) -> Set[str]:
    s = set()
    for kind, decls in mod.decl_order:
        for d in decls:
            if kind == "wire":
                s.add(d.name)
    return s

def collect_ports(mod: ModuleNetlist) -> Set[str]:
    s = set(mod.ports)
    for kind, decls in mod.decl_order:
        if kind in {"input", "output"}:
            for d in decls:
                s.add(d.name)
    return s

def ensure_wire_decl(mod: ModuleNetlist, name: str):
    s = name.strip()

    # 跳过空/常量/明显的表达式
    if not s or s in {"1'b0", "1'b1"}:
        return
    if any(ch in s for ch in "{}()=,+-*/&|^~?!"):
        return

    # foo[3] / foo[7:0] -> foo（也兼容 escaped identifier: \foo.bar[3]）
    m = re.match(
        r"^(?P<base>(?:\\\S+|[A-Za-z_]\w*))\s*\[\s*\d+\s*(?::\s*\d+\s*)?\]\s*$",
        s
    )
    if m:
        s = m.group("base")

    # 端口不声明为 wire
    if s in collect_ports(mod):
        return

    # wire 去重：全局扫描所有 wire decl，已存在则不再追加
    for k, decls in mod.decl_order:
        if k == "wire":
            if any(d.name == s for d in decls):
                return

    # 追加到第一个 wire 组（若存在），否则新建 wire 组
    for k, decls in mod.decl_order:
        if k == "wire":
            decls.append(Decl(name=s, width=None))
            return

    mod.decl_order.append(("wire", [Decl(name=s, width=None)]))



# -----------------------------
# Choosing real cells for a simplified gate
# -----------------------------

def build_simple_to_cells(lib_ports: Dict[str, List[str]], gate_simplification: Dict[str, str]) -> Dict[str, List[str]]:
    simple2cells: Dict[str, List[str]] = {}
    for cell in lib_ports.keys():
        st = simplify_cell(cell, gate_simplification)
        simple2cells.setdefault(st, []).append(cell)
    return simple2cells

def pick_cell_for_simple(simple_type: str, prefer_cell: Optional[str],
                         simple2cells: Dict[str, List[str]]) -> Optional[str]:
    if prefer_cell and prefer_cell in simple2cells.get(simple_type, []):
        return prefer_cell
    cells = simple2cells.get(simple_type, [])
    if not cells:
        return None
    return sorted(cells)[0]


# =============================================================================
# 分任务4 基础设施：表达式度量 / 规则家族划分 / 网表深度 / view 元数据
# =============================================================================

TOOL_NAME = "equiv_rewrite_netlist"
TOOL_VERSION = "1.0.0"

#: 不作为“同族结合律(balance)”判据的门（反相器、缓冲器）
_INV_BUF_FNS = {"INV", "BUF", "NBUFF"}

#: 可交换的二输入门（resub 的 divisor 匹配时输入顺序无关）
COMMUTATIVE_2IN_FNS = {"AND2", "OR2", "NAND2", "NOR2", "XOR2", "XNOR2"}

#: 取反互补门对（resub 的“已有反相网表复用”）
COMPLEMENT_TYPE_PAIRS = {
    "AND2": "NAND2", "NAND2": "AND2",
    "AND3": "NAND3", "NAND3": "AND3",
    "AND4": "NAND4", "NAND4": "AND4",
    "OR2": "NOR2", "NOR2": "OR2",
    "OR3": "NOR3", "NOR3": "OR3",
    "OR4": "NOR4", "NOR4": "OR4",
    "XOR2": "XNOR2", "XNOR2": "XOR2",
    "XOR3": "XNOR3", "XNOR3": "XOR3",
}

#: 触发器（时序边界）：深度计算与 resub 都跳过
SEQUENTIAL_SIMPLE_TYPES = {"DFF", "SDFFSR"}


def file_sha1(path: Union[str, Path]) -> str:
    """文件 SHA1（用于 freeze 校验），失败返回空串。"""
    import hashlib
    try:
        h = hashlib.sha1()
        with open(str(path), "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def expr_node_count(expr: Expr) -> int:
    """表达式中的门节点数（叶子不计）。"""
    if isinstance(expr, str):
        return 0
    return 1 + sum(expr_node_count(a) for a in expr.args)


def expr_max_depth(expr: Expr) -> int:
    """表达式深度（单个门为 1）。"""
    if isinstance(expr, str):
        return 0
    return 1 + max([expr_max_depth(a) for a in expr.args] or [0])


def expr_fns(expr: Expr) -> List[str]:
    """表达式里出现的所有门类型。"""
    if isinstance(expr, str):
        return []
    out = [expr.fn]
    for a in expr.args:
        out.extend(expr_fns(a))
    return out


def expr_leaves(expr: Expr) -> List[str]:
    """表达式里的所有叶子符号（形参或常量）。"""
    if isinstance(expr, str):
        return [expr]
    out: List[str] = []
    for a in expr.args:
        out.extend(expr_leaves(a))
    return out


def fn_family(fn: str) -> str:
    """把门类型归一到运算符族：NAND->AND, NOR->OR, XNOR->XOR, 其余保持。"""
    if fn.startswith("NAND") or fn.startswith("AND"):
        return "AND"
    if fn.startswith("NOR") or fn.startswith("OR"):
        return "OR"
    if fn.startswith("XNOR") or fn.startswith("XOR"):
        return "XOR"
    return fn


def _has_duplicate_args(expr: Expr) -> bool:
    """表达式中是否存在同一个门的两个参数完全相同（等价于幂等改写，如 AND2(A,A)）。"""
    if isinstance(expr, str):
        return False
    ss = [repr(a) for a in expr.args]
    if len(ss) != len(set(ss)):
        return True
    return any(_has_duplicate_args(a) for a in expr.args)


def rule_bucket(simple_type: str, expr_str: str) -> str:
    """
    把一条等价规则划分到互斥的机制家族：

      - idempotent: 含重复参数的幂等改写（如 AND2(A,A) / INV→NAND2(A,A)），四个机制家族都不选用；
      - balance   : 纯结合律重结合（表达式内所有门都属于目标门的 and/or/xor 同族，且无 INV/BUF）；
      - refactor  : 1:1 或 1:2 的局部结构重构（节点数 <= 2，门数不膨胀）；
      - decomp    : 其余（De Morgan / 混合门族 / 带反相器的分解，通常膨胀门数并加深逻辑）。
    """
    try:
        expr = parse_equiv_expr(expr_str)
    except Exception:
        return "decomp"
    if _has_duplicate_args(expr):
        return "idempotent"
    fns = expr_fns(expr)
    if fns and all((f not in _INV_BUF_FNS) and (fn_family(f) == fn_family(simple_type)) for f in fns):
        return "balance"
    if expr_node_count(expr) <= 2:
        return "refactor"
    return "decomp"


def rule_pref_key(bucket: str, expr_str: str) -> Tuple[float, ...]:
    """同一 bucket 内的规则偏好排序键（越小越优先）。"""
    try:
        expr = parse_equiv_expr(expr_str)
    except Exception:
        return (1e9, 1e9)
    nodes = expr_node_count(expr)
    depth = expr_max_depth(expr)
    if bucket == "balance":
        # 结合律：优先浅树（平衡），其次多做重结合
        return (float(depth), -float(nodes))
    if bucket == "refactor":
        # 局部结构重构：优先 1:1（零膨胀），再优先浅
        return (float(nodes), float(depth))
    # decomp：优先“膨胀更多”的分解（更多门、更深），拉开与 balance/refactor 的机制差异
    return (-float(nodes), -float(depth))


def rule_formals_bindable(expr_str: str, formal_bind: Dict[str, str]) -> bool:
    """检查规则里的全部叶子能否被 formal_bind 绑定（常量除外）。"""
    try:
        expr = parse_equiv_expr(expr_str)
    except Exception:
        return False
    for leaf in expr_leaves(expr):
        if leaf in {"1'b0", "1'b1", "1'bz"}:
            continue
        if leaf not in formal_bind:
            return False
    return True


# -----------------------------
# 网表深度 / 结构统计
# -----------------------------

def _is_sequential_cell(cell: str, gate_simplification: Optional[Dict[str, str]] = None) -> bool:
    st = simplify_cell(cell, gate_simplification) if gate_simplification else cell
    if st in SEQUENTIAL_SIMPLE_TYPES:
        return True
    return bool(re.match(r"^(S?DFF|DFF)", st.upper()))


#: 常见输出端口名（库声明缺失时的兜底判据；注意 MUX 的 S 只在库无声明时才可能被误判）
_OUTPUT_PORT_RE = re.compile(r"^(Q|QN|Q_N|QB|Z|ZN|Y|YN|S|SO|SUM|CO|COUT|C1)$")
#: 库声明里缺失、但实际网表中确实作为输出的互补端口（例如 SDFFSRX1_RS 缺 QN 声明）
_EXTRA_OUTPUT_PORT_RE = re.compile(r"^(QN|Q_N|QB|ZN|YN|CO_N)$")


def instance_output_ports(inst: Instance,
                          lib_outs: Dict[str, Set[str]]) -> Set[str]:
    """
    返回该实例的所有输出端口名。

    优先使用库声明；若库声明不完整（如 SDFFSRX1_RS 只声明 Q，网表却连接 .QN(...)），
    则把实例上出现的互补输出端口（QN/ZN/...）也算作输出。
    库完全未知时，退化为按端口名模式判断。
    """
    declared = {p for p in lib_outs.get(inst.cell, set()) if p in inst.conns}
    if declared:
        extra = {p for p in inst.conns
                 if p not in declared and _EXTRA_OUTPUT_PORT_RE.match(p.upper())}
        return declared | extra
    return {p for p in inst.conns if _OUTPUT_PORT_RE.match(p.upper())}


def instance_primary_output_port(inst: Instance,
                                 lib_ports: Dict[str, List[str]],
                                 lib_outs: Dict[str, Set[str]]) -> Optional[str]:
    """实例的主输出端口（多输出如 DFF 的 Q/QN 只取一个，用于需要单一 sink 的场景）。"""
    outs = instance_output_ports(inst, lib_outs)
    if len(outs) == 1:
        return next(iter(outs))
    return pick_output_port(inst, lib_ports, lib_outs)


def strip_bit_select(sig: str) -> str:
    """把 'xmit_dataH[3]' / 'xmit_dataH[7:0]' 归一到基名 'xmit_dataH'。"""
    return re.sub(r"\[[^\]]*\]", "", str(sig)).strip()




def compute_netlist_depth(mod: ModuleNetlist,
                          lib_ports: Dict[str, List[str]],
                          lib_outs: Dict[str, Set[str]],
                          gate_simplification: Optional[Dict[str, str]] = None) -> Dict[str, int]:
    """
    组合逻辑深度（门级层数，不含触发器自身）：

      - PI / 模块输入端口 / assign 左侧 / **触发器输出** 一律视为第 0 层；
      - 组合门的层数 = 1 + max(输入网层数)；
      - depth = 所有组合门层数的最大值（DFF 自身不计入，避免把时间步当逻辑层）；
      - cycle_count = 无法定层的组合门数（未驱动网 / 组合环），会被保守赋 1 层。

    返回 dict(gate_count, depth, seq_count, cycle_count, net_count)
    """
    consts = {"1'b0", "1'b1", "1'bz"}
    level_net: Dict[str, int] = {}

    # 1) 第 0 层：PI / 端口 / assign 左侧
    for p in mod.ports:
        level_net.setdefault(p, 0)
    for kind, decls in mod.decl_order:
        if kind == "input":
            for d in decls:
                level_net[d.name] = 0
    for a in mod.assigns:
        level_net.setdefault(a.lhs, 0)

    # 2) 时序边界：DFF 输出（含 Q/QN）直接为第 0 层；DFF 自身不参与组合深度
    seq_count = 0
    comb_insts: List[Instance] = []
    for inst in mod.instances:
        if _is_sequential_cell(inst.cell, gate_simplification):
            seq_count += 1
            for p in instance_output_ports(inst, lib_outs):
                net = inst.conns.get(p)
                if net:
                    level_net[net] = 0
        else:
            comb_insts.append(inst)

    # 3) 组合门 Kahn 松弛：只有输入层都已知的门才能定层
    level_inst: Dict[str, int] = {}

    def _known(sig: str) -> bool:
        return (sig in level_net) or (strip_bit_select(sig) in level_net) or (sig in consts)

    def _lvl(sig: str) -> int:
        if sig in level_net:
            return level_net[sig]
        return level_net.get(strip_bit_select(sig), 0)

    pending: List[Instance] = list(comb_insts)
    progress = True
    while pending and progress:
        progress = False
        nxt: List[Instance] = []
        for inst in pending:
            out_ports = instance_output_ports(inst, lib_outs)
            if not out_ports:
                level_inst[inst.name] = 1
                progress = True
                continue
            in_sigs = [v for k, v in inst.conns.items() if k not in out_ports]
            if any(not _known(s) for s in in_sigs):
                nxt.append(inst)
                continue
            cur = 1 + max([_lvl(s) for s in in_sigs] or [0])
            level_inst[inst.name] = cur
            for p in out_ports:
                net = inst.conns.get(p)
                if net:
                    level_net[net] = cur
            progress = True
        pending = nxt

    cycle_count = len(pending)
    for inst in pending:  # 未驱动网 / 组合环：保守赋 1 层
        level_inst[inst.name] = 1

    return {
        "gate_count": len(mod.instances),
        "depth": max(level_inst.values()) if level_inst else 0,
        "seq_count": seq_count,
        "cycle_count": cycle_count,
        "net_count": len(level_net),
    }


def netlist_stats(mod: ModuleNetlist,
                  lib_ports: Dict[str, List[str]],
                  lib_outs: Dict[str, Set[str]],
                  gate_simplification: Optional[Dict[str, str]] = None) -> Dict[str, int]:
    """view 级网表统计（门数 / 组合深度 / 触发器数）。"""
    return compute_netlist_depth(mod, lib_ports, lib_outs, gate_simplification)


def netlist_signature(mod: ModuleNetlist,
                      lib_ports: Dict[str, List[str]],
                      lib_outs: Dict[str, Set[str]],
                      gate_simplification: Optional[Dict[str, str]] = None) -> Dict[str, int]:
    """结构签名：门数/深度 + 关键门类计数（用于量化家族机制差异）。"""
    hist: Dict[str, int] = defaultdict(int)
    for inst in mod.instances:
        key = simplify_cell(inst.cell, gate_simplification) if gate_simplification else inst.cell
        hist[key] += 1
    st = netlist_stats(mod, lib_ports, lib_outs, gate_simplification)
    return {
        "gate_count": st["gate_count"],
        "depth": st["depth"],
        "inv_count": hist.get("INV", 0),
        "buf_count": hist.get("BUF", 0) + hist.get("NBUFF", 0),
        "and_count": sum(v for k, v in hist.items() if k.startswith("AND")),
        "or_count": sum(v for k, v in hist.items() if k.startswith("OR")),
        "x2_count": sum(hist.get(k, 0) for k in ("AND2", "OR2", "NAND2", "NOR2")),
        "wide_count": sum(v for k, v in hist.items()
                          if k[-1:] in {"3", "4"} or k.endswith(("221", "222"))),
    }


def compose_alignment(prev_alignment: Dict[str, List[str]],
                      step_alignment: Dict[str, List[str]],
                      alive_names: Set[str]) -> Dict[str, List[str]]:
    """
    把两步的节点溯源串起来：prev(src -> 中间名) ∘ step(中间名 -> 新名)。
    中间名若既不在 step_alignment 中、也不在新网表里，说明它被彻底消除 → 丢弃。
    """
    merged: Dict[str, List[str]] = {}
    for src, mids in prev_alignment.items():
        out: List[str] = []
        for mid in mids:
            if mid in step_alignment:
                out.extend(step_alignment[mid])
            elif mid in alive_names:
                out.append(mid)
        dedup: List[str] = []
        for n in out:
            if n not in dedup:
                dedup.append(n)
        if dedup:
            merged[src] = dedup
    return merged


def merge_rewrite_stats(stats_list: List["RewriteStats"],
                        gate_equivalences: Optional[Dict[str, dict]] = None) -> "RewriteStats":
    """把多步算子的 RewriteStats 合并成一个（组合变换视图用）。"""
    merged = RewriteStats(gate_equivalences)
    for s in stats_list:
        if s is None:
            continue
        merged.total_rewrites += s.total_rewrites
        merged.total_added_gates += s.total_added_gates
        merged.rewritten_instances |= set(s.rewritten_instances)
        merged.csv_records.extend(list(s.csv_records))
        for gtype, d in s.rule_use_counts.items():
            for k, v in d.items():
                merged.rule_use_counts[gtype][k] += v
        for gtype, d in s.rule_selection_counts.items():
            tgt = merged.rule_selection_counts.setdefault(gtype, {})
            for k, v in d.items():
                tgt[k] = tgt.get(k, 0) + v
    return merged


# -----------------------------
# view 元数据（分任务4：edit count / gate expansion / depth change）
# -----------------------------

VIEW_METADATA_FIELDS: List[str] = [
    # 标识
    "view_name", "src_verilog", "dst_verilog",
    # 变换描述
    "operator_family", "operator_chain", "composition_depth", "rule_mode",
    "seed", "strength", "max_rewrites",
    # 规模 / 编辑量 / 深度
    "orig_gate_count", "final_gate_count", "edit_count", "gate_expansion",
    "gate_expansion_ratio", "total_added_gates", "successful_rewrite_count",
    "depth_orig", "depth_final", "depth", "depth_change", "depth_change_ratio",
    "orig_net_count", "final_net_count", "edit_ratio",
    # 网表质量诊断（未定层组合门 / 触发器数）
    "seq_gate_count", "orig_cycle_count", "final_cycle_count",
    # 细粒度信息
    "bucket_edit_counts_json", "rule_use_counts_json", "step_stats_json",
    # 冻结信息
    "tool_name", "tool_version", "freeze_tag",
    "lib_sha1", "map_sha1", "rules_sha1",
]


def _count_edit_buckets(stats: "RewriteStats") -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for rec in getattr(stats, "csv_records", []) or []:
        counts[str(rec.get("规则家族", "unknown"))] += 1
    return dict(counts)


def build_view_metadata_row(*,
                            view_name: str,
                            src_verilog: str,
                            dst_verilog: str,
                            operator_family: str,
                            operator_chain: List[str],
                            seed: int,
                            strength: float,
                            max_rewrites: int,
                            orig_stats: Dict[str, int],
                            out_stats: Dict[str, int],
                            stats: "RewriteStats",
                            rule_mode: str = "legacy",
                            step_records: Optional[List[Dict[str, object]]] = None,
                            freeze_tag: str = "",
                            lib_sha1: str = "",
                            map_sha1: str = "",
                            rules_sha1: str = "",
                            extra: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    """构造一行 view 级元数据（单文件 CLI 与 matrix_builder 共用，保证 schema 一致）。"""
    og = int(orig_stats.get("gate_count", 0))
    fg = int(out_stats.get("gate_count", 0))
    od = int(orig_stats.get("depth", 0))
    fd = int(out_stats.get("depth", 0))
    edit_count = len(getattr(stats, "csv_records", []) or [])
    row: Dict[str, object] = {
        "view_name": view_name,
        "src_verilog": src_verilog,
        "dst_verilog": dst_verilog,
        "operator_family": operator_family,
        "operator_chain": "+".join(operator_chain),
        "composition_depth": len(operator_chain),
        "rule_mode": rule_mode,
        "seed": seed,
        "strength": strength,
        "max_rewrites": max_rewrites,
        "orig_gate_count": og,
        "final_gate_count": fg,
        "edit_count": edit_count,
        "gate_expansion": fg - og,
        "gate_expansion_ratio": round((fg - og) / max(1, og), 6),
        "total_added_gates": getattr(stats, "total_added_gates", 0),
        "successful_rewrite_count": getattr(stats, "total_rewrites", 0),
        "depth_orig": od,
        "depth_final": fd,
        "depth": fd,
        "depth_change": fd - od,
        "depth_change_ratio": round((fd - od) / max(1, od), 6),
        "orig_net_count": int(orig_stats.get("net_count", 0)),
        "final_net_count": int(out_stats.get("net_count", 0)),
        "edit_ratio": round(edit_count / max(1, og), 6),
        "seq_gate_count": int(out_stats.get("seq_count", 0)),
        "orig_cycle_count": int(orig_stats.get("cycle_count", 0)),
        "final_cycle_count": int(out_stats.get("cycle_count", 0)),
        "bucket_edit_counts_json": json.dumps(_count_edit_buckets(stats), ensure_ascii=False),
        "rule_use_counts_json": json.dumps(
            {k: {str(kk): vv for kk, vv in v.items()}
             for k, v in getattr(stats, "rule_use_counts", {}).items()},
            ensure_ascii=False),
        "step_stats_json": json.dumps(step_records or [], ensure_ascii=False),
        "tool_name": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "freeze_tag": freeze_tag,
        "lib_sha1": lib_sha1,
        "map_sha1": map_sha1,
        "rules_sha1": rules_sha1,
    }
    if extra:
        row.update(extra)
    return row


def append_view_metadata_csv(path: Union[str, Path], row: Dict[str, object],
                            fields: Optional[List[str]] = None) -> None:
    """
    追加一行 view 元数据；若已有文件表头缺列，则安全升级表头（旧行补空），
    避免新旧 schema 混写导致列错位。
    """
    import csv as _csv
    path = Path(path)
    fields = list(fields or VIEW_METADATA_FIELDS)
    for k in row.keys():
        if k not in fields:
            fields.append(k)

    old_rows: List[Dict[str, object]] = []
    old_header: List[str] = []
    if path.exists():
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rd = _csv.DictReader(f)
            old_header = list(rd.fieldnames or [])
            old_rows = [dict(r) for r in rd]

    merged_header = list(old_header)
    for k in fields:
        if k not in merged_header:
            merged_header.append(k)

    def _norm(d: Dict[str, object], keys: List[str]) -> Dict[str, object]:
        return {k: (d.get(k) if d.get(k) is not None else "") for k in keys}

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        wr = _csv.DictWriter(f, fieldnames=merged_header)
        wr.writeheader()
        for r in old_rows:
            wr.writerow(_norm(r, merged_header))
        wr.writerow(_norm(row, merged_header))








# -----------------------------
# 门增加重写器（改进版：迭代重写，随机选择门）
# -----------------------------

@dataclass
class RewriteLimits:
    strength: float
    max_rewrites: int

@dataclass
class ExpansionRuleInfo:
    expr: str
    gate_score: float
    normality_score: float
    merge_potential: float
    inv_buf_penalty: float
    redundancy_penalty: float
    depth_score: float
    total: float

class RewriteStats:
    """记录重写统计信息"""
    def __init__(self, gate_equivalences: dict = None):
        self.total_rewrites = 0
        self.rewritten_instances: Set[str] = set()
        self.rule_selection_counts: Dict[str, Dict[int, int]] = {}
        self.rule_use_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.csv_records = []
        self.total_added_gates = 0

        if gate_equivalences:
            for gtype, data in gate_equivalences.items():
                self.rule_use_counts[gtype] = {i: 0 for i in range(len(data.get('equivalent', [])))}

class BaseOperator:
    """所有 operator family 的基类。"""
    family_name = "base"

    def __init__(self,
                 lib_ports: Dict[str, List[str]],
                 lib_outs: Dict[str, Set[str]],
                 lib_ins: Dict[str, List[str]],
                 gate_simplification: Dict[str, str],
                 gate_equivalences: Dict[str, dict],
                 seed: int,
                 location_map: Optional[Dict[str, str]] = None,
                 log_writer=None,
                 netlist_id: str = "default"):
        self.lib_ports = lib_ports
        self.lib_outs = lib_outs
        self.lib_ins = lib_ins
        self.gate_simplification = gate_simplification
        self.gate_equivalences = gate_equivalences
        self.rng = random.Random(seed)
        self.location_map = location_map or {}
        self.log_writer = log_writer
        self.netlist_id = netlist_id

    def apply(self, mod: ModuleNetlist, limits: "RewriteLimits") -> Tuple[ModuleNetlist, "RewriteStats", Dict[str, List[str]]]:
        """
        返回 (out_mod, stats, node_mappings_dict)。
        node_mappings_dict: {orig_inst_name: [trans_inst_name, ...]}
        """
        raise NotImplementedError


class DecompOperator(BaseOperator):
    """基于 gate_equivalences 的门分解/扩展（当前实现）。"""
    family_name = "decomp"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.simple2cells = build_simple_to_cells(self.lib_ports, self.gate_simplification)
        # 在规则被重排之前，先记住“规则表达式 -> 规则文件中的原始序号”，保证 provenance 可追溯
        self.rule_expr_to_raw_index: Dict[str, Dict[str, int]] = {
            st: {e: i for i, e in enumerate(rules.get("equivalent", []) or [])}
            for st, rules in self.gate_equivalences.items()
        }
        self._reorder_gate_equivalences_for_expansion()
        self.net_used: Set[str] = set()
        self.name_used: Set[str] = set()
        self.parent_map: Dict[str, str] = {}
        self.node_mappings: List[Dict[str, str]] = []
        self.stats = RewriteStats(self.gate_equivalences)

    # 以下方法从 GateExpander 原样搬迁：
    def _log(self, message: str):
        if self.log_writer:
            self.log_writer.write(message + "\n")
        print(message)

    def _fresh_net(self, base: str) -> str:
        i = 0
        while True:
            n = f"n_{base}_{i}"
            if n not in self.net_used:
                self.net_used.add(n)
                return n
            i += 1

    def _generate_instance_name(self, origin_inst_name: str, fn: str, counter: int) -> str:
        base_name = f"{origin_inst_name}_{counter}"
        i = 0
        while True:
            candidate = base_name if i == 0 else f"{base_name}_{i}"
            if candidate not in self.name_used:
                self.name_used.add(candidate)
                return candidate
            i += 1

    def _init_used(self, mod: ModuleNetlist):
        ports = collect_ports(mod)
        self.net_used |= ports
        self.net_used |= collect_declared_wires(mod)
        for a in mod.assigns:
            self.net_used.add(a.lhs)
        for inst in mod.instances:
            self.name_used.add(inst.name)
            for sig in inst.conns.values():
                if sig not in {"1'b0", "1'b1"}:
                    self.net_used.add(sig)

    def _expr_metrics(self, expr: Expr) -> Dict[str, float]:
        # ... 原样保留 GateExpander._expr_metrics
        def walk(e, depth=1):
            if isinstance(e, str):
                return {"nodes": 0, "depth": 0, "inv": 0, "buf": 0, "dup": 0, "wide": 0, "aoi": 0, "mux": 0, "vars": [e]}
            vars_seen = []
            nodes = 1
            max_depth = depth
            inv = 1 if e.fn == "INV" else 0
            buf = 1 if e.fn in {"BUF", "NBUFF"} else 0
            wide = 1 if e.fn.endswith("3") or e.fn.endswith("4") or e.fn.endswith("221") or e.fn.endswith("222") else 0
            aoi = 1 if any(tag in e.fn for tag in ["AO", "OA"]) else 0
            mux = 1 if e.fn.startswith("MUX") else 0
            dup = max(0, len(e.args) - len({str(a) for a in e.args}))
            for a in e.args:
                sub = walk(a, depth+1)
                nodes += sub["nodes"]
                max_depth = max(max_depth, sub["depth"])
                inv += sub["inv"]
                buf += sub["buf"]
                dup += sub["dup"]
                wide += sub["wide"]
                aoi += sub["aoi"]
                mux += sub["mux"]
                vars_seen.extend(sub["vars"])
            return {"nodes": nodes, "depth": max_depth, "inv": inv, "buf": buf, "dup": dup, "wide": wide, "aoi": aoi, "mux": mux, "vars": vars_seen}
        return walk(expr)

    def _simple_gate_expand_priority(self, simple_type: str) -> float:
        # ... 原样保留 GateExpander._simple_gate_expand_priority
        priority = {
            "AOI222": 1.00, "OAI222": 1.00, "AO222": 0.98, "OA222": 0.98,
            "AOI221": 0.96, "OAI221": 0.96, "AO221": 0.94, "OA221": 0.94,
            "AOI22": 0.92, "OAI22": 0.92, "AO22": 0.90, "OA22": 0.90,
            "AOI21": 0.88, "OAI21": 0.88, "AO21": 0.86, "OA21": 0.86,
            "MUX2": 0.85, "AND4": 0.84, "OR4": 0.84, "NAND4": 0.84, "NOR4": 0.84,
            "XOR3": 0.80, "XNOR3": 0.80, "AND3": 0.78, "OR3": 0.78, "NAND3": 0.78, "NOR3": 0.78,
            "XOR2": 0.72, "XNOR2": 0.72, "AND2": 0.66, "OR2": 0.66, "NAND2": 0.66, "NOR2": 0.66,
            "INV": 0.15, "BUF": 0.12, "NBUFF": 0.12,
        }
        return priority.get(simple_type, 0.55)

    def _rank_expansion_rule(self, simple_type: str, expr_str: str) -> ExpansionRuleInfo:
        # ... 原样保留 GateExpander._rank_expansion_rule
        expr = parse_equiv_expr(expr_str)
        m = self._expr_metrics(expr)
        nodes = m["nodes"]
        depth = m["depth"]
        inv_buf_penalty = 0.18 * m["inv"] + 0.22 * m["buf"]
        redundancy_penalty = 0.45 * m["dup"]
        balanced_bonus = 0.25 if simple_type.endswith("4") and "AND2(AND2" in expr_str or "OR2(OR2" in expr_str else 0.0
        if simple_type.endswith("4") and ("AND2(AND2" in expr_str or "OR2(OR2" in expr_str or "NAND2(AND2" in expr_str or "NOR2(OR2" in expr_str):
            balanced_bonus = 0.35
        if simple_type.endswith("3") and ("AND2(AND2" in expr_str or "OR2(OR2" in expr_str or "NAND2(AND2" in expr_str or "NOR2(OR2" in expr_str):
            balanced_bonus = max(balanced_bonus, 0.28)
        merge_potential = min(1.0, 0.18 * nodes + 0.22 * m["wide"] + 0.18 * m["aoi"] + 0.12 * m["mux"] + balanced_bonus)
        normality_score = max(0.0, min(1.0, 0.70 + 0.08 * m["aoi"] + 0.06 * m["wide"] - 0.10 * m["buf"] - 0.08 * max(0, m["inv"] - 1) - 0.10 * m["dup"]))
        gate_score = max(0.0, min(1.0, 0.28 * nodes + 0.12 * m["wide"] + 0.10 * min(depth, 4)))
        depth_score = max(0.0, min(1.0, 1.0 - 0.18 * max(0, depth - 3)))
        total = 1.35 * merge_potential + 1.10 * normality_score + 0.55 * gate_score + 0.35 * depth_score - inv_buf_penalty - redundancy_penalty
        if simple_type in {"INV", "BUF", "NBUFF"}:
            total -= 0.6
        return ExpansionRuleInfo(expr=expr_str, gate_score=gate_score, normality_score=normality_score, merge_potential=merge_potential, inv_buf_penalty=inv_buf_penalty, redundancy_penalty=redundancy_penalty, depth_score=depth_score, total=total)

    def _reorder_gate_equivalences_for_expansion(self) -> None:
        # ... 原样保留 GateExpander._reorder_gate_equivalences_for_expansion
        reordered = {}
        gate_items = []
        for simple_type, rules in self.gate_equivalences.items():
            eq_list = list(rules.get("equivalent", []))
            ranked = sorted((self._rank_expansion_rule(simple_type, expr) for expr in eq_list), key=lambda x: x.total, reverse=True)
            new_rules = dict(rules)
            new_rules["equivalent"] = [r.expr for r in ranked]
            reordered[simple_type] = new_rules
            best = ranked[0].total if ranked else -1.0
            gate_items.append((self._simple_gate_expand_priority(simple_type), best, simple_type))
        gate_items.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
        self.gate_equivalences = {gt: reordered[gt] for _, _, gt in gate_items}

    def _emit_from_expr(self, expr, formal_bind, sink_net, prefer_cells, origin_tag, origin_inst_name):
        # ... 原样保留 GateExpander._emit_from_expr 的整个实现
        created: List[Instance] = []

        def eval_expr(e: Expr, target_net: str = None) -> str:
            if isinstance(e, str):
                if e in {"1'b0", "1'b1", "1'bz"}: return e
                if e in formal_bind: return formal_bind[e]
                raise ValueError(f"Variable '{e}' not found in formal_bind for instance {origin_inst_name}. "
                                f"Available: {list(formal_bind.keys())}")
                if target_net:
                    cell = pick_cell_for_simple("BUF", prefer_cells.get("BUF"), self.simple2cells)
                    inst_name = self._generate_instance_name(origin_inst_name, "BUF", len(created))
                    created.append(Instance(cell=cell, name=inst_name, conns={in_port: actual_sig, out_port: target_net}))
                    self.node_mappings.append({"src": origin_inst_name, "dst": inst_name})
                    return target_net
                return actual_sig

            assert isinstance(e, ExprCall)
            fn = e.fn
            arg_sigs = [eval_expr(a) for a in e.args]
            out_net = target_net if target_net else self._fresh_net(f"{origin_tag}_{fn}")
            cell = pick_cell_for_simple(fn, prefer_cells.get(fn), self.simple2cells)
            if cell is None:
                return arg_sigs[0] if arg_sigs else out_net

            inst_counter = len(created)
            inst_name = self._generate_instance_name(origin_inst_name, fn, inst_counter)
            conns: Dict[str, str] = {}
            ports = self.lib_ports.get(cell, [])
            out_port = None
            outs = self.lib_outs.get(cell, set())
            if outs:
                for p in OUTPUT_PORT_CANDIDATES:
                    if p in outs and p in ports:
                        out_port = p; break
                    if p in outs:
                        out_port = p; break
                if out_port is None:
                    if len(outs) == 1:
                        out_port = next(iter(outs))
                    else:
                        for p in ports:
                            if p in outs:
                                out_port = p; break
                        if out_port is None:
                            out_port = next(iter(outs))
            else:
                for p in OUTPUT_PORT_CANDIDATES:
                    if p in ports:
                        out_port = p; break
                if out_port is None and ports:
                    out_port = ports[-1]
            if out_port is None:
                return arg_sigs[0] if arg_sigs else out_net
            conns[out_port] = out_net
            in_ports = [p for p in ports if p != out_port]

            if fn == "MUX2" and len(arg_sigs) == 3:
                s_port = next((p for p in in_ports if any(kw in p.upper() for kw in ["S", "SEL", "SE"])), None)
                if s_port:
                    conns[s_port] = arg_sigs[2]
                    other_inps = [p for p in in_ports if p != s_port]
                    for p, s in zip(other_inps, arg_sigs[:2]):
                        conns[p] = s
                else:
                    for p, s in zip(in_ports, arg_sigs):
                        conns[p] = s
            else:
                for p, s in zip(in_ports, arg_sigs):
                    conns[p] = s

            created.append(Instance(cell=cell, name=inst_name, conns=conns))
            try:
                conns_s = ", ".join([f".{k}({v})" for k, v in conns.items()])
                self._log(f"[EXPAND]   + {cell} {inst_name} ({conns_s})")
            except Exception:
                pass
            self.node_mappings.append({"src": origin_inst_name, "dst": inst_name})
            return out_net

        final_net = eval_expr(expr, target_net=sink_net)
        return created

    def _select_rule_with_probability(self, rules, simple_type, first_rule_prob, average_mode=False, max_rule_use=None):
        # ... 原样保留 GateExpander._select_rule_with_probability
        if "equivalent" not in rules or not rules["equivalent"]:
            return None
        eq_list = list(rules["equivalent"])
        if len(eq_list) == 1:
            return (eq_list[0], 0)
        if average_mode:
            available_indices = []
            for idx, rule in enumerate(eq_list):
                rule_key = f"{simple_type}_{idx}"
                current_use = self.stats.rule_use_counts[simple_type][rule_key]
                if max_rule_use is not None and current_use >= max_rule_use:
                    continue
                available_indices.append((idx, current_use))
            if not available_indices:
                return (eq_list[-1], len(eq_list) - 1)
            min_use = min(use for _, use in available_indices)
            candidates = [idx for idx, use in available_indices if use == min_use]
            selected_index = self.rng.choice(candidates)
            selected_rule = eq_list[selected_index]
        else:
            rand_val = self.rng.random()
            if rand_val < first_rule_prob:
                selected_index = 0
            else:
                remaining_rules = len(eq_list) - 1
                remaining_index = int((rand_val - first_rule_prob) * remaining_rules / (1.0 - first_rule_prob))
                selected_index = remaining_index + 1
                if selected_index >= len(eq_list):
                    selected_index = len(eq_list) - 1
            selected_rule = eq_list[selected_index]

        if simple_type not in self.stats.rule_selection_counts:
            self.stats.rule_selection_counts[simple_type] = {}
        self.stats.rule_selection_counts[simple_type][selected_index] = \
            self.stats.rule_selection_counts[simple_type].get(selected_index, 0) + 1
        rule_key = f"{simple_type}_{selected_index}"
        self.stats.rule_use_counts[simple_type][rule_key] += 1
        return (selected_rule, selected_index)

    def _select_rule_from_location(self, inst_name, rules, simple_type):
        # ... 原样保留 GateExpander._select_rule_from_location
        if inst_name not in self.location_map:
            return None
        location_rule = self.location_map[inst_name]
        if location_rule is None:
            return None
        location_rule = location_rule.strip().strip('"')
        if "equivalent" not in rules or not rules["equivalent"]:
            return None
        eq_list = list(rules["equivalent"])
        for idx, rule in enumerate(eq_list):
            if rule == location_rule:
                if simple_type not in self.stats.rule_selection_counts:
                    self.stats.rule_selection_counts[simple_type] = {}
                self.stats.rule_selection_counts[simple_type][idx] = \
                    self.stats.rule_selection_counts[simple_type].get(idx, 0) + 1
                rule_key = f"{simple_type}_{idx}"
                self.stats.rule_use_counts[simple_type][rule_key] += 1
                self._log(f"[DEBUG] 使用location规则: {inst_name} -> {rule}")
                return (rule, idx)
        self._log(f"[WARNING] 未找到location规则: {location_rule} 在 {simple_type} 的规则列表中")
        return None

    def _apply_rule_by_index(self, mod, inst, st, ridx):
        # ... 原样保留 GateExpander._apply_rule_by_index
        rules = self.gate_equivalences.get(st)
        if not rules or ridx >= len(rules['equivalent']):
            return False
        eq_str = rules['equivalent'][ridx]
        expr = parse_equiv_expr(eq_str)
        formal_bind = bind_formals(st, inst, self.lib_ports, self.lib_outs)
        out_port = pick_output_port(inst, self.lib_ports, self.lib_outs)
        if not out_port:
            return False
        sink_net = inst.conns[out_port]
        root_origin = self.parent_map.get(inst.name, inst.name)
        created = self._emit_from_expr(expr, formal_bind, sink_net, {st: inst.cell},
                                       origin_tag=inst.name, origin_inst_name=root_origin)
        added_count = len(created) - 1
        self.stats.total_added_gates += added_count
        raw_idx = self.rule_expr_to_raw_index.get(st, {}).get(eq_str, -1)
        self.stats.csv_records.append({
            "变换门名称": inst.name,
            "变换门类型": st,
            "使用规则序号": ridx + 1,
            "使用规则序号_原始": (raw_idx + 1) if raw_idx >= 0 else "",
            "规则表达式": eq_str,
            "变换比例": f"1:{len(created)}",
            "规则家族": rule_bucket(st, eq_str),
        })
        try:
            pos = mod.instances.index(inst)
            mod.instances.pop(pos)
            mod.instances[pos:pos] = created
            for new_gate in created:
                self.parent_map[new_gate.name] = root_origin
            self.stats.rule_use_counts[st][ridx] += 1
            self.stats.total_rewrites += 1
            self.stats.rewritten_instances.add(inst.name)
            for g in created:
                for sig in g.conns.values():
                    if sig not in {"1'b0", "1'b1"}:
                        ensure_wire_decl(mod, sig)
            return True
        except ValueError:
            return False

    def apply(self, mod: ModuleNetlist, limits: "RewriteLimits"):
        out = copy.deepcopy(mod)
        self._init_used(out)
        orig_count = len(out.instances)
        self._log(f"[INFO] 原始门数: {orig_count}")

        rewrite_count = 0
        attempts = 0
        max_attempts = max(1000, limits.max_rewrites * 50)  # 安全上限，避免无效候选导致死循环
        while rewrite_count < limits.max_rewrites and attempts < max_attempts:
            attempts += 1
            candidates = [i for i in out.instances
                          if i.name not in self.stats.rewritten_instances]
            if not candidates:
                break
            target_inst = self.rng.choice(candidates)
            st = simplify_cell(target_inst.cell, self.gate_simplification)
            rules = self.gate_equivalences.get(st, {}).get('equivalent', [])
            if not rules:
                self.stats.rewritten_instances.add(target_inst.name)
                continue
            ridx = self.rng.randrange(len(rules))
            if self._apply_rule_by_index(out, target_inst, st, ridx):
                rewrite_count += 1

        final_count = len(out.instances)
        self._log(f"[INFO] 变换后门数: {final_count}")

        # 整合 mapping
        final_gate_names = {inst.name for inst in out.instances}
        final_alignment = {}
        for entry in self.node_mappings:
            orig = entry["src"]
            trans = entry["dst"]
            if trans in final_gate_names:
                final_alignment.setdefault(orig, [])
                if trans not in final_alignment[orig]:
                    final_alignment[orig].append(trans)

        return out, self.stats, final_alignment


def finalize_alignment(node_mappings: List[Dict[str, str]],
                       out_mod: ModuleNetlist,
                       successor_map: Optional[Dict[str, str]] = None) -> Dict[str, List[str]]:
    """
    把 node_mappings 收敛成 {src -> [dst...]}。

    - 丢掉指向“已不存在门”的 dst；
    - 若提供 successor_map（被删除的门 -> 其功能承接门），会沿着它一路解析到仍存活的门，
      这样 resub 的“消除冗余门 + 改网名”不会让上游溯源断链。
    """
    final_names = {inst.name for inst in out_mod.instances}
    successor_map = successor_map or {}

    def resolve(name: str) -> Optional[str]:
        hops = 0
        cur = name
        while cur is not None and cur not in final_names and hops < 64:
            cur = successor_map.get(cur)
            hops += 1
        return cur if (cur and cur in final_names) else None

    final_alignment: Dict[str, List[str]] = {}
    for entry in node_mappings:
        src = entry.get("src")
        dst = entry.get("dst")
        if not src or not dst:
            continue
        live = resolve(dst)
        if live is None:
            continue
        final_alignment.setdefault(src, [])
        if live not in final_alignment[src]:
            final_alignment[src].append(live)
    return final_alignment



class ExpressionRewriteOperator(DecompOperator):
    """
    规则空间受约束的表达式重写算子（balance / refactor / partitioned decomp）。

    与 legacy decomp 的差异：
      1. 只在“所属 bucket”的规则里选（rule_mode=partitioned），机制单一、可解释；
      2. 按家族偏好排序后在前 top-k 条里随机（decomp: 更多门/更深；balance: 更浅；refactor: 1:1 优先）；
      3. 选规则前先做形参可绑定校验，并对单个 edit 失败做隔离，避免整条流水线崩掉。
    legacy decomp（rule_mode=legacy）仍然走 DecompOperator.apply，行为与旧版完全一致。
    """
    family_name = "expression"
    bucket = "balance"

    def __init__(self, *args, rule_mode: str = "partitioned", rule_topk: int = 3, **kwargs):
        super().__init__(*args, **kwargs)
        if rule_mode not in ("partitioned", "uniform"):
            raise ValueError(f"未知 rule_mode: {rule_mode}")
        self.rule_mode = rule_mode
        self.rule_topk = max(1, int(rule_topk))
        self.allowed_rules: Dict[str, List[int]] = self._build_allowed_rules()

    # ---------- 规则空间 ----------
    def _rule_allowed(self, st: str, expr_str: str) -> bool:
        if self.rule_mode == "uniform":
            return True
        return rule_bucket(st, expr_str) == self.bucket

    def _build_allowed_rules(self) -> Dict[str, List[int]]:
        allowed: Dict[str, List[int]] = {}
        for st, rules in self.gate_equivalences.items():
            eq_list = list(rules.get("equivalent", []) or [])
            idxs = [i for i, e in enumerate(eq_list) if self._rule_allowed(st, e)]
            if idxs:
                allowed[st] = idxs
        return allowed

    def allowed_rule_count(self, st: str) -> int:
        return len(self.allowed_rules.get(st, []))

    # ---------- 规则选择 ----------
    def _choose_rule_index(self, st: str, rules: dict, inst: Instance) -> Optional[int]:
        eq_list = list(rules.get("equivalent", []) or [])
        cands = [i for i in self.allowed_rules.get(st, []) if 0 <= i < len(eq_list)]
        if not cands:
            return None
        # 形参可绑定校验：避免规则引用了本门类型不存在的形参（如缺 ISO / S）
        bind = bind_formals(st, inst, self.lib_ports, self.lib_outs)
        cands = [i for i in cands if rule_formals_bindable(eq_list[i], bind)]
        if not cands:
            return None
        keyed = sorted(cands, key=lambda i: (rule_pref_key(self.bucket, eq_list[i]), i))
        topk = keyed[: self.rule_topk]
        idx = int(self.rng.choice(topk))
        if st not in self.stats.rule_selection_counts:
            self.stats.rule_selection_counts[st] = {}
        self.stats.rule_selection_counts[st][idx] = \
            self.stats.rule_selection_counts[st].get(idx, 0) + 1
        return idx

    # ---------- 主循环 ----------
    def apply(self, mod: ModuleNetlist, limits: "RewriteLimits"):
        out = copy.deepcopy(mod)
        self._init_used(out)
        self._log(f"[INFO][{self.family_name}] 原始门数: {len(out.instances)}")

        rewrite_count = 0
        attempts = 0
        max_attempts = max(1000, limits.max_rewrites * 50)
        use_strength_prob = 0.0 < float(limits.strength) < 1.0

        while rewrite_count < limits.max_rewrites and attempts < max_attempts:
            attempts += 1
            candidates = [i for i in out.instances
                          if i.name not in self.stats.rewritten_instances]
            if not candidates:
                break
            target = self.rng.choice(candidates)
            st = simplify_cell(target.cell, self.gate_simplification)
            rules = self.gate_equivalences.get(st) or {}
            if not rules.get("equivalent") or not self.allowed_rules.get(st):
                self.stats.rewritten_instances.add(target.name)
                continue
            if use_strength_prob and self.rng.random() > float(limits.strength):
                self.stats.rewritten_instances.add(target.name)
                continue
            ridx = self._choose_rule_index(st, rules, target)
            if ridx is None:
                self.stats.rewritten_instances.add(target.name)
                continue
            ok = False
            try:
                ok = bool(self._apply_rule_by_index(out, target, st, ridx))
            except Exception as e:  # 单条规则失败不影响整体
                self._log(f"[WARN][{self.family_name}] 规则应用失败 {target.name}/{st}[{ridx}]: {e}")
            if ok:
                rewrite_count += 1
            else:
                self.stats.rewritten_instances.add(target.name)

        self._log(f"[INFO][{self.family_name}] 变换后门数: {len(out.instances)}")
        return out, self.stats, finalize_alignment(self.node_mappings, out)


class DecompFamilyOperator(ExpressionRewriteOperator):
    """分解算子（机制纯净版）：只用 decomp bucket 规则（De Morgan / 混合门族分解）。"""
    family_name = "decomp"
    bucket = "decomp"


class BalanceOperator(ExpressionRewriteOperator):
    """平衡算子：只用同族结合律规则，优先浅树（降低/控制逻辑深度）。"""
    family_name = "balance"
    bucket = "balance"


class RefactorOperator(ExpressionRewriteOperator):
    """重构算子：只用 1:1 / 1:2 局部结构重构规则（门数基本不变，改门型与局部结构）。"""
    family_name = "refactor"
    bucket = "refactor"


class ResubOperator(BaseOperator):
    """
    重替换（resubstitution）算子：**不使用规则表选规则**，而是利用网表自身已有逻辑重新实现目标门。

    四种机制（结构签名不同）：
      1) resub_reuse_buf    : 已存在同功能同输入的门 → 用 BUF 复用其输出网（1:1，门数不变）
      2) resub_reuse_shrink : 同上，但输出网不是模块端口 → 消除冗余门并把该网改名（门数 -1）
      3) resub_invert       : 已存在取反功能同输入的门 → 用 INV 接其输出（1:1，门型变 INV）
      4) resub_divisor      : 目标门存在 2 层等价分解，且其中“除数(divisor)”子函数已由现有门实现
                              → 直接用该已有网重接顶层门（1:1，复用已有子逻辑）

    与 decomp/balance/refactor 的机制差异：门数不变或减少、深度基本不变，
    每一步都依赖全局网表上下文（其它门是否已实现该功能），而不是表达式规则库。
    """
    family_name = "resub"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.simple2cells = build_simple_to_cells(self.lib_ports, self.gate_simplification)
        self.stats = RewriteStats(self.gate_equivalences)
        self.net_used: Set[str] = set()
        self.name_used: Set[str] = set()
        self.parent_map: Dict[str, str] = {}
        self.node_mappings: List[Dict[str, str]] = []
        #: 被消除的门 -> 功能承接门（resub 的 shrink 模式），用于溯源链不断裂
        self.successor: Dict[str, str] = {}

    # ---------- 基础工具 ----------
    def _log(self, message: str):
        if self.log_writer:
            self.log_writer.write(message + "\n")
        print(message)

    def _fresh_inst_name(self, base: str) -> str:
        i = 0
        while True:
            cand = f"{base}_rs{i}"
            if cand not in self.name_used:
                self.name_used.add(cand)
                return cand
            i += 1

    def _init_used(self, mod: ModuleNetlist):
        self.net_used |= collect_ports(mod)
        self.net_used |= collect_declared_wires(mod)
        for a in mod.assigns:
            self.net_used.add(a.lhs)
        for inst in mod.instances:
            self.name_used.add(inst.name)
            for sig in inst.conns.values():
                if sig not in {"1'b0", "1'b1", "1'bz"}:
                    self.net_used.add(sig)

    def _io_of(self, inst: Instance) -> Optional[Tuple[str, str, List[str]]]:
        """返回 (简化门类型, 输出网, 输入网列表)；时序门/多输出门/无输出门返回 None。"""
        if _is_sequential_cell(inst.cell, self.gate_simplification):
            return None
        st = simplify_cell(inst.cell, self.gate_simplification)
        if st in SEQUENTIAL_SIMPLE_TYPES:
            return None
        out_ports = instance_output_ports(inst, self.lib_outs)
        if len(out_ports) != 1:
            return None  # 多输出/无输出门不参与 resub（避免语义歧义）
        out_port = next(iter(out_ports))
        if out_port not in inst.conns:
            return None
        in_sigs = [v for k, v in inst.conns.items() if k != out_port]
        if not in_sigs:
            return None
        return st, inst.conns[out_port], in_sigs

    def _key(self, st: str, in_sigs: List[str]) -> tuple:
        """功能索引键：可交换二输入门对输入顺序不敏感。"""
        if st in COMMUTATIVE_2IN_FNS and len(in_sigs) == 2:
            return (st, tuple(sorted(in_sigs)))
        return (st, tuple(in_sigs))

    def _build_index(self, mod: ModuleNetlist) -> Tuple[Dict[tuple, List[str]], Dict[str, str]]:
        """构建 (门类型, 输入签名) -> [输出网] 索引，以及 输出网 -> 驱动门名 映射。"""
        index: Dict[tuple, List[str]] = defaultdict(list)
        driver: Dict[str, str] = {}
        for inst in mod.instances:
            io = self._io_of(inst)
            if io is None:
                continue
            st, out_net, in_sigs = io
            index[self._key(st, in_sigs)].append(out_net)
            driver.setdefault(out_net, inst.name)
        return index, driver

    def _fanin_of_net(self, mod: ModuleNetlist) -> Dict[str, List[str]]:
        fanin: Dict[str, List[str]] = {}
        for inst in mod.instances:
            io = self._io_of(inst)
            if io is None:
                continue
            _, out_net, in_sigs = io
            fanin[out_net] = in_sigs
        return fanin

    @staticmethod
    def _depends_on(fanin: Dict[str, List[str]], start_net: str, target_net: str,
                    max_nodes: int = 20000) -> bool:
        """start_net 的扇入锥是否包含 target_net（避免 resub 引入组合环）。"""
        if start_net == target_net:
            return True
        seen = {start_net}
        stack = [start_net]
        while stack:
            n = stack.pop()
            for p in fanin.get(n, []):
                if p == target_net:
                    return True
                if p not in seen:
                    if len(seen) > max_nodes:
                        return True  # 保守：锥太大，视为有依赖
                    seen.add(p)
                    stack.append(p)
        return False

    def _resolve_expr_with_divisors(self, expr: Expr, formal_bind: Dict[str, str],
                                    index: Dict[tuple, List[str]], sink_net: str
                                    ) -> Optional[Tuple[Expr, List[str]]]:
        """
        把表达式里的“可复用 divisor 子表达式”（叶子全是变量、门类型为可交换二输入门）
        替换成网表中已存在的等价网；至少替换掉一个才算成功。
        叶子统一翻译成实际网名（常量保留），根节点不参与替换（避免“自己指向自己”）。
        """
        consts = {"1'b0", "1'b1", "1'bz"}
        used: List[str] = []

        def resolve_leaf(name: str) -> Optional[str]:
            if name in consts:
                return name
            if name in formal_bind:
                return formal_bind[name]
            return None

        def walk(e: Expr, is_root: bool) -> Optional[Expr]:
            if isinstance(e, str):
                return resolve_leaf(e)
            if (not is_root) and e.fn in COMMUTATIVE_2IN_FNS and len(e.args) == 2:
                leaves: List[str] = []
                ok = True
                for a in e.args:
                    if not isinstance(a, str):
                        ok = False
                        break
                    r = resolve_leaf(a)
                    if r is None or r in consts:  # 常量不参与 divisor 复用，避免语义歧义
                        ok = False
                        break
                    leaves.append(r)
                if ok and len(leaves) == 2:
                    nets = [n for n in index.get(self._key(e.fn, leaves), []) if n != sink_net]
                    if nets:
                        used.append(nets[0])
                        return nets[0]
            new_args: List[Expr] = []
            for a in e.args:
                ra = walk(a, False)
                if ra is None:
                    return None
                new_args.append(ra)
            return ExprCall(fn=e.fn, args=new_args)

        new_expr = walk(expr, True)
        if new_expr is None or not used:
            return None
        return new_expr, used

    # ---------- 发射 / 替换 / 记录 ----------
    def _emit_single_gate(self, fn: str, arg_sigs: List[str], sink_net: str,
                          prefer_cells: Optional[Dict[str, str]],
                          origin_inst_name: str) -> Optional[Instance]:
        """发射单个门（输出接 sink_net），端口按库声明顺序绑定。"""
        prefer_cell = (prefer_cells or {}).get(fn)
        cell = pick_cell_for_simple(fn, prefer_cell, self.simple2cells)
        if cell is None:
            return None
        ports = self.lib_ports.get(cell, [])
        outs = self.lib_outs.get(cell, set())
        out_port = None
        if outs:
            for p in OUTPUT_PORT_CANDIDATES:
                if p in outs and p in ports:
                    out_port = p
                    break
                if p in outs:
                    out_port = p
                    break
            if out_port is None:
                if len(outs) == 1:
                    out_port = next(iter(outs))
                else:
                    for p in ports:
                        if p in outs:
                            out_port = p
                            break
                    if out_port is None:
                        out_port = next(iter(outs))
        else:
            for p in OUTPUT_PORT_CANDIDATES:
                if p in ports:
                    out_port = p
                    break
            if out_port is None and ports:
                out_port = ports[-1]
        if out_port is None:
            return None

        in_ports = [p for p in ports if p != out_port]
        conns: Dict[str, str] = {out_port: sink_net}
        if fn == "MUX2" and len(arg_sigs) == 3:
            s_port = next((p for p in in_ports if any(kw in p.upper() for kw in ["S", "SEL", "SE"])), None)
            if s_port:
                conns[s_port] = arg_sigs[2]
                others = [p for p in in_ports if p != s_port]
                for p, s in zip(others, arg_sigs[:2]):
                    conns[p] = s
            else:
                for p, s in zip(in_ports, arg_sigs):
                    conns[p] = s
        else:
            for p, s in zip(in_ports, arg_sigs):
                conns[p] = s
        if len(conns) < 1 + len(arg_sigs):  # 端口不足，放弃
            return None

        name = self._fresh_inst_name(origin_inst_name)
        inst = Instance(cell=cell, name=name, conns=conns)
        try:
            conns_s = ", ".join(f".{k}({v})" for k, v in conns.items())
            self._log(f"[RESUB]   + {cell} {name} ({conns_s})")
        except Exception:
            pass
        return inst

    def _replace_instance(self, mod: ModuleNetlist, target: Instance,
                          new_insts: List[Instance], root_origin: str,
                          shrink_dst: Optional[str] = None) -> None:
        """用 new_insts 替换 target（可为空 = 删除），并维护溯源与 wire 声明。"""
        pos = mod.instances.index(target)
        mod.instances.pop(pos)
        mod.instances[pos:pos] = new_insts

        dsts = [g.name for g in new_insts]
        if not dsts and shrink_dst:
            dsts = [shrink_dst]
        for g in new_insts:
            self.parent_map[g.name] = root_origin
        # 同时登记“祖先名”和“当前门名”，保证组合变换时溯源可以逐级串联
        for src_name in {target.name, root_origin}:
            for d in dsts:
                entry = {"src": src_name, "dst": d}
                if entry not in self.node_mappings:
                    self.node_mappings.append(entry)
        for g in new_insts:
            for sig in g.conns.values():
                if sig not in {"1'b0", "1'b1", "1'bz"}:
                    ensure_wire_decl(mod, sig)

    def _rename_net(self, mod: ModuleNetlist, old: str, new: str) -> None:
        """把所有对 old 的引用改成 new（resub 消除冗余门时用）。"""
        pat = re.compile(rf"(?<![\w$]){re.escape(old)}(?![\w$])")
        for inst in mod.instances:
            for k, v in list(inst.conns.items()):
                if v == old:
                    inst.conns[k] = new
                elif old in v:
                    inst.conns[k] = pat.sub(new, v)
        for a in mod.assigns:
            if a.lhs == old:
                a.lhs = new
            elif old in a.lhs:
                a.lhs = pat.sub(new, a.lhs)
            if a.rhs == old:
                a.rhs = new
            elif old in a.rhs:
                a.rhs = pat.sub(new, a.rhs)

    def _record(self, inst_name: str, st: str, ridx: int, ratio: str,
                bucket: str, added: int, expr: str = "") -> None:
        self.stats.csv_records.append({
            "变换门名称": inst_name,
            "变换门类型": st,
            "使用规则序号": (ridx + 1) if ridx >= 0 else "",
            "使用规则序号_原始": (ridx + 1) if ridx >= 0 else "",
            "规则表达式": expr,
            "变换比例": ratio,
            "规则家族": bucket,
        })
        self.stats.total_rewrites += 1
        self.stats.total_added_gates += added
        self.stats.rewritten_instances.add(inst_name)
        if ridx >= 0:
            self.stats.rule_use_counts[st][ridx] += 1

    # ---------- 候选 / 执行 ----------
    def _collect_options(self, target: Instance, index: Dict[tuple, List[str]],
                         ) -> Dict[str, List[object]]:
        """收集该门可用的 resub 机制（按 mode 分组）。"""
        io = self._io_of(target)
        if io is None:
            return {}
        st, out_net, in_sigs = io
        options: Dict[str, List[object]] = {}

        peers = [n for n in index.get(self._key(st, in_sigs), []) if n != out_net]
        if peers:
            options["reuse"] = peers

        comp = COMPLEMENT_TYPE_PAIRS.get(st)
        if comp is not None:
            cpeers = [n for n in index.get(self._key(comp, in_sigs), []) if n != out_net]
            if cpeers:
                options["invert"] = cpeers

        rules = self.gate_equivalences.get(st, {}) or {}
        eq_list = list(rules.get("equivalent", []) or [])
        if eq_list:
            bind = bind_formals(st, target, self.lib_ports, self.lib_outs)
            div_opts: List[object] = []
            for ridx, eq_str in enumerate(eq_list):
                if not rule_formals_bindable(eq_str, bind):
                    continue
                try:
                    expr = parse_equiv_expr(eq_str)
                except Exception:
                    continue
                if expr_node_count(expr) < 2:  # 没有嵌套子函数 → 不存在 divisor
                    continue
                res = self._resolve_expr_with_divisors(expr, bind, index, out_net)
                if res is None:
                    continue
                new_expr, used = res
                if not isinstance(new_expr, ExprCall):
                    continue
                if not all(isinstance(a, str) for a in new_expr.args):
                    continue
                div_opts.append((ridx, eq_str, new_expr, list(used)))
            if div_opts:
                options["divisor"] = div_opts
        return options

    def _apply_option(self, mod: ModuleNetlist, target: Instance, mode: str,
                      payload: object, fanin: Dict[str, List[str]],
                      driver: Dict[str, str]) -> bool:
        io = self._io_of(target)
        if io is None:
            return False
        st, out_net, _in_sigs = io
        root_origin = self.parent_map.get(target.name, target.name)

        if mode in ("reuse", "invert"):
            src_net = str(payload)
            # 复用已有网之前先确认不会形成组合环
            if self._depends_on(fanin, src_net, out_net):
                return False
            if mode == "reuse":
                if out_net in collect_ports(mod):
                    new_inst = self._emit_single_gate("BUF", [src_net], out_net, None, root_origin)
                    if new_inst is None:
                        return False
                    self._replace_instance(mod, target, [new_inst], root_origin)
                    self._record(target.name, st, -1, "1:1", "resub_reuse_buf", added=0)
                    return True
                # 输出网不是模块端口 → 直接消除冗余门并改网名（真正的“重替换”）
                dst_gate = driver.get(src_net)
                if dst_gate:
                    self.successor[target.name] = dst_gate
                self._replace_instance(mod, target, [], root_origin, shrink_dst=dst_gate)
                self._rename_net(mod, out_net, src_net)
                self._record(target.name, st, -1, "1:0", "resub_reuse_shrink", added=-1)
                return True
            new_inst = self._emit_single_gate("INV", [src_net], out_net, None, root_origin)
            if new_inst is None:
                return False
            self._replace_instance(mod, target, [new_inst], root_origin)
            self._record(target.name, st, -1, "1:1", "resub_invert", added=0)
            return True

        if mode == "divisor":
            ridx, eq_str, new_expr, used = payload  # type: ignore[misc]
            for w in used:
                if self._depends_on(fanin, str(w), out_net):
                    return False
            arg_sigs = [str(a) for a in new_expr.args]
            new_inst = self._emit_single_gate(new_expr.fn, arg_sigs, out_net,
                                              {st: target.cell}, root_origin)
            if new_inst is None:
                return False
            self._replace_instance(mod, target, [new_inst], root_origin)
            self._record(target.name, st, int(ridx), f"1:1(divisor x{len(used)})",
                         "resub_divisor", added=0, expr=str(eq_str))
            return True
        return False

    def apply(self, mod: ModuleNetlist, limits: "RewriteLimits"):
        out = copy.deepcopy(mod)
        self._init_used(out)
        self._log(f"[INFO][resub] 原始门数: {len(out.instances)}")

        rewrite_count = 0
        attempts = 0
        max_attempts = max(1000, limits.max_rewrites * 50)
        use_strength_prob = 0.0 < float(limits.strength) < 1.0
        tried: Dict[str, int] = defaultdict(int)
        index: Optional[Dict[tuple, List[str]]] = None
        driver: Dict[str, str] = {}
        fanin: Dict[str, List[str]] = {}

        while rewrite_count < limits.max_rewrites and attempts < max_attempts:
            attempts += 1
            if index is None:
                index, driver = self._build_index(out)
                fanin = self._fanin_of_net(out)

            candidates = [i for i in out.instances
                          if tried.get(i.name, 0) < 2 and self._io_of(i) is not None]
            if not candidates:
                break
            target = self.rng.choice(candidates)
            tried[target.name] += 1
            if use_strength_prob and self.rng.random() > float(limits.strength):
                continue

            options = self._collect_options(target, index)
            if not options:
                continue
            mode = str(self.rng.choice(sorted(options.keys())))
            payload = self.rng.choice(options[mode])
            ok = False
            try:
                ok = self._apply_option(out, target, mode, payload, fanin, driver)
            except Exception as e:
                self._log(f"[WARN][resub] {mode} 失败 {target.name}: {e}")
                ok = False
            if ok:
                rewrite_count += 1
                index = None  # 网表已改变，索引失效

        self._log(f"[INFO][resub] 变换后门数: {len(out.instances)}")
        return out, self.stats, finalize_alignment(self.node_mappings, out, self.successor)


class ComposeOperator(BaseOperator):
    """
    组合变换算子：按 chain 顺序依次施加多个 operator family（depth = len(chain)）。

    - 每一步使用独立的确定性 seed（base_seed + step*step_seed_stride），组合结果可复现；
    - 每一步有独立重写预算（step_budgets），便于在“匹配变换强度”的前提下做组合；
    - 溯源逐级串联（compose_alignment），最终给出 原始门名 -> 最终门名列表；
    - 逐步记录 edit_count / gate_expansion / depth_change（step_records）。
    """
    family_name = "compose"

    def __init__(self, *args, seed: int = 0, chain: Optional[List[str]] = None,
                 step_budgets: Optional[List[int]] = None, rule_mode: str = "partitioned",
                 step_seed_stride: int = 1009, operator_kwargs: Optional[Dict[str, dict]] = None,
                 **kwargs):
        super().__init__(*args, seed=seed, **kwargs)
        self.base_seed = int(seed)
        self.chain = [str(c) for c in (chain or []) if str(c)]
        if not self.chain:
            raise ValueError("ComposeOperator 需要非空 chain（--chain 或 --depth）")
        self.step_budgets = list(step_budgets or [])
        self.rule_mode = rule_mode
        self.step_seed_stride = int(step_seed_stride)
        self.operator_kwargs = operator_kwargs or {}
        self.step_records: List[Dict[str, object]] = []
        self.sub_stats: List[RewriteStats] = []

    def _step_budget(self, si: int, default_budget: int) -> int:
        if si < len(self.step_budgets) and self.step_budgets[si] is not None:
            return int(self.step_budgets[si])
        return int(default_budget)

    def apply(self, mod: ModuleNetlist, limits: "RewriteLimits"):
        cur = copy.deepcopy(mod)
        chain_map: Dict[str, List[str]] = {i.name: [i.name] for i in cur.instances}
        self.step_records = []
        self.sub_stats = []

        for si, fam in enumerate(self.chain):
            budget = self._step_budget(si, limits.max_rewrites)
            extra = dict(self.operator_kwargs.get(fam, {}))
            sub = build_operator(
                fam,
                lib_ports=self.lib_ports,
                lib_outs=self.lib_outs,
                lib_ins=self.lib_ins,
                gate_simplification=self.gate_simplification,
                gate_equivalences=self.gate_equivalences,
                seed=self.base_seed + si * self.step_seed_stride,
                location_map=self.location_map,
                log_writer=self.log_writer,
                netlist_id=self.netlist_id,
                rule_mode=self.rule_mode,
                **extra,
            )
            before = netlist_stats(cur, self.lib_ports, self.lib_outs, self.gate_simplification)
            out_mod, st_stats, step_align = sub.apply(
                cur, RewriteLimits(strength=limits.strength, max_rewrites=budget))
            out_mod.name = cur.name
            after = netlist_stats(out_mod, self.lib_ports, self.lib_outs, self.gate_simplification)

            # 给每个 edit 记录补上步序/算子，便于事后按算子归因
            for rec in getattr(st_stats, "csv_records", []) or []:
                rec.setdefault("步序", si + 1)
                rec.setdefault("算子", fam)
            self.step_records.append({
                "step": si + 1,
                "family": fam,
                "seed": self.base_seed + si * self.step_seed_stride,
                "budget": budget,
                "edit_count": len(getattr(st_stats, "csv_records", []) or []),
                "gate_expansion": after["gate_count"] - before["gate_count"],
                "gate_count_before": before["gate_count"],
                "gate_count_after": after["gate_count"],
                "depth_before": before["depth"],
                "depth_after": after["depth"],
                "depth_change": after["depth"] - before["depth"],
            })
            chain_map = compose_alignment(chain_map, step_align,
                                          {i.name for i in out_mod.instances})
            self.sub_stats.append(st_stats)
            cur = out_mod

        merged = merge_rewrite_stats(self.sub_stats, self.gate_equivalences)
        return cur, merged, chain_map


def build_operator(family_name: str, **kwargs) -> BaseOperator:
    """
    工厂函数：按 family_name 返回对应的 operator 实例。

    family_name:
      - decomp   : 表达式规则重写；rule_mode=legacy 时与旧版完全一致，partitioned 时只用 decomp bucket
      - balance  : 只用同族结合律规则（优先浅树）
      - refactor : 只用 1:1 / 1:2 局部结构重构规则
      - resub    : 基于网表上下文的 resubstitution（不使用规则表）
      - compose  : 组合多个 family（需要 chain / depth）
    """
    rule_mode = kwargs.pop("rule_mode", "legacy")
    if family_name == "decomp":
        if rule_mode in ("legacy", "uniform"):
            kwargs.pop("rule_topk", None)
            return DecompOperator(**kwargs)
        return DecompFamilyOperator(rule_mode="partitioned", **kwargs)
    if family_name == "balance":
        return BalanceOperator(rule_mode="partitioned", **kwargs)
    if family_name == "refactor":
        return RefactorOperator(rule_mode="partitioned", **kwargs)
    if family_name == "resub":
        kwargs.pop("rule_topk", None)
        return ResubOperator(**kwargs)
    if family_name == "compose":
        return ComposeOperator(rule_mode=rule_mode, **kwargs)
    raise NotImplementedError(f"Operator family '{family_name}' 暂未实现")









class GateExpander:
    def __init__(self, lib_ports: Dict[str, List[str]],
                 lib_outs: Dict[str, Set[str]],
                 lib_ins: Dict[str, List[str]],
                 gate_simplification: Dict[str, str],
                 gate_equivalences: Dict[str, dict],
                 seed: int,
                 location_map: Optional[Dict[str, str]] = None,  # 新增：位置映射
                 log_writer=None,
                 netlist_id: str = "default"):
        self.lib_ports = lib_ports
        self.lib_outs = lib_outs
        self.lib_ins = lib_ins
        self.gate_simplification = gate_simplification
        self.gate_equivalences = gate_equivalences
        self.rng = random.Random(seed)
        self.simple2cells = build_simple_to_cells(lib_ports, gate_simplification)
        self.location_map = location_map or {}  # 实例名 -> 分解规则
        self.log_writer = log_writer  # 新增：日志写入器
        self.stats = RewriteStats(gate_equivalences)
        self.netlist_id = netlist_id # 存储网表ID

        self._reorder_gate_equivalences_for_expansion()

        self.net_used: Set[str] = set()
        self.name_used: Set[str] = set()
        # 核心映射存储
        self.parent_map = {}  # 记录: 新门名字 -> 最初原始门名字 (溯源字典)
        self.node_mappings = []  # 记录: {"original": 原始名, "transformed": 变换名}
        

    def _log(self, message: str):
        """记录日志消息"""
        if self.log_writer:
            self.log_writer.write(message + "\n")
        print(message)

    def _fresh_net(self, base: str) -> str:
        i = 0
        while True:
            n = f"n_{base}_{i}"
            if n not in self.net_used:
                self.net_used.add(n)
                return n
            i += 1

    def _generate_instance_name(self, origin_inst_name: str, fn: str, counter: int) -> str:
        """根据原实例名生成新实例名（label-blind）"""
        base_name = f"{origin_inst_name}_{counter}"
        i = 0
        while True:
            candidate = base_name if i == 0 else f"{base_name}_{i}"
            if candidate not in self.name_used:
                self.name_used.add(candidate)
                return candidate
            i += 1

    def _init_used(self, mod: ModuleNetlist):
        ports = collect_ports(mod)
        self.net_used |= ports
        self.net_used |= collect_declared_wires(mod)
        for a in mod.assigns:
            self.net_used.add(a.lhs)
        for inst in mod.instances:
            self.name_used.add(inst.name)
            for sig in inst.conns.values():
                if sig not in {"1'b0", "1'b1"}:
                    self.net_used.add(sig)


    def _expr_metrics(self, expr: Expr) -> Dict[str, float]:
        def walk(e, depth=1):
            if isinstance(e, str):
                return {"nodes": 0, "depth": 0, "inv": 0, "buf": 0, "dup": 0, "wide": 0, "aoi": 0, "mux": 0, "vars": [e]}
            vars_seen = []
            nodes = 1
            max_depth = depth
            inv = 1 if e.fn == "INV" else 0
            buf = 1 if e.fn in {"BUF", "NBUFF"} else 0
            wide = 1 if e.fn.endswith("3") or e.fn.endswith("4") or e.fn.endswith("221") or e.fn.endswith("222") else 0
            aoi = 1 if any(tag in e.fn for tag in ["AO", "OA"]) else 0
            mux = 1 if e.fn.startswith("MUX") else 0
            dup = max(0, len(e.args) - len({str(a) for a in e.args}))
            for a in e.args:
                sub = walk(a, depth+1)
                nodes += sub["nodes"]
                max_depth = max(max_depth, sub["depth"])
                inv += sub["inv"]
                buf += sub["buf"]
                dup += sub["dup"]
                wide += sub["wide"]
                aoi += sub["aoi"]
                mux += sub["mux"]
                vars_seen.extend(sub["vars"])
            return {"nodes": nodes, "depth": max_depth, "inv": inv, "buf": buf, "dup": dup, "wide": wide, "aoi": aoi, "mux": mux, "vars": vars_seen}
        return walk(expr)

    def _simple_gate_expand_priority(self, simple_type: str) -> float:
        priority = {
            "AOI222": 1.00, "OAI222": 1.00, "AO222": 0.98, "OA222": 0.98,
            "AOI221": 0.96, "OAI221": 0.96, "AO221": 0.94, "OA221": 0.94,
            "AOI22": 0.92, "OAI22": 0.92, "AO22": 0.90, "OA22": 0.90,
            "AOI21": 0.88, "OAI21": 0.88, "AO21": 0.86, "OA21": 0.86,
            "MUX2": 0.85, "AND4": 0.84, "OR4": 0.84, "NAND4": 0.84, "NOR4": 0.84,
            "XOR3": 0.80, "XNOR3": 0.80, "AND3": 0.78, "OR3": 0.78, "NAND3": 0.78, "NOR3": 0.78,
            "XOR2": 0.72, "XNOR2": 0.72, "AND2": 0.66, "OR2": 0.66, "NAND2": 0.66, "NOR2": 0.66,
            "INV": 0.15, "BUF": 0.12, "NBUFF": 0.12,
        }
        return priority.get(simple_type, 0.55)

    def _rank_expansion_rule(self, simple_type: str, expr_str: str) -> ExpansionRuleInfo:
        expr = parse_equiv_expr(expr_str)
        m = self._expr_metrics(expr)
        nodes = m["nodes"]
        depth = m["depth"]
        inv_buf_penalty = 0.18 * m["inv"] + 0.22 * m["buf"]
        redundancy_penalty = 0.45 * m["dup"]
        balanced_bonus = 0.25 if simple_type.endswith("4") and "AND2(AND2" in expr_str or "OR2(OR2" in expr_str else 0.0
        if simple_type.endswith("4") and ("AND2(AND2" in expr_str or "OR2(OR2" in expr_str or "NAND2(AND2" in expr_str or "NOR2(OR2" in expr_str):
            balanced_bonus = 0.35
        if simple_type.endswith("3") and ("AND2(AND2" in expr_str or "OR2(OR2" in expr_str or "NAND2(AND2" in expr_str or "NOR2(OR2" in expr_str):
            balanced_bonus = max(balanced_bonus, 0.28)
        merge_potential = min(1.0, 0.18 * nodes + 0.22 * m["wide"] + 0.18 * m["aoi"] + 0.12 * m["mux"] + balanced_bonus)
        normality_score = max(0.0, min(1.0, 0.70 + 0.08 * m["aoi"] + 0.06 * m["wide"] - 0.10 * m["buf"] - 0.08 * max(0, m["inv"] - 1) - 0.10 * m["dup"]))
        gate_score = max(0.0, min(1.0, 0.28 * nodes + 0.12 * m["wide"] + 0.10 * min(depth, 4)))
        depth_score = max(0.0, min(1.0, 1.0 - 0.18 * max(0, depth - 3)))
        total = 1.35 * merge_potential + 1.10 * normality_score + 0.55 * gate_score + 0.35 * depth_score - inv_buf_penalty - redundancy_penalty
        if simple_type in {"INV", "BUF", "NBUFF"}:
            total -= 0.6
        return ExpansionRuleInfo(expr=expr_str, gate_score=gate_score, normality_score=normality_score, merge_potential=merge_potential, inv_buf_penalty=inv_buf_penalty, redundancy_penalty=redundancy_penalty, depth_score=depth_score, total=total)

    def _reorder_gate_equivalences_for_expansion(self) -> None:
        reordered = {}
        gate_items = []
        for simple_type, rules in self.gate_equivalences.items():
            eq_list = list(rules.get("equivalent", []))
            ranked = sorted((self._rank_expansion_rule(simple_type, expr) for expr in eq_list), key=lambda x: x.total, reverse=True)
            new_rules = dict(rules)
            new_rules["equivalent"] = [r.expr for r in ranked]
            reordered[simple_type] = new_rules
            best = ranked[0].total if ranked else -1.0
            gate_items.append((self._simple_gate_expand_priority(simple_type), best, simple_type))
        gate_items.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
        self.gate_equivalences = {gt: reordered[gt] for _, _, gt in gate_items}

    def _emit_from_expr(self, expr: Expr, formal_bind: Dict[str, str],
                        sink_net: str, prefer_cells: Dict[str, str],
                        origin_tag: str, origin_inst_name: str) -> List[Instance]:
        """
        Build a small sub-network that drives sink_net from expr.
        Returns new instances in evaluation order.
        """
        created: List[Instance] = []

        def eval_expr(e: Expr, target_net: str = None) -> str:
            if isinstance(e, str):
                if e in {"1'b0", "1'b1", "1'bz"}: return e
                if e in formal_bind: return formal_bind[e]
                # 修改点 1：找不到映射则抛出错误，防止生成无效信号名
                raise ValueError(f"Variable '{e}' not found in formal_bind for instance {origin_inst_name}. "
                                f"Available: {list(formal_bind.keys())}")

                if target_net:
                    cell = pick_cell_for_simple("BUF", prefer_cells.get("BUF"), self.simple2cells)
                    inst_name = self._generate_instance_name(origin_inst_name, "BUF", len(created))
                    # 确定端口...
                    created.append(Instance(cell=cell, name=inst_name, conns={in_port: actual_sig, out_port: target_net}))
                    # 记录映射
                    self.node_mappings.append({"src": origin_inst_name, "dst": inst_name})
                    return target_net
                return actual_sig

            assert isinstance(e, ExprCall)
            fn = e.fn
            arg_sigs = [eval_expr(a) for a in e.args]

            out_net = target_net if target_net else self._fresh_net(f"{origin_tag}_{fn}")
            cell = pick_cell_for_simple(fn, prefer_cells.get(fn), self.simple2cells)
            if cell is None:
                return arg_sigs[0] if arg_sigs else out_net

            # 使用自定义的实例名生成函数
            inst_counter = len(created)
            inst_name = self._generate_instance_name(origin_inst_name, fn, inst_counter)

            conns: Dict[str, str] = {}
            ports = self.lib_ports.get(cell, [])

            out_port = None
            # Prefer declared outputs from lib
            outs = self.lib_outs.get(cell, set())
            if outs:
                # prefer common output names
                for p in OUTPUT_PORT_CANDIDATES:
                    if p in outs and p in ports:
                        out_port = p
                        break
                    if p in outs:
                        out_port = p
                        break
                if out_port is None:
                    # single output
                    if len(outs) == 1:
                        out_port = next(iter(outs))
                    else:
                        # pick first output in header order
                        for p in ports:
                            if p in outs:
                                out_port = p
                                break
                        if out_port is None:
                            out_port = next(iter(outs))
            else:
                # fallback legacy behavior
                for p in OUTPUT_PORT_CANDIDATES:
                    if p in ports:
                        out_port = p
                        break
                if out_port is None and ports:
                    out_port = ports[-1]
            if out_port is None:
                return arg_sigs[0] if arg_sigs else out_net
            conns[out_port] = out_net

            in_ports = [p for p in ports if p != out_port]

            # 2. 针对 MUX2 的特殊对齐逻辑
            # 规则文件里的 MUX2(A, B, S) 最后一个参数通常是选择信号 S
            if fn == "MUX2" and len(arg_sigs) == 3:
                # 尝试在库端口中寻找包含 S, SEL, SE 关键字的端口作为选择端
                s_port = next((p for p in in_ports if any(kw in p.upper() for kw in ["S", "SEL", "SE"])), None)
                if s_port:
                    # 将 arg_sigs[2] (即规则里的 S) 连到找到的 s_port
                    conns[s_port] = arg_sigs[2]
                    # 将 arg_sigs[0], arg_sigs[1] (A, B) 连到剩下的输入端口
                    other_inps = [p for p in in_ports if p != s_port]
                    for p, s in zip(other_inps, arg_sigs[:2]):
                        conns[p] = s
                else:
                    # 找不到带 S 的端口，则按 0, 1, 2 顺序盲连
                    for p, s in zip(in_ports, arg_sigs):
                        conns[p] = s
            
            # 3. 通用逻辑：适用于 INV, AND, OR, AOI, OAI 等所有其他门
            # 直接将解析表达式得到的信号列表 arg_sigs 按顺序连接到输入端口 in_ports 上
            else:
                for p, s in zip(in_ports, arg_sigs):
                    conns[p] = s

            created.append(Instance(cell=cell, name=inst_name, conns=conns))
            # 详细日志：生成的子门
            try:
                conns_s = ", ".join([f".{k}({v})" for k, v in conns.items()])
                self._log(f"[EXPAND]   + {cell} {inst_name} ({conns_s})")
            except Exception:
                pass


            # 【关键修改】记录映射关系
            # origin_inst_name 是从 expand 方法传进来的当前被替换的门的名字
            self.node_mappings.append({
                "src": origin_inst_name, 
                "dst": inst_name
            })
            return out_net

        final_net = eval_expr(expr, target_net=sink_net)

        return created
    
    def _select_rule_with_probability(self, rules: dict, simple_type: str, 
                                     first_rule_prob: float, average_mode: bool = False,
                                     max_rule_use: Optional[int] = None) -> Optional[Tuple[str, int]]:
        """
        根据规则顺序选择等价表达式
        支持三种模式：
        1. 普通模式：第一条规则概率为first_rule_prob，其余规则平分剩余概率
        2. average模式：选择使用次数最少的规则（考虑最大使用次数限制）
        
        返回: (选择的规则字符串, 规则索引)
        """
        if "equivalent" not in rules or not rules["equivalent"]:
            return None
            
        eq_list: List[str] = list(rules["equivalent"])
        
        # 如果只有一条规则，直接返回
        if len(eq_list) == 1:
            return (eq_list[0], 0)
        
        if average_mode:
            # average模式：选择使用次数最少的规则
            available_indices = []
            
            for idx, rule in enumerate(eq_list):
                rule_key = f"{simple_type}_{idx}"
                current_use = self.stats.rule_use_counts[simple_type][rule_key]
                
                # 检查是否超过最大使用次数限制
                if max_rule_use is not None and current_use >= max_rule_use:
                    self._log(f"[DEBUG] 规则 {simple_type}[{idx}] 已达到最大使用次数: {current_use}/{max_rule_use}")
                    continue
                
                available_indices.append((idx, current_use))
            
            if not available_indices:
                self._log(f"[DEBUG] 所有规则都达到最大使用次数限制，将使用最后一条规则")
                # 所有规则都达到限制，使用最后一条规则
                return (eq_list[-1], len(eq_list) - 1)
            
            # 找到使用次数最少的规则
            min_use = min(use for _, use in available_indices)
            candidates = [idx for idx, use in available_indices if use == min_use]
            
            # 如果多个规则使用次数相同，随机选择一个
            selected_index = self.rng.choice(candidates)
            selected_rule = eq_list[selected_index]
            
        else:
            # 普通模式：使用概率选择
            rand_val = self.rng.random()
            
            # 选择规则
            if rand_val < first_rule_prob:
                # 选择第一条规则
                selected_index = 0
            else:
                # 从剩余规则中均匀选择
                remaining_rules = len(eq_list) - 1
                # 均匀分布在剩余规则上
                remaining_index = int((rand_val - first_rule_prob) * remaining_rules / (1.0 - first_rule_prob))
                selected_index = remaining_index + 1  # 跳过第一条规则
                
                # 确保索引在有效范围内
                if selected_index >= len(eq_list):
                    selected_index = len(eq_list) - 1
            
            selected_rule = eq_list[selected_index]
        
        # 记录规则选择统计
        if simple_type not in self.stats.rule_selection_counts:
            self.stats.rule_selection_counts[simple_type] = {}
        
        self.stats.rule_selection_counts[simple_type][selected_index] = \
            self.stats.rule_selection_counts[simple_type].get(selected_index, 0) + 1
        
        # 更新规则使用次数统计（用于average模式）
        rule_key = f"{simple_type}_{selected_index}"
        self.stats.rule_use_counts[simple_type][rule_key] += 1
        
        return (selected_rule, selected_index)
    
    def _select_rule_from_location(self, inst_name: str, rules: dict, simple_type: str) -> Optional[Tuple[str, int]]:
        """
        从location_map中获取特定实例的分解规则
        返回: (选择的规则字符串, 规则索引) 或 None
        """
        if inst_name not in self.location_map:
            return None
            
        location_rule = self.location_map[inst_name]
        # 清理规则字符串
        location_rule = location_rule.strip().strip('"')
        
        # 查找规则在列表中的位置
        if "equivalent" not in rules or not rules["equivalent"]:
            return None
            
        eq_list: List[str] = list(rules["equivalent"])
        
        for idx, rule in enumerate(eq_list):
            if rule == location_rule:
                # 记录规则选择统计
                if simple_type not in self.stats.rule_selection_counts:
                    self.stats.rule_selection_counts[simple_type] = {}
                
                self.stats.rule_selection_counts[simple_type][idx] = \
                    self.stats.rule_selection_counts[simple_type].get(idx, 0) + 1
                
                # 更新规则使用次数统计
                rule_key = f"{simple_type}_{idx}"
                self.stats.rule_use_counts[simple_type][rule_key] += 1
                
                self._log(f"[DEBUG] 使用location规则: {inst_name} -> {rule}")
                return (rule, idx)
        
        self._log(f"[WARNING] 未找到location规则: {location_rule} 在 {simple_type} 的规则列表中")
        return None
    

    def expand(self, mod, limits, name_suffix):
        out = copy.deepcopy(mod)
        out.name = f"{mod.name}_{name_suffix}"
        self._init_used(out)

        orig_count = len(out.instances)
        self._log(f"[INFO] 原始门数: {orig_count}")

        # Label-blind：所有门一视同仁，只受 limits.strength 和 limits.max_rewrites 控制
        rewrite_count = 0
        attempts = 0
        max_attempts = max(1000, limits.max_rewrites * 50)  # 安全上限，避免无效候选导致死循环
        while rewrite_count < limits.max_rewrites and attempts < max_attempts:
            attempts += 1
            candidates = [i for i in out.instances
                        if i.name not in self.stats.rewritten_instances]
            if not candidates:
                break

            target_inst = self.rng.choice(candidates)
            st = simplify_cell(target_inst.cell, self.gate_simplification)
            rules = self.gate_equivalences.get(st, {}).get('equivalent', [])
            if not rules:
                self.stats.rewritten_instances.add(target_inst.name)
                continue

            ridx = self.rng.randrange(len(rules))
            if self._apply_rule_by_index(out, target_inst, st, ridx):
                rewrite_count += 1

        final_count = len(out.instances)
        self._log(f"[INFO] 变换后门数: {final_count}")
        return out

    def _apply_rule_by_index(self, mod: ModuleNetlist, inst: Instance, st: str, ridx: int) -> bool:
            """执行具体的门替换操作，并记录血缘关系"""
            rules = self.gate_equivalences.get(st)
            if not rules or ridx >= len(rules['equivalent']):
                return False
            
            eq_str = rules['equivalent'][ridx]
            expr = parse_equiv_expr(eq_str)
        
            # 绑定端口
            formal_bind = bind_formals(st, inst, self.lib_ports, self.lib_outs)
            out_port = pick_output_port(inst, self.lib_ports, self.lib_outs)
            if not out_port: 
                return False
        
            sink_net = inst.conns[out_port]

            # 【核心修改：溯源】
            # 如果 inst.name 已经在 parent_map 里，说明它是之前变换生成的，我们需要找到它的“祖先”
            root_origin = self.parent_map.get(inst.name, inst.name)

            # 生成新门：传入 root_origin 作为 origin_inst_name
            created = self._emit_from_expr(expr, formal_bind, sink_net, {st: inst.cell}, 
                                       origin_tag=inst.name, 
                                       origin_inst_name=root_origin)

            # 新增：记录 CSV 数据
            added_count = len(created) - 1 # 1:2 增加 1 个，1:1 增加 0 个
            self.stats.total_added_gates += added_count
            self.stats.csv_records.append({
                "变换门名称": inst.name,
                "变换门类型": st,
                "使用规则序号": ridx + 1,
                "使用规则序号_原始": "",
                "规则表达式": eq_str,
                "变换比例": f"1:{len(created)}",
                "规则家族": rule_bucket(st, eq_str),
        })
        
            try:
                pos = mod.instances.index(inst)
                mod.instances.pop(pos)
                mod.instances[pos:pos] = created
            
                # 【核心修改：更新血缘字典】
                # 将新生成的所有门都指向那个最初的祖先名
                for new_gate in created:
                    self.parent_map[new_gate.name] = root_origin
            
                # 更新统计信息
                self.stats.rule_use_counts[st][ridx] += 1
                self.stats.total_rewrites += 1
                self.stats.rewritten_instances.add(inst.name)
            
                # 声明新线网
                for g in created:
                    for sig in g.conns.values():
                        if sig not in {"1'b0", "1'b1"}:
                            ensure_wire_decl(mod, sig)
                return True
            except ValueError:
                return False

# -----------------------------
# 解析add_location.txt文件
# -----------------------------

def parse_location_file(location_file: Path) -> Dict[str, str]:
    """
    解析add_location.txt文件
    格式:
        实例名
        分解规则
    例如:
        EquivU1_3_0_3_0
        "AND2(A, 1'b1)->BUF"
    """
    location_map = {}
    
    if not location_file.exists():
        print(f"[WARNING] location文件不存在: {location_file}")
        return location_map
    
    content = location_file.read_text(encoding="utf-8").strip()
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    
    i = 0
    while i < len(lines):
        inst_name = lines[i]
        # 检查下一行是否是以括号开头的规则字符串
        if i + 1 < len(lines) and ("(" in lines[i+1] or "->" in lines[i+1]):
            rule = lines[i + 1].strip().strip('"').strip("'")
            location_map[inst_name] = rule
            i += 2
        else:
            # 如果没有规则，存为 None，表示“强制分解但规则随机”
            location_map[inst_name] = None
            i += 1
    return location_map

# -----------------------------
# CLI
# -----------------------------

def main():
    ap = argparse.ArgumentParser(description="门级网表等价变换工具 v0.5.0 (label-blind decomp)")
    ap.add_argument("--lib", required=True, help="verilog_lib.v")
    ap.add_argument("--in", dest="infile", required=True,
                    help="原始网表文件名（默认从 orig/ 目录读取）")
    ap.add_argument("--out", required=True, help="输出 Verilog 文件名（写入 trans/）")
    ap.add_argument("--map", required=True, help="映射.txt (gate_simplification dict)")
    ap.add_argument("--rules", required=True, help="等价变换规则.txt (gate_equivalences dict)")
    ap.add_argument("--seed", type=int, default=1, help="随机种子")
    ap.add_argument("--suffix", default="equiv_equiv", help="模块名后缀")
    ap.add_argument("--log-file", type=Path, help="生成日志文件路径")
    ap.add_argument("--strength", type=float, default=1.0, help="每个符合条件门的重写概率 (0..1)")
    ap.add_argument("--max-rewrites", type=int, default=100000, help="最大重写门数")
    ap.add_argument("--location-file", type=Path, help="add_location.txt 文件路径")
    ap.add_argument("--netlist-id", type=str, help="唯一网表ID，默认取文件名")
    ap.add_argument("--mapping-out", type=str, help="映射关系输出文件名 (JSON，写入 mappings/)")
    ap.add_argument("--operator-family", type=str, default="decomp",
                    choices=["decomp", "balance", "refactor", "resub", "compose"],
                    help="算子家族，默认 decomp")
    ap.add_argument("--chain", type=str, default="",
                    help="组合变换算子链，逗号分隔（如 decomp,refactor）；优先于 --depth")
    ap.add_argument("--depth", type=int, default=1,
                    help="组合变换层数（1=单算子；>1 时按 --families 轮转取算子，depth=2/3 用于组合实验）")
    ap.add_argument("--families", type=str, default="decomp,balance,refactor,resub",
                    help="--depth>1 时用于构造 chain 的候选家族列表")
    ap.add_argument("--step-budgets", type=str, default="",
                    help="组合变换每步的重写预算，逗号分隔；缺省则全部用 --max-rewrites")
    ap.add_argument("--rule-mode", type=str, default="legacy", choices=["legacy", "partitioned"],
                    help="规则空间：legacy=旧版均匀采样（仅 decomp，行为与旧版一致）；partitioned=按机制纯度选规则")
    ap.add_argument("--rule-topk", type=int, default=3, help="partitioned 模式下每条门的候选规则池大小")
    ap.add_argument("--orig-dir", type=Path, default=Path("orig"),
                    help="原始网表所在目录，默认 orig/")
    ap.add_argument("--view-root", type=Path, default=Path("trans"),
                    help="视图网表输出根目录，默认 trans/")
    ap.add_argument("--mapping-root", type=Path, default=Path("mappings"),
                    help="mapping JSON 输出根目录，默认 mappings/")
    ap.add_argument("--metadata-csv", type=Path, default=None,
                    help="view 元数据 CSV 路径（默认 <view-root>/view_metadata.csv）")
    ap.add_argument("--metadata-out", type=Path, default=None,
                    help="单个 view 的完整元数据 JSON 输出路径（含逐条 edit 记录）")
    ap.add_argument("--freeze-tag", type=str, default="",
                    help="freeze 标签（写入元数据，便于数据/脚本版本冻结后追溯）")
    ap.add_argument("--no-view-metadata", action="store_true",
                    help="不追加 view_metadata.csv（matrix_builder 逐视图调用时使用）")
    args = ap.parse_args()

    # ---------- 输出目录 ----------
    trans_dir = Path(args.view_root)
    mappings_dir = Path(args.mapping_root)
    trans_dir.mkdir(parents=True, exist_ok=True)
    mappings_dir.mkdir(parents=True, exist_ok=True)

    out_path = trans_dir / os.path.basename(args.out)
    args.out = str(out_path)

    mapping_out_path = None
    if args.mapping_out:
        mapping_out_path = mappings_dir / os.path.basename(args.mapping_out)
        args.mapping_out = str(mapping_out_path)

    # ---------- 原始网表查找：优先 orig/ 目录 ----------
    infile_basename = os.path.basename(args.infile)
    infile_path = args.orig_dir / infile_basename
    if not infile_path.exists():
        fallback_path = Path(args.infile)
        if fallback_path.exists():
            print(f"[WARN] {infile_path} 不存在，回退到 {fallback_path}")
            infile_path = fallback_path
        else:
            print(f"[ERROR] 找不到原始网表: {args.infile}")
            print(f"        已尝试: {infile_path}")
            print(f"        已尝试: {fallback_path}")
            sys.exit(1)

    netlist_id = args.netlist_id if args.netlist_id else infile_basename

    # ---------- 加载库和映射 ----------
    lib_ports, lib_outs, lib_ins = parse_lib_info(
        Path(args.lib).read_text(encoding="utf-8", errors="ignore"))
    gate_simplification = load_py_dict_from_file(Path(args.map), "gate_simplification")
    gate_equivalences = load_py_dict_from_file(Path(args.rules), "gate_equivalences")

    # ---------- 解析原始网表 ----------
    timescale, mod = parse_gatelevel_verilog(
        infile_path.read_text(encoding="utf-8", errors="ignore"))

    print(f"[INFO] 输入模块: {mod.name}, 门数: {len(mod.instances)}")
    print(f"[INFO] 原始网表路径: {infile_path}")

    # ---------- 解析 location 文件 ----------
    location_map = {}
    if args.location_file:
        location_map = parse_location_file(args.location_file)

    # ---------- 构造 limits ----------
    limits = RewriteLimits(
        strength=max(0.0, min(1.0, args.strength)),
        max_rewrites=max(0, args.max_rewrites),
    )

    # ---------- 日志 ----------
    log_writer = None
    log_fp = None
    if args.log_file:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        log_fp = open(args.log_file, "w", encoding="utf-8")
        log_fp.write("门增加重写日志文件\n")
        log_fp.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_fp.write(f"输入文件: {infile_path.name}\n")
        log_fp.write(f"库文件: {args.lib}\n")
        log_fp.write(f"映射文件: {args.map}\n")
        log_fp.write(f"规则文件: {args.rules}\n")
        log_fp.write(f"随机种子: {args.seed}\n")
        log_fp.write("=" * 80 + "\n\n")

        class LogWriter:
            def __init__(self, file):
                self.file = file
            def write(self, text):
                self.file.write(text)
                self.file.flush()

        log_writer = LogWriter(log_fp)

    # ---------- 构建 operator ----------
    chain = [c.strip() for c in args.chain.split(",") if c.strip()]
    if not chain and args.depth and args.depth > 1:
        fams = [f.strip() for f in args.families.split(",") if f.strip()]
        if not fams:
            raise ValueError("--families 不能为空")
        chain = [fams[i % len(fams)] for i in range(int(args.depth))]
    step_budgets = [int(x) for x in args.step_budgets.split(",") if x.strip()] or None

    if chain:
        operator = build_operator(
            "compose",
            lib_ports=lib_ports,
            lib_outs=lib_outs,
            lib_ins=lib_ins,
            gate_simplification=gate_simplification,
            gate_equivalences=gate_equivalences,
            seed=args.seed,
            location_map=location_map,
            log_writer=log_writer,
            netlist_id=netlist_id,
            chain=chain,
            step_budgets=step_budgets,
            rule_mode=args.rule_mode,
        )
        family_label = "compose"
    else:
        operator = build_operator(
            args.operator_family,
            lib_ports=lib_ports,
            lib_outs=lib_outs,
            lib_ins=lib_ins,
            gate_simplification=gate_simplification,
            gate_equivalences=gate_equivalences,
            seed=args.seed,
            location_map=location_map,
            log_writer=log_writer,
            netlist_id=netlist_id,
            rule_mode=args.rule_mode,
            rule_topk=args.rule_topk,
        )
        family_label = args.operator_family
        chain = [args.operator_family]

    orig_stats = netlist_stats(mod, lib_ports, lib_outs, gate_simplification)
    out_mod, stats, final_alignment = operator.apply(mod, limits)
    out_stats = netlist_stats(out_mod, lib_ports, lib_outs, gate_simplification)
    out_mod.name = f"{mod.name}_{re.sub(r'[^0-9A-Za-z_]', '_', str(args.suffix))}"

    step_records = getattr(operator, "step_records", None)

    # ============================================================
    # 1) 保存 mapping JSON
    # ============================================================
    if mapping_out_path:
        import json
        output_data = {
            "netlist_id": netlist_id,
            "src_verilog": infile_path.name,     # 只取文件名
            "dst_verilog": out_path.name,        # 只取文件名
            "operator_family": (family_label if len(chain) == 1 else "compose"),
            "operator_chain": chain,
            "composition_depth": len(chain),
            "rule_mode": args.rule_mode,
            "seed": args.seed,
            "node_alignment": final_alignment,
        }
        with open(args.mapping_out, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4)
        print(f"[OK] 映射关系已保存至: {args.mapping_out}")

    # ============================================================
    # 2) 输出 Verilog
    # ============================================================
    print(f"[INFO] 最终门数: {len(out_mod.instances)}")
    verilog_out = emit_verilog(timescale, out_mod, lib_ports)
    out_path.write_text(verilog_out, encoding="utf-8")
    print(f"[OK] 写入输出文件: {args.out}")

    if log_fp:
        try:
            log_fp.write(f"输出文件: {out_path.name}\n")
            log_fp.write(f"最终门数: {len(out_mod.instances)}\n")
            log_fp.write(f"原始门数: {len(mod.instances)}\n")
            log_fp.write("=" * 80 + "\n")
            log_fp.close()
        except Exception:
            pass

    import csv
    import json

    # ============================================================
    # 3) view 元数据 CSV（追加模式；表头缺列时安全升级）
    # ============================================================
    view_meta_path = Path(args.metadata_csv) if args.metadata_csv else (out_path.parent / "view_metadata.csv")
    view_meta_row = build_view_metadata_row(
        view_name=out_mod.name,
        src_verilog=infile_path.name,     # 只取文件名
        dst_verilog=out_path.name,        # 只取文件名
        operator_family=(family_label if len(chain) == 1 else "compose"),
        operator_chain=chain,
        seed=args.seed,
        strength=args.strength,
        max_rewrites=args.max_rewrites,
        orig_stats=orig_stats,
        out_stats=out_stats,
        stats=stats,
        rule_mode=args.rule_mode,
        step_records=step_records,
        freeze_tag=args.freeze_tag,
        lib_sha1=file_sha1(args.lib),
        map_sha1=file_sha1(args.map),
        rules_sha1=file_sha1(args.rules),
    )
    if not args.no_view_metadata:
        append_view_metadata_csv(view_meta_path, view_meta_row)
        print(f"[OK] view metadata 已追加至: {view_meta_path}")

    # ============================================================
    # 3.5) 单 view 元数据 JSON（含逐条 edit 记录，供等价自检复算）
    # ============================================================
    if args.metadata_out:
        meta_out = Path(args.metadata_out)
        meta_out.parent.mkdir(parents=True, exist_ok=True)
        meta_payload = dict(view_meta_row)
        meta_payload["edits"] = list(getattr(stats, "csv_records", []) or [])
        meta_payload["node_alignment"] = final_alignment
        with open(meta_out, "w", encoding="utf-8") as f:
            json.dump(meta_payload, f, indent=2, ensure_ascii=False)
        print(f"[OK] 单 view 元数据已保存至: {meta_out}")

    # ============================================================
    # 4) 节点对齐明细 CSV
    # ============================================================
    node_csv_path = out_path.parent / "log" / f"{out_path.stem}_nodes.csv"
    node_csv_path.parent.mkdir(exist_ok=True)

    src_cell_map = {inst.name: inst.cell for inst in mod.instances}
    dst_cell_map = {inst.name: inst.cell for inst in out_mod.instances}

    node_rows = []
    for src, dst_list in final_alignment.items():
        for dst in dst_list:
            node_rows.append({
                "src_inst": src,
                "src_cell": src_cell_map.get(src, "MISSING"),
                "dst_inst": dst,
                "dst_cell": dst_cell_map.get(dst, "MISSING"),
                "mapping_ratio": len(dst_list),
            })

    unmapped_src = [
        {"src_inst": n, "src_cell": c, "dst_inst": "", "dst_cell": "", "mapping_ratio": 0}
        for n, c in src_cell_map.items() if n not in final_alignment
    ]

    with open(node_csv_path, 'w', encoding='utf-8-sig', newline='') as nf:
        writer = csv.DictWriter(
            nf,
            fieldnames=["src_inst", "src_cell", "dst_inst", "dst_cell", "mapping_ratio"],
        )
        writer.writeheader()
        writer.writerows(node_rows)
        writer.writerows(unmapped_src)

    print(f"[OK] 节点对齐明细已保存至: {node_csv_path}")
    print(f"       已映射 src 节点: {len(final_alignment)}，"
          f"明细行数: {len(node_rows)}，"
          f"未映射 src 节点: {len(unmapped_src)}")

if __name__ == "__main__":
    main()