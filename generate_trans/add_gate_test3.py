#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
equiv_rewrite_netlist.py v0.9.0

新增功能：
1. 批量生成不同max-iterations的文件
2. 自动生成日志文件
3. 从add_location.txt读取特定门分解规则
4. average模式限制每种规则的最大使用次数
"""
""" python add_gate_test3.py --lib verilog_lib.v --map map.txt --rule rule_expand1.txt --seed 42 --in rs232t1000.v --out rs232t1000tr2/42.v --trojan-op 2
"""

import argparse
import ast
import copy
import io
import random
import re
import tokenize
import sys
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Union, Any
import time
import math
import json
import csv
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

TOK_FN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

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


# -----------------------------
# 门增加重写器（改进版：迭代重写，随机选择门）
# -----------------------------

@dataclass
class RewriteLimits:
    strength: float
    max_rewrites: int
    max_growth: float
    per_type_limit: int
    max_iterations: int  # 新增：最大迭代次数（不再使用递归深度）
    max_inv_buf_expand: int  # 新增：INV/BUF最大分解次数
    modification_scope: Optional[Set[str]] = None  # 新增：限定修改的实例名集合
    first_rule_prob: float = 0.5  # 新增：第一条规则的概率
    average_mode: bool = False  # 新增：average模式
    max_rule_use: Optional[int] = None  # 新增：每种规则最大使用次数
    location_file: Optional[Path] = None  # 新增：add_location.txt文件路径
    local_size: int = 0  # 新增：局部变换门数量（0=全局）
    local_depth: int = 2  # 新增：局部连通搜索深度
    selection_mode: str = "weighted"  # random | topk | weighted
    region_focus: str = "balanced"  # balanced | rare | low_obs | low_ctrl | suspicious | normal
    score_temperature: float = 1.0
    score_topk: int = 0
    ctrl_obs_approx: str = "topo"
    weight_position: float = 1.0
    weight_scale: float = 1.0
    weight_rare: float = 1.0
    weight_observability: float = 1.0
    weight_controllability: float = 1.0
    weight_camouflage: float = 1.0
    weight_rule_diversity: float = 0.25
    risk_threshold: float = 0.0
    normality_target: float = 0.5
    suspiciousness_target: float = 0.5
    max_score_impact: float = 1.0
    max_ctrl_delta: float = 1.0
    max_obs_delta: float = 1.0
    max_naturalness_delta: float = 1.0
    expansion_mode: bool = False
    expansion_score_weight: float = 1.0
    reordered_rules_out: Optional[Path] = None
    weight_expand_quality: float = 0.45
    weight_stage2_decomp: float = 0.30
    weight_stage2_merge: float = 0.25
    global_score_csv: Optional[Path] = None
    global_score_json: Optional[Path] = None
    global_score_topn: int = 50
    diversity_weight: float = 0.35
    diversity_spatial_weight: float = 0.45
    diversity_type_weight: float = 0.35
    diversity_rule_weight: float = 0.20
    diversity_hops: int = 4
    diversity_min_factor: float = 0.35

@dataclass
class ScoreBreakdown:
    total: float
    position: float
    scale: float
    rare: float
    observability: float
    controllability: float
    camouflage: float
    rule_diversity: float
    naturalness: float
    suspiciousness: float
    controllability_raw: float
    observability_raw: float
    fanin: int
    fanout: int
    dist_pi: int
    dist_po: int
    expansion_score: float = 0.0
    stage2_decomp_score: float = 0.0
    stage2_merge_score: float = 0.0
    balanced_score: float = 0.0
    diversity_score: float = 1.0
    diversity_spatial: float = 1.0
    diversity_type: float = 1.0
    diversity_rule: float = 1.0


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

@dataclass
class RewriteEvent:
    iteration: int
    inst_name: str
    simple_type: str
    rule_idx: int
    rule_expr: str
    candidate_score_before: float
    candidate_score_after: float
    local_score_before: float
    local_score_after: float
    score_delta: float
    ctrl_before: float
    ctrl_after: float
    ctrl_delta: float
    obs_before: float
    obs_after: float
    obs_delta: float
    naturalness_before: float
    naturalness_after: float
    naturalness_delta: float
    suspicious_before: float
    suspicious_after: float
    suspicious_delta: float
    created_gate_count: int
    weighted_pick_prob: float

class RewriteStats:
    """记录重写统计信息"""
    def __init__(self, gate_equivalences: dict = None):
        self.total_rewrites = 0
        self.iteration_count = 0
        self.max_growth_reached = 0
        self.type_counts: Dict[str, int] = {}
        self.rewritten_instances: Set[str] = set()  # 记录已被重写的实例
        self.rule_selection_counts: Dict[str, Dict[int, int]] = {}  # 记录每条规则被选择的次数
        self.inv_buf_expand_count: int = 0  # INV/BUF分解次数计数器
        self.rule_use_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))  # average模式：每种规则使用次数
        self.rewrite_events: List[RewriteEvent] = []
        self.selection_score_history: List[Tuple[str, float]] = []
        self.selected_type_counts: Dict[str, int] = defaultdict(int)
        self.selected_name_history: List[str] = []
        self.csv_records = [] # 新增：用于存储每一条变换记录
        self.total_added_gates = 0 # 新增：汇总增加的门数
        self.summary_data = {
            "原木马门数": 0,
            "原普通门数": 0,
            "变换后木马门数": 0,
            "变换后普通门数": 0
        }

        if gate_equivalences:
            for gtype, data in gate_equivalences.items():
                self.rule_use_counts[gtype] = {i: 0 for i in range(len(data.get('equivalent', [])))}

    def load_from_file(self, path: Path):
        if path and path.exists():
            import json
            data = json.loads(path.read_text())
            for gtype, rules in data.items():
                if gtype in self.rule_use_counts:
                    for idx_str, count in rules.items():
                        self.rule_use_counts[gtype][int(idx_str)] = count

    def save_to_file(self, path: Path):
        if path:
            import json
            path.write_text(json.dumps(self.rule_use_counts, indent=4))

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
        """根据原实例名生成新实例名"""
        # 检查原实例名是否包含Trojan或Equiv
        if "Trojan" in origin_inst_name or "Equiv" in origin_inst_name:
            # 包含Trojan或Equiv的实例，使用原实例名加数字后缀
            base_name = f"{origin_inst_name}_{counter}"
        else:
            # 其他实例，添加Equiv前缀
            base_name = f"{origin_inst_name}_{counter}"
        
        # 确保名称唯一
        i = 0
        while True:
            if i == 0:
                candidate = base_name
            else:
                candidate = f"{base_name}_{i}"
            
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

    def _build_undirected_adj(self, mod: ModuleNetlist) -> Dict[str, Set[str]]:
        """Build an undirected adjacency among instances based on net connectivity.
        Edge: driver(output_net) <-> sink(instance consuming that net).
        """
        adj: Dict[str, Set[str]] = defaultdict(set)
    
        net_to_driver: Dict[str, str] = {}
        net_to_sinks: Dict[str, List[str]] = defaultdict(list)
    
        # pass 1: collect drivers and sinks
        for inst in mod.instances:
            out_port = pick_output_port(inst, self.lib_ports, self.lib_outs)
            out_net = inst.conns.get(out_port) if out_port else None
            if out_net and out_net not in {"1'b0", "1'b1"}:
                net_to_driver[out_net] = inst.name
    
            for sig in inst.conns.values():
                if sig in {"1'b0", "1'b1"}:
                    continue
                net_to_sinks[sig].append(inst.name)
    
        # pass 2: connect driver-sink
        for net, drv in net_to_driver.items():
            for sink in net_to_sinks.get(net, []):
                if sink == drv:
                    continue
                adj[drv].add(sink)
                adj[sink].add(drv)
    
        for inst in mod.instances:
            adj.setdefault(inst.name, set())
    
        return adj
    
    def _sample_connected_names(self, adj: Dict[str, Set[str]], start: str, k: int, max_depth: int) -> Set[str]:
        """Random BFS sample up to k connected instance names."""
        if k <= 0:
            return set(adj.keys())
        if start not in adj:
            return set()
    
        selected: Set[str] = set()
        q: List[Tuple[str, int]] = [(start, 0)]
        while q and len(selected) < k:
            cur, d = q.pop(0)
            if cur in selected:
                continue
            selected.add(cur)
            if d >= max_depth:
                continue
            nbrs = list(adj.get(cur, set()))
            self.rng.shuffle(nbrs)
            for nb in nbrs:
                if nb not in selected:
                    q.append((nb, d + 1))
    
        return selected

    def _build_analysis_cache(self, mod: ModuleNetlist) -> Dict[str, Any]:
        inst_map = {inst.name: inst for inst in mod.instances}
        ports = collect_ports(mod)
        adj = self._build_undirected_adj(mod)
        net_to_driver: Dict[str, str] = {}
        net_to_sinks: Dict[str, List[str]] = defaultdict(list)
        inputs_of_inst: Dict[str, List[str]] = defaultdict(list)
        outputs_of_inst: Dict[str, Optional[str]] = {}

        for inst in mod.instances:
            out_port = pick_output_port(inst, self.lib_ports, self.lib_outs)
            out_net = inst.conns.get(out_port) if out_port else None
            outputs_of_inst[inst.name] = out_net
            if out_net and out_net not in {"1'b0", "1'b1"}:
                net_to_driver[out_net] = inst.name

            for port, sig in inst.conns.items():
                if port == out_port or sig in {"1'b0", "1'b1"}:
                    continue
                net_to_sinks[sig].append(inst.name)
                inputs_of_inst[inst.name].append(sig)

        fanout_map: Dict[str, int] = {}
        fanin_map: Dict[str, int] = {}
        primary_input_driven: Set[str] = set()
        primary_output_drivers: Set[str] = set()

        for inst in mod.instances:
            ins = inputs_of_inst.get(inst.name, [])
            fanin_map[inst.name] = len(ins)
            out_net = outputs_of_inst.get(inst.name)
            fanout_map[inst.name] = len(net_to_sinks.get(out_net, [])) if out_net else 0
            if any(sig in ports for sig in ins):
                primary_input_driven.add(inst.name)
            if out_net and out_net in ports:
                primary_output_drivers.add(inst.name)

        def bfs(start_names: Set[str]) -> Dict[str, int]:
            dist = {name: 10**9 for name in inst_map}
            q: List[str] = []
            for name in start_names:
                if name in dist:
                    dist[name] = 0
                    q.append(name)
            head = 0
            while head < len(q):
                cur = q[head]
                head += 1
                for nb in adj.get(cur, set()):
                    if dist[nb] > dist[cur] + 1:
                        dist[nb] = dist[cur] + 1
                        q.append(nb)
            return dist

        dist_pi = bfs(primary_input_driven or set(inst_map.keys()))
        dist_po = bfs(primary_output_drivers or set(inst_map.keys()))

        return {
            "inst_map": inst_map,
            "adj": adj,
            "net_to_driver": net_to_driver,
            "net_to_sinks": net_to_sinks,
            "fanin_map": fanin_map,
            "fanout_map": fanout_map,
            "dist_pi": dist_pi,
            "dist_po": dist_po,
            "ports": ports,
        }

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

    def dump_reordered_rules(self, out_path: Path) -> None:
        lines = ["self.gate_equivalences = {"]
        for simple_type, rules in self.gate_equivalences.items():
            lines.append(f"    '{simple_type}': {{")
            lines.append("        'equivalent': [")
            ranked = [self._rank_expansion_rule(simple_type, expr) for expr in rules.get("equivalent", [])]
            for info in ranked:
                lines.append(f'            "{info.expr}",  # total={info.total:.3f} merge={info.merge_potential:.3f} normal={info.normality_score:.3f}')
            lines.append("        ]")
            lines.append("    },")
        lines.append("}")
        out_path.write_text("\n".join(lines), encoding="utf-8")

    def _compute_expansion_score(self, inst: Instance, analysis: Dict[str, Any], limits: RewriteLimits) -> float:
        st = simplify_cell(inst.cell, self.gate_simplification)
        base = self._score_instance(inst, analysis, limits)
        local_names = self._collect_local_region(inst.name, analysis, limits) if (limits.local_size and limits.local_size > 0) else {inst.name}
        same_type_density = 0.0
        merge_friendly_neighbors = 0
        for nm in local_names:
            other = analysis["inst_map"].get(nm)
            if other is None:
                continue
            ost = simplify_cell(other.cell, self.gate_simplification)
            if ost == st:
                same_type_density += 1.0
            if ost in {"AND2","OR2","NAND2","NOR2","AOI21","OAI21","AOI22","OAI22","AO21","OA21","AO22","OA22"}:
                merge_friendly_neighbors += 1
        denom = max(1.0, float(len(local_names)))
        same_type_density /= denom
        merge_friendly_neighbors /= denom
        decomposable = self._simple_gate_expand_priority(st)
        return (
            0.32 * decomposable +
            0.18 * base.scale +
            0.14 * same_type_density +
            0.16 * merge_friendly_neighbors +
            0.10 * base.naturalness +
            0.10 * (1.0 - min(1.0, abs(base.dist_pi - base.dist_po)/10.0))
        )

    def _compute_stage2_decomp_quality(self, inst: Instance, analysis: Dict[str, Any], limits: RewriteLimits) -> float:
        st = simplify_cell(inst.cell, self.gate_simplification)
        base = self._score_instance(inst, analysis, limits)
        local_names = self._collect_local_region(inst.name, analysis, limits) if (limits.local_size and limits.local_size > 0) else {inst.name}
        decomposable = self._simple_gate_expand_priority(st)
        rule_count = len(self.gate_equivalences.get(st, {}).get("equivalent", []) or [])
        rule_entropy_hint = min(1.0, rule_count / 6.0)
        rarity_value = base.rare
        structured_mid_depth = 1.0 - min(1.0, abs(base.dist_pi - base.dist_po) / 8.0)
        local_complexity = 0.0
        for nm in local_names:
            other = analysis["inst_map"].get(nm)
            if other is None:
                continue
            ost = simplify_cell(other.cell, self.gate_simplification)
            local_complexity += 1.0 if ost in {"AOI21","OAI21","AOI22","OAI22","MUX2","AND3","OR3","NAND3","NOR3","AND4","OR4","NAND4","NOR4"} else 0.35
        local_complexity /= max(1.0, float(len(local_names)))
        return max(0.0, min(1.0,
            0.32 * decomposable +
            0.22 * rule_entropy_hint +
            0.16 * rarity_value +
            0.15 * structured_mid_depth +
            0.15 * local_complexity
        ))

    def _compute_stage2_merge_quality(self, inst: Instance, analysis: Dict[str, Any], limits: RewriteLimits) -> float:
        st = simplify_cell(inst.cell, self.gate_simplification)
        base = self._score_instance(inst, analysis, limits)
        local_names = self._collect_local_region(inst.name, analysis, limits) if (limits.local_size and limits.local_size > 0) else {inst.name}
        merge_neighbors = 0.0
        same_polarity = 0.0
        tree_like = 0.0
        for nm in local_names:
            other = analysis["inst_map"].get(nm)
            if other is None:
                continue
            ost = simplify_cell(other.cell, self.gate_simplification)
            if ost in {"AND2","OR2","NAND2","NOR2","AOI21","OAI21","AOI22","OAI22","AO21","OA21","AO22","OA22"}:
                merge_neighbors += 1.0
            if (st.startswith("AND") and ost.startswith("AND")) or (st.startswith("OR") and ost.startswith("OR")) or (st.startswith("NAND") and ost.startswith("NAND")) or (st.startswith("NOR") and ost.startswith("NOR")):
                same_polarity += 1.0
            fanin_other = analysis["fanin_map"].get(nm, 0)
            fanout_other = analysis["fanout_map"].get(nm, 0)
            if fanin_other <= 3 and fanout_other <= 3:
                tree_like += 1.0
        denom = max(1.0, float(len(local_names)))
        merge_neighbors /= denom
        same_polarity /= denom
        tree_like /= denom
        return max(0.0, min(1.0,
            0.30 * merge_neighbors +
            0.22 * same_polarity +
            0.18 * tree_like +
            0.18 * base.naturalness +
            0.12 * base.scale
        ))

    def _compute_balanced_expansion_score(self, inst: Instance, analysis: Dict[str, Any], limits: RewriteLimits) -> Tuple[float, float, float, float]:
        expansion_score = self._compute_expansion_score(inst, analysis, limits)
        decomp_score = self._compute_stage2_decomp_quality(inst, analysis, limits)
        merge_score = self._compute_stage2_merge_quality(inst, analysis, limits)
        balanced = (
            limits.weight_expand_quality * expansion_score +
            limits.weight_stage2_decomp * decomp_score +
            limits.weight_stage2_merge * merge_score
        )
        return balanced, expansion_score, decomp_score, merge_score

    def _collect_global_score_rows(self, mod: ModuleNetlist, analysis: Dict[str, Any], limits: RewriteLimits, stage: str) -> List[Dict[str, Any]]:
        rows = []
        for inst in mod.instances:
            st = simplify_cell(inst.cell, self.gate_simplification)
            if is_sequential_simple(st):
                continue
            sb = self._score_instance(inst, analysis, limits)
            balanced, expansion_score, decomp_score, merge_score = self._compute_balanced_expansion_score(inst, analysis, limits)
            rows.append({
                "stage": stage,
                "inst_name": inst.name,
                "cell": inst.cell,
                "simple_type": st,
                "balanced_score": balanced,
                "expansion_score": expansion_score,
                "stage2_decomp_score": decomp_score,
                "stage2_merge_score": merge_score,
                "risk_score": sb.total,
                "position": sb.position,
                "scale": sb.scale,
                "rare": sb.rare,
                "low_obs": sb.observability,
                "low_ctrl": sb.controllability,
                "naturalness": sb.naturalness,
                "suspiciousness": sb.suspiciousness,
                "fanin": sb.fanin,
                "fanout": sb.fanout,
                "dist_pi": sb.dist_pi,
                "dist_po": sb.dist_po,
            })
        rows.sort(key=lambda x: (x["balanced_score"], x["stage2_decomp_score"], x["stage2_merge_score"]), reverse=True)
        return rows

    def _summarize_global_rows(self, rows: List[Dict[str, Any]], topn: int) -> Dict[str, Any]:
        if not rows:
            return {"count": 0, "top": [], "means": {}}
        n = float(len(rows))
        means = {}
        for key in ["balanced_score", "expansion_score", "stage2_decomp_score", "stage2_merge_score", "risk_score", "naturalness", "suspiciousness"]:
            means[key] = sum(float(r[key]) for r in rows) / n
        top = rows[:max(1, topn)]
        type_counts = {}
        for r in top:
            type_counts[r["simple_type"]] = type_counts.get(r["simple_type"], 0) + 1
        return {"count": len(rows), "means": means, "top": top, "top_type_counts": type_counts}

    def _write_global_score_views(self, limits: RewriteLimits, before_rows: List[Dict[str, Any]], after_rows: List[Dict[str, Any]]) -> None:
        if limits.global_score_csv:
            limits.global_score_csv.parent.mkdir(parents=True, exist_ok=True)
            with open(limits.global_score_csv, "w", encoding="utf-8", newline="") as fp:
                writer = csv.DictWriter(fp, fieldnames=list(before_rows[0].keys() if before_rows else after_rows[0].keys()))
                writer.writeheader()
                for row in before_rows + after_rows:
                    writer.writerow(row)
            self._log(f"[INFO] 已导出全局评分CSV: {limits.global_score_csv}")
        if limits.global_score_json:
            limits.global_score_json.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "before": self._summarize_global_rows(before_rows, limits.global_score_topn),
                "after": self._summarize_global_rows(after_rows, limits.global_score_topn),
            }
            limits.global_score_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self._log(f"[INFO] 已导出全局评分JSON: {limits.global_score_json}")

    def _calc_camouflage_scores(self, simple_type: str, fanin: int, fanout: int, dist_pi: int, dist_po: int, limits: RewriteLimits) -> Tuple[float, float]:
        common_types = {"AND2", "NAND2", "OR2", "NOR2", "INV", "BUF", "XOR2", "XNOR2", "AND3", "OR3", "NAND3", "NOR3"}
        structural_common = 1.0 if simple_type in common_types else 0.55
        balanced_connectivity = 1.0 - min(1.0, abs(fanin - fanout) / 6.0)
        locality = 1.0 - min(1.0, abs(dist_pi - dist_po) / 10.0)
        naturalness = max(0.0, min(1.0, 0.5 * structural_common + 0.3 * balanced_connectivity + 0.2 * locality))
        suspiciousness = 1.0 - naturalness
        if limits.region_focus == "normal":
            suspiciousness *= 0.7
        elif limits.region_focus == "suspicious":
            suspiciousness = min(1.0, suspiciousness * 1.2)
        return naturalness, suspiciousness

    def _score_instance(self, inst: Instance, analysis: Dict[str, Any], limits: RewriteLimits) -> ScoreBreakdown:
        st = simplify_cell(inst.cell, self.gate_simplification)
        fanin = analysis["fanin_map"].get(inst.name, 0)
        fanout = analysis["fanout_map"].get(inst.name, 0)
        dist_pi = analysis["dist_pi"].get(inst.name, 10**9)
        dist_po = analysis["dist_po"].get(inst.name, 10**9)
        dist_pi_n = min(1.0, dist_pi / 10.0)
        dist_po_n = min(1.0, dist_po / 10.0)
        fanin_n = min(1.0, fanin / 6.0)
        fanout_n = min(1.0, fanout / 6.0)

        position = 0.5 * dist_pi_n + 0.5 * dist_po_n
        scale = 0.6 * fanin_n + 0.4 * fanout_n
        rare = max(0.0, min(1.0, 0.65 * (1.0 - fanout_n) + 0.35 * dist_po_n))
        controllability_raw = max(0.0, min(1.0, 1.0 - (0.55 * dist_pi_n + 0.45 * fanin_n)))
        observability_raw = max(0.0, min(1.0, 1.0 - (0.60 * dist_po_n + 0.40 * fanout_n)))
        low_ctrl = 1.0 - controllability_raw
        low_obs = 1.0 - observability_raw
        naturalness, suspiciousness = self._calc_camouflage_scores(st, fanin, fanout, dist_pi, dist_po, limits)
        camouflage = suspiciousness if limits.region_focus in {"suspicious", "balanced", "rare", "low_obs", "low_ctrl"} else naturalness
        rule_diversity = 1.0 / (1.0 + sum(self.stats.rule_use_counts.get(st, {}).values()))

        focus_boost = 1.0
        if limits.region_focus == "rare":
            focus_boost += 0.35 * rare
        elif limits.region_focus == "low_obs":
            focus_boost += 0.35 * low_obs
        elif limits.region_focus == "low_ctrl":
            focus_boost += 0.35 * low_ctrl
        elif limits.region_focus == "normal":
            focus_boost += 0.35 * naturalness
        elif limits.region_focus == "suspicious":
            focus_boost += 0.35 * suspiciousness

        total = (
            limits.weight_position * position +
            limits.weight_scale * scale +
            limits.weight_rare * rare +
            limits.weight_observability * low_obs +
            limits.weight_controllability * low_ctrl +
            limits.weight_camouflage * camouflage +
            limits.weight_rule_diversity * rule_diversity
        ) * focus_boost

        return ScoreBreakdown(
            total=total,
            position=position,
            scale=scale,
            rare=rare,
            observability=low_obs,
            controllability=low_ctrl,
            camouflage=camouflage,
            rule_diversity=rule_diversity,
            naturalness=naturalness,
            suspiciousness=suspiciousness,
            controllability_raw=controllability_raw,
            observability_raw=observability_raw,
            fanin=fanin,
            fanout=fanout,
            dist_pi=dist_pi if dist_pi < 10**9 else 999,
            dist_po=dist_po if dist_po < 10**9 else 999,
        )

    def _score_subgraph(self, names: Set[str], analysis: Dict[str, Any], limits: RewriteLimits) -> Dict[str, float]:
        if not names:
            return {
                "score": 0.0,
                "ctrl": 0.0,
                "obs": 0.0,
                "naturalness": 0.0,
                "suspicious": 0.0,
            }
        vals = []
        for name in names:
            inst = analysis["inst_map"].get(name)
            if inst is None:
                continue
            vals.append(self._score_instance(inst, analysis, limits))
        if not vals:
            return {"score": 0.0, "ctrl": 0.0, "obs": 0.0, "naturalness": 0.0, "suspicious": 0.0}
        n = float(len(vals))
        return {
            "score": sum(v.total for v in vals) / n,
            "ctrl": sum(v.controllability_raw for v in vals) / n,
            "obs": sum(v.observability_raw for v in vals) / n,
            "naturalness": sum(v.naturalness for v in vals) / n,
            "suspicious": sum(v.suspiciousness for v in vals) / n,
        }

    def _collect_local_region(self, anchor_name: str, analysis: Dict[str, Any], limits: RewriteLimits) -> Set[str]:
        local_size = max(1, limits.local_size or 1)
        local_depth = max(1, limits.local_depth)
        return self._sample_connected_names(analysis["adj"], anchor_name, local_size, local_depth)

    def _bounded_distance_to_rewritten(self, inst_name: str, analysis: Dict[str, Any], max_hops: int) -> Optional[int]:
        if not self.stats.rewritten_instances:
            return None
        if inst_name in self.stats.rewritten_instances:
            return 0
        adj = analysis["adj"]
        q: List[Tuple[str, int]] = [(inst_name, 0)]
        visited = {inst_name}
        rewritten = self.stats.rewritten_instances
        while q:
            cur, d = q.pop(0)
            if d >= max_hops:
                continue
            for nb in adj.get(cur, set()):
                if nb in visited:
                    continue
                nd = d + 1
                if nb in rewritten:
                    return nd
                visited.add(nb)
                q.append((nb, nd))
        return None

    def _compute_diversity_bonus(self, inst: Instance, analysis: Dict[str, Any], limits: RewriteLimits) -> Tuple[float, float, float, float]:
        st = simplify_cell(inst.cell, self.gate_simplification)

        # 空历史时保持完全开放，避免一开始被多样性约束干扰
        if not self.stats.rewritten_instances and not self.stats.selected_type_counts:
            return 1.0, 1.0, 1.0, 1.0

        max_hops = max(1, limits.diversity_hops)
        min_dist = self._bounded_distance_to_rewritten(inst.name, analysis, max_hops)
        if min_dist is None:
            spatial = 1.0
        else:
            spatial = max(0.0, min(1.0, min_dist / float(max_hops)))

        type_count = self.stats.selected_type_counts.get(st, 0)
        type_bonus = 1.0 / (1.0 + float(type_count))

        total_rule_use = sum(self.stats.rule_use_counts.get(st, {}).values())
        rule_bonus = 1.0 / (1.0 + float(total_rule_use))

        w_spatial = max(0.0, limits.diversity_spatial_weight)
        w_type = max(0.0, limits.diversity_type_weight)
        w_rule = max(0.0, limits.diversity_rule_weight)
        w_sum = w_spatial + w_type + w_rule
        if w_sum <= 1e-9:
            diversity = 1.0
        else:
            diversity = (w_spatial * spatial + w_type * type_bonus + w_rule * rule_bonus) / w_sum
        diversity = max(0.0, min(1.0, diversity))
        return diversity, spatial, type_bonus, rule_bonus

    def _weighted_choice(self, weighted_candidates: List[Tuple[Instance, ScoreBreakdown]], temperature: float = 1.0) -> Tuple[Instance, ScoreBreakdown, float]:
        weights = []
        for _, score in weighted_candidates:
            w = max(1e-6, score.total) ** (1.0 / max(1e-6, temperature))
            weights.append(w)
        total = sum(weights)
        if total <= 0:
            idx = self.rng.randrange(len(weighted_candidates))
            return weighted_candidates[idx][0], weighted_candidates[idx][1], 1.0 / len(weighted_candidates)
        r = self.rng.random() * total
        acc = 0.0
        for (inst, score), w in zip(weighted_candidates, weights):
            acc += w
            if acc >= r:
                return inst, score, w / total
        inst, score = weighted_candidates[-1]
        return inst, score, weights[-1] / total

    def _select_candidate_by_score(self, candidates: List[Instance], analysis: Dict[str, Any], limits: RewriteLimits) -> Tuple[Instance, ScoreBreakdown, float]:
        scored = []
        for inst in candidates:
            sb = self._score_instance(inst, analysis, limits)
            balanced_score, expansion_score, decomp_score, merge_score = self._compute_balanced_expansion_score(inst, analysis, limits)
            if limits.expansion_mode:
                quality_score = (1.0 - limits.expansion_score_weight) * sb.total + limits.expansion_score_weight * balanced_score
            else:
                quality_score = sb.total
            diversity_score, diversity_spatial, diversity_type, diversity_rule = self._compute_diversity_bonus(inst, analysis, limits)
            diversity_factor = (1.0 - limits.diversity_weight) + limits.diversity_weight * diversity_score
            diversity_factor = max(limits.diversity_min_factor, diversity_factor)
            total_score = quality_score * diversity_factor
            sb = ScoreBreakdown(
                total=total_score,
                position=sb.position, scale=sb.scale, rare=sb.rare, observability=sb.observability,
                controllability=sb.controllability, camouflage=sb.camouflage, rule_diversity=sb.rule_diversity,
                naturalness=sb.naturalness, suspiciousness=sb.suspiciousness,
                controllability_raw=sb.controllability_raw, observability_raw=sb.observability_raw,
                fanin=sb.fanin, fanout=sb.fanout, dist_pi=sb.dist_pi, dist_po=sb.dist_po,
                expansion_score=expansion_score, stage2_decomp_score=decomp_score,
                stage2_merge_score=merge_score, balanced_score=balanced_score,
                diversity_score=diversity_score, diversity_spatial=diversity_spatial,
                diversity_type=diversity_type, diversity_rule=diversity_rule,
            )
            scored.append((inst, sb))
        scored = [item for item in scored if item[1].total >= limits.risk_threshold]
        if not scored:
            rescored = []
            for inst in candidates:
                sb = self._score_instance(inst, analysis, limits)
                diversity_score, diversity_spatial, diversity_type, diversity_rule = self._compute_diversity_bonus(inst, analysis, limits)
                diversity_factor = (1.0 - limits.diversity_weight) + limits.diversity_weight * diversity_score
                diversity_factor = max(limits.diversity_min_factor, diversity_factor)
                rescored.append((inst, ScoreBreakdown(
                    total=sb.total * diversity_factor,
                    position=sb.position, scale=sb.scale, rare=sb.rare, observability=sb.observability,
                    controllability=sb.controllability, camouflage=sb.camouflage, rule_diversity=sb.rule_diversity,
                    naturalness=sb.naturalness, suspiciousness=sb.suspiciousness,
                    controllability_raw=sb.controllability_raw, observability_raw=sb.observability_raw,
                    fanin=sb.fanin, fanout=sb.fanout, dist_pi=sb.dist_pi, dist_po=sb.dist_po,
                    diversity_score=diversity_score, diversity_spatial=diversity_spatial,
                    diversity_type=diversity_type, diversity_rule=diversity_rule,
                )))
            scored = rescored
        scored.sort(key=lambda x: x[1].total, reverse=True)
        if limits.score_topk and limits.score_topk > 0:
            scored = scored[:max(1, limits.score_topk)]
        if limits.selection_mode == "topk":
            return scored[0][0], scored[0][1], 1.0
        if limits.selection_mode == "random":
            inst, score = self.rng.choice(scored)
            return inst, score, 1.0 / len(scored)
        return self._weighted_choice(scored, limits.score_temperature)

    def _format_score_breakdown(self, sc: ScoreBreakdown) -> str:
        return (
            f"total={sc.total:.3f} bal={sc.balanced_score:.3f} exp={sc.expansion_score:.3f} "
            f"decomp={sc.stage2_decomp_score:.3f} merge={sc.stage2_merge_score:.3f} "
            f"div={sc.diversity_score:.3f} spatial={sc.diversity_spatial:.3f} typeDiv={sc.diversity_type:.3f} ruleDiv={sc.diversity_rule:.3f} "
            f"pos={sc.position:.3f} scale={sc.scale:.3f} rare={sc.rare:.3f} "
            f"low_obs={sc.observability:.3f} low_ctrl={sc.controllability:.3f} camo={sc.camouflage:.3f} "
            f"nat={sc.naturalness:.3f} susp={sc.suspiciousness:.3f} fanin={sc.fanin} fanout={sc.fanout} "
            f"distPI={sc.dist_pi} distPO={sc.dist_po}"
        )

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
    
    def _try_rewrite_instance(self, inst: Instance, limits: RewriteLimits,
                              per_type_cnt: Dict[str, int],
                              score_before: Optional[ScoreBreakdown] = None) -> Tuple[List[Instance], bool, Dict[str, Any]]:
        """
        尝试对单个实例进行重写（无递归）
        返回: (新实例列表, 是否成功, 重写元数据)
        """
        cell = inst.cell
        st = simplify_cell(cell, self.gate_simplification)
        meta: Dict[str, Any] = {"rule_idx": -1, "rule_expr": "", "simple_type": st, "score_before": score_before}

        # 检查概率
        if self.rng.random() > limits.strength and inst.name not in self.location_map:
            return [inst], False, meta

        rules = self.gate_equivalences.get(st)
        if not rules or "equivalent" not in rules or not rules["equivalent"]:
            return [inst], False, meta

        if per_type_cnt.get(st, 0) >= limits.per_type_limit:
            return [inst], False, meta

        if st in {"INV", "BUF", "NBUFF"} and self.stats.inv_buf_expand_count >= limits.max_inv_buf_expand:
            self._log(f"[DEBUG] 跳过 {inst.name}({st})，INV/BUF分解次数已达上限: {self.stats.inv_buf_expand_count}/{limits.max_inv_buf_expand}")
            return [inst], False, meta

        formal_bind = bind_formals(st, inst, self.lib_ports, self.lib_outs)
        out_port = pick_output_port(inst, self.lib_ports, self.lib_outs)
        if out_port is None:
            return [inst], False, meta

        sink_net = inst.conns[out_port]
        eq_result = None
        # 逻辑 1：如果在强制位置名单 (location_map) 中
        if self.location_map and inst.name in self.location_map:
            specified_rule = self.location_map[inst.name]
            if specified_rule is not None:
                # 匹配文件中指定的具体公式
                eq_result = self._select_rule_from_location(inst.name, rules, st)
            
            # 如果没指定具体公式，或者上面匹配失败了，则在该位置随机选一个公式
            if eq_result is None:
                eq_result = self._select_rule_with_probability(
                    rules, st, limits.first_rule_prob,
                    limits.average_mode, limits.max_rule_use
                )
        
        # 逻辑 2：如果不在强制名单中（即普通随机修改，或在 scope-file 名单中）
        else:
            eq_result = self._select_rule_with_probability(
                rules, st, limits.first_rule_prob,
                limits.average_mode, limits.max_rule_use
            )

        # 逻辑 3：安全检查。如果最终还是没选出规则（例如该门类在 rules 文件里没定义规则）
        if eq_result is None:
            return [inst], False, meta

        eq_str, rule_idx = eq_result
        expr = parse_equiv_expr(eq_str)
        meta["rule_idx"] = rule_idx
        meta["rule_expr"] = eq_str
        meta["formal_bind"] = formal_bind
        meta["sink_net"] = sink_net
        meta["out_port"] = out_port

        self._log(f"[REWRITE] {inst.name} : cell={inst.cell} simple={st} out_port={out_port} sink={sink_net}")
        self._log(f"[REWRITE]   rule_idx={rule_idx+1} expr={eq_str}")
        if score_before is not None:
            self._log(f"[REWRITE]   score_before: {self._format_score_breakdown(score_before)}")
        if formal_bind:
            fb = ", ".join([f"{k}={v}" for k, v in sorted(formal_bind.items())])
            self._log(f"[REWRITE]   bind: {fb}")
        else:
            self._log("[REWRITE]   bind: <empty>")

        prefer_cells = {st: cell}
        origin_tag = inst.name
        created = self._emit_from_expr(expr, formal_bind, sink_net, prefer_cells, origin_tag, inst.name)

        self.stats.total_rewrites += 1
        self.stats.type_counts[st] = self.stats.type_counts.get(st, 0) + 1
        self.stats.rewritten_instances.add(inst.name)

        if st in {"INV", "BUF", "NBUFF"}:
            self.stats.inv_buf_expand_count += 1
            self._log(f"[DEBUG] INV/BUF分解次数: {self.stats.inv_buf_expand_count}/{limits.max_inv_buf_expand}")

        return created, True, meta

    def expand(self, mod: ModuleNetlist, limits: RewriteLimits, name_suffix: str, trojan_op: int = 0) -> ModuleNetlist:
        out = copy.deepcopy(mod)
        out.name = f"{mod.name}_{name_suffix}"
        self._init_used(out)
        
        # 1. 统计原始分布
        orig_all = out.instances
        # 使用 count 逻辑
        n_orig_trojan = sum(1 for i in orig_all if "Trojan" in i.name)
        n_orig_benign = len(orig_all) - n_orig_trojan
        self.stats.summary_data["原木马门数"] = n_orig_trojan
        self.stats.summary_data["原普通门数"] = n_orig_benign
        
        self._log(f"[INFO] 原始统计 - 普通门: {n_orig_benign}, 木马门: {n_orig_trojan}")

        # 2. 第一阶段：对木马门进行定向变换
        trojan_rewrite_count = 0
        added_by_trojan = 0
        print(f"{trojan_op}\n")
        while trojan_rewrite_count < trojan_op:
            # 过滤出未被重写的木马门
            candidates = [i for i in out.instances if "Trojan" in i.name and i.name not in self.stats.rewritten_instances]
            print("fail\n")
            if not candidates: break
            
            target_inst = self.rng.choice(candidates)
            st = simplify_cell(target_inst.cell, self.gate_simplification)
            # 随机选一个该类型的规则
            rules = self.gate_equivalences.get(st, {}).get('equivalent', [])
            if not rules: 
                self.stats.rewritten_instances.add(target_inst.name)
                continue
                
            ridx = self.rng.randrange(len(rules))
            pre_len = len(out.instances)
            if self._apply_rule_by_index(out, target_inst, st, ridx):
                added_by_trojan += (len(out.instances) - pre_len)
                trojan_rewrite_count += 1

        # 3. 计算理想增长比例
        # 增长比例 = 木马增加门数 / 原始木马总数
        growth_ratio = added_by_trojan / n_orig_trojan if n_orig_trojan > 0 else 0
        target_benign_growth = math.ceil(growth_ratio * n_orig_benign)
        self._log(f"[INFO] 木马变换完成，增加 {added_by_trojan} 门。普通门目标增长数: {target_benign_growth}")

        # 4. 第二阶段：普通门按比例增长
        current_benign_growth = 0
        while current_benign_growth < target_benign_growth:
            # 过滤出未被重写的普通门
            candidates = [i for i in out.instances if "Trojan" not in i.name and i.name not in self.stats.rewritten_instances]
            if not candidates: break
            
            target_inst = self.rng.choice(candidates)
            st = simplify_cell(target_inst.cell, self.gate_simplification)
            rules = self.gate_equivalences.get(st, {}).get('equivalent', [])
            if not rules: 
                self.stats.rewritten_instances.add(target_inst.name)
                continue
            
            ridx = self.rng.randrange(len(rules))
            pre_len = len(out.instances)
            if self._apply_rule_by_index(out, target_inst, st, ridx):
                current_benign_growth += (len(out.instances) - pre_len)
                if self.stats.total_rewrites >= limits.max_rewrites: break

        final_all = out.instances
        n_final_trojan = sum(1 for i in final_all if "Trojan" in i.name)
        n_final_benign = len(final_all) - n_final_trojan
        self.stats.summary_data["变换后木马门数"] = n_final_trojan
        self.stats.summary_data["变换后普通门数"] = n_final_benign

        self._log_minimal_stats(len(orig_all), len(final_all))
        return out

    def save_mappings(self, filepath, netlist_id):
        import json
        data = {
            "netlist_id": netlist_id,
            "mappings": self.node_mappings
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

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
                "变换比例": f"1:{len(created)}"
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
        
    def _log_minimal_stats(self, orig_count, final_count):
        """只记录要求的两项数据"""
        self._log("\n" + "="*50)
        # 1. 记录门数变化
        self._log(f"1. 原门数: {orig_count}, 变换后门数: {final_count}")
        
        # 2. 记录所有规则的使用次数列表
        self._log("2. 变换使用的规则次数列表 (包含0次):")
        # 按门类型字母顺序排列
        for gtype in sorted(self.stats.rule_use_counts.keys()):
            # 提取该类型下的所有规则次数并转为列表
            counts_dict = self.stats.rule_use_counts[gtype]
            counts_list = [counts_dict[i] for i in range(len(counts_dict))]
            self._log(f"   {gtype}: {counts_list}")
        self._log("="*50 + "\n")

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


def parse_scope_file(scope_file: Path) -> Set[str]:
    """
    解析 Verilog 实例代码片段并提取实例名。
    支持格式：OAI21X1_RS U3 ( ... );
    """
    if not scope_file.exists():
        print(f"[WARNING] 范围文件不存在: {scope_file}")
        return set()
    
    content = scope_file.read_text(encoding="utf-8")
    # 正则逻辑：匹配单词(门类) + 空格 + 单词(实例名) + 左括号
    # 例如：OAI21X1_RS U3 (
    matches = re.findall(r'\b\w+\b\s+([a-zA-Z0-9_]+)\s*\(', content)
    
    scope_set = set(matches)
    print(f"[INFO] 从范围文件中识别到 {len(scope_set)} 个候选门实例: {list(scope_set)[:5]}...")
    return scope_set

# -----------------------------
# 批量生成功能
# -----------------------------

def run_batch_generation(args):
    """批量生成不同max-iterations的文件"""
    # 加载库和映射
    lib_ports, lib_outs, lib_ins = parse_lib_info(Path(args.lib).read_text(encoding="utf-8", errors="ignore"))
    gate_simplification = load_py_dict_from_file(Path(args.map), "gate_simplification")
    gate_equivalences   = load_py_dict_from_file(Path(args.rules), "gate_equivalences")

    # 解析输入网表
    timescale, mod = parse_gatelevel_verilog(Path(args.infile).read_text(encoding="utf-8", errors="ignore"))
    
    # 创建输出文件夹
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建日志文件夹
    log_dir = Path(args.log_dir) if args.log_dir else output_dir / "log_file"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 解析location文件（如果有）
    location_map = {}
    if args.location_file:
        location_map = parse_location_file(args.location_file)
    
    # 批量生成
    print(f"[INFO] 开始批量生成，迭代次数范围: {args.iter_start} 到 {args.iter_end}，步长: {args.iter_step}")
    print(f"[INFO] 输出文件夹: {output_dir}")
    print(f"[INFO] 日志文件夹: {log_dir}")
    
    # 获取输入文件名（不含路径和扩展名）
    input_path = Path(args.infile)
    input_stem = input_path.stem
    
    # 批量生成循环
    for iteration in range(args.iter_start, args.iter_end + 1, args.iter_step):
        # 计算当前种子（从42开始递增）
        seed = 42 + (iteration - args.iter_start) // args.iter_step
        
        # 创建日志文件
        log_filename = f"{input_stem}_iter{iteration}.log"
        log_filepath = log_dir / log_filename
        
        with open(log_filepath, 'w', encoding='utf-8') as log_file:
            # 写入日志头部
            log_file.write(f"门增加重写日志文件\n")
            log_file.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.write(f"输入文件: {args.infile}\n")
            log_file.write(f"库文件: {args.lib}\n")
            log_file.write(f"映射文件: {args.map}\n")
            log_file.write(f"规则文件: {args.rules}\n")
            log_file.write(f"迭代次数: {iteration}\n")
            log_file.write(f"随机种子: {seed}\n")
            log_file.write(f"强度: {args.strength}\n")
            log_file.write(f"最大重写次数: {args.max_rewrites}\n")
            log_file.write(f"最大增长: {args.max_growth}\n")
            log_file.write(f"每条规则最大使用次数: {args.max_rule_use if args.max_rule_use else '无限制'}\n")
            log_file.write(f"第一条规则概率: {args.first_rule_prob}\n")
            log_file.write(f"INV/BUF最大分解次数: {args.max_inv_buf_expand}\n")
            if args.average_mode:
                log_file.write(f"模式: average\n")
            else:
                log_file.write(f"模式: 普通\n")
            log_file.write(f"=" * 80 + "\n\n")
            
            # 创建日志写入器
            class LogWriter:
                def __init__(self, file):
                    self.file = file
                
                def write(self, text):
                    self.file.write(text)
                    self.file.flush()
            
            log_writer = LogWriter(log_file)
            
            print(f"\n[INFO] 正在生成迭代次数为 {iteration} 的电路 (种子: {seed})...")
            
            # 执行门增加重写
            limits = RewriteLimits(
                strength=max(0.0, min(1.0, args.strength)),
                max_rewrites=max(0, args.max_rewrites),
                max_growth=max(0.0, args.max_growth),
                per_type_limit=max(0, args.per_type_limit),
                max_iterations=iteration,
                max_inv_buf_expand=max(0, args.max_inv_buf_expand),
                first_rule_prob=max(0.0, min(1.0, args.first_rule_prob)),
                average_mode=args.average_mode,
                max_rule_use=args.max_rule_use,
                location_file=args.location_file,
                local_size=args.local_size,
                local_depth=args.local_depth,
                selection_mode=args.selection_mode,
                region_focus=args.region_focus,
                score_temperature=max(1e-6, args.score_temperature),
                score_topk=max(0, args.score_topk),
                risk_threshold=args.risk_threshold,
                weight_position=args.weight_position,
                weight_scale=args.weight_scale,
                weight_rare=args.weight_rare,
                weight_observability=args.weight_observability,
                weight_controllability=args.weight_controllability,
                weight_camouflage=args.weight_camouflage,
                weight_rule_diversity=args.weight_rule_diversity,
                max_score_impact=max(0.0, args.max_score_impact),
                max_ctrl_delta=max(0.0, args.max_ctrl_delta),
                max_obs_delta=max(0.0, args.max_obs_delta),
                max_naturalness_delta=max(0.0, args.max_naturalness_delta),
                expansion_mode=args.expansion_mode,
                expansion_score_weight=max(0.0, min(1.0, args.expansion_score_weight)),
                reordered_rules_out=args.dump_reordered_rules,
                weight_expand_quality=args.weight_expand_quality,
                weight_stage2_decomp=args.weight_stage2_decomp,
                weight_stage2_merge=args.weight_stage2_merge,
                global_score_csv=args.global_score_csv,
                global_score_json=args.global_score_json,
                global_score_topn=max(1, args.global_score_topn),
                diversity_weight=max(0.0, min(1.0, args.diversity_weight)),
                diversity_spatial_weight=max(0.0, args.diversity_spatial_weight),
                diversity_type_weight=max(0.0, args.diversity_type_weight),
                diversity_rule_weight=max(0.0, args.diversity_rule_weight),
                diversity_hops=max(1, args.diversity_hops),
                diversity_min_factor=max(0.0, min(1.0, args.diversity_min_factor)),
            )
            
            # 使用原模块的副本进行重写
            mod_copy = copy.deepcopy(mod)
            
            expander = GateExpander(
        lib_ports=lib_ports,
        lib_outs=lib_outs,
        lib_ins=lib_ins,
        gate_simplification=gate_simplification,
        gate_equivalences=gate_equivalences,
        seed=seed,
        location_map=location_map,
        log_writer=log_writer,
    )
            out_mod = expander.expand(mod, limits, name_suffix=args.suffix, trojan_op=args.trojanop)
            
            # 生成输出文件名
            output_filename = f"{input_stem}_a{iteration}.v"
            output_filepath = output_dir / output_filename
            
            # 生成输出文件
            verilog_out = emit_verilog(timescale, out_mod, lib_ports)
            output_filepath.write_text(verilog_out, encoding="utf-8")
            
            # 记录日志尾部
            log_file.write(f"\n" + "=" * 80 + "\n")
            log_file.write(f"生成完成\n")
            log_file.write(f"输出文件: {output_filepath}\n")
            log_file.write(f"最终门数: {len(out_mod.instances)}\n")
            log_file.write(f"原始门数: {len(mod.instances)}\n")
            log_file.write(f"门数增长: {(len(out_mod.instances) - len(mod.instances)) / len(mod.instances) * 100:.2f}%\n")
            
            print(f"[OK] 生成完成: {output_filename}")
            print(f"[OK] 日志文件: {log_filename}")
    
    print(f"\n[INFO] 批量生成完成！共生成 {len(range(args.iter_start, args.iter_end + 1, args.iter_step))} 个文件")


# -----------------------------
# CLI
# -----------------------------

def main():
    ap = argparse.ArgumentParser(description="门级网表等价变换工具 v0.9.0 (支持批量生成和日志功能)")
    ap.add_argument("--lib", required=True, help="verilog_lib.v")
    ap.add_argument("--in", dest="infile", required=True, help="输入门级verilog")
    ap.add_argument("--out", help="输出verilog（单个生成模式时使用）")
    ap.add_argument("--map", required=True, help="映射.txt (gate_simplification dict)")
    ap.add_argument("--rules", required=True, help="等价变换规则.txt (gate_equivalences dict)")
    ap.add_argument("--seed", type=int, default=1, help="随机种子（单个生成模式时使用）")
    ap.add_argument("--suffix", default="equiv_equiv", help="模块名后缀")
    ap.add_argument("--log-file", type=Path, help="生成日志文件路径（单个生成模式）。若不指定，则不写文件")
    ap.add_argument("--scope-file", type=Path, help="限定修改范围的文件，包含 Verilog 门实例片段")

        # 新增：记录和加载规则使用次数的文件
    ap.add_argument("--load-usage", type=Path, help="读取已有的规则使用次数统计文件(JSON)")
    ap.add_argument("--save-usage", type=Path, help="保存本次操作后的规则使用次数统计文件(JSON)")
    
    # 门增加参数
    ap.add_argument("--strength", type=float, default=1.0, help="每个符合条件门的重写概率 (0..1)")
    ap.add_argument("--max-rewrites", type=int, default=100000, help="最大重写门数")
    ap.add_argument("--max-growth", type=float, default=100.0, help="最大新增门比例 (0.30 => +30%)")
    ap.add_argument("--per-type-limit", type=int, default=999999, help="每种简化类型的重写上限")
    ap.add_argument("--max-iterations", type=int, default=50, help="最大迭代次数（单个生成模式时使用）")
    ap.add_argument("--max-inv-buf-expand", type=int, default=100, help="INV/BUF最大分解次数")

    ap.add_argument("--local-size", type=int, default=0, help="局部变换：整个运行固定在随机连通的N个门窗口内(0=全局)")
    ap.add_argument("--local-depth", type=int, default=2, help="局部变换：固定窗口BFS最大深度")

    ap.add_argument("--first-rule-prob", type=float, default=0.5, help="第一条规则被选中的概率 (0..1)")
    ap.add_argument("--selection-mode", choices=["random", "topk", "weighted"], default="weighted", help="候选实例选择方式")
    ap.add_argument("--region-focus", choices=["balanced", "rare", "low_obs", "low_ctrl", "suspicious", "normal"], default="balanced", help="候选区域偏好")
    ap.add_argument("--score-temperature", type=float, default=1.0, help="score采样温度（当前用于预留调节）")
    ap.add_argument("--score-topk", type=int, default=0, help="按score排序后只保留前K个候选（0=不限）")
    ap.add_argument("--risk-threshold", type=float, default=0.0, help="候选最小风险分数阈值")
    ap.add_argument("--weight-position", type=float, default=1.0, help="位置风险权重")
    ap.add_argument("--weight-scale", type=float, default=1.0, help="改动规模/局部复杂度权重")
    ap.add_argument("--weight-rare", type=float, default=1.0, help="稀有节点倾向权重")
    ap.add_argument("--weight-observability", type=float, default=1.0, help="低可观测性权重")
    ap.add_argument("--weight-controllability", type=float, default=1.0, help="低可控性权重")
    ap.add_argument("--weight-camouflage", type=float, default=1.0, help="伪装/自然度风格权重")
    ap.add_argument("--weight-rule-diversity", type=float, default=0.25, help="规则多样性权重")
    ap.add_argument("--max-score-impact", type=float, default=1.0, help="单次变换允许的局部score最大变化")
    ap.add_argument("--max-ctrl-delta", type=float, default=1.0, help="单次变换允许的ctrl最大变化")
    ap.add_argument("--max-obs-delta", type=float, default=1.0, help="单次变换允许的obs最大变化")
    ap.add_argument("--max-naturalness-delta", type=float, default=1.0, help="单次变换允许的naturalness最大变化")

    ap.add_argument("--expansion-mode", action="store_true", help="启用扩充专用模式：规则重排+扩充专用分数")
    ap.add_argument("--expansion-score-weight", type=float, default=0.7, help="扩充专用分数在候选总分中的权重 (0..1)")
    ap.add_argument("--dump-reordered-rules", type=Path, help="导出重排后的rule_expand文件")
    ap.add_argument("--weight-expand-quality", type=float, default=0.45, help="预扩充自身质量权重")
    ap.add_argument("--weight-stage2-decomp", type=float, default=0.30, help="后续门分解变换质量权重")
    ap.add_argument("--weight-stage2-merge", type=float, default=0.25, help="后续门合并变换质量权重")
    ap.add_argument("--global-score-csv", type=Path, help="导出前后全局评分CSV")
    ap.add_argument("--global-score-json", type=Path, help="导出前后全局评分JSON摘要")
    ap.add_argument("--global-score-topn", type=int, default=50, help="日志/JSON中保留的全局高分节点数量")

    ap.add_argument("--diversity-weight", type=float, default=0.35, help="候选选择时多样性约束强度 (0..1)")
    ap.add_argument("--diversity-spatial-weight", type=float, default=0.45, help="空间新颖性权重")
    ap.add_argument("--diversity-type-weight", type=float, default=0.35, help="门类覆盖新颖性权重")
    ap.add_argument("--diversity-rule-weight", type=float, default=0.20, help="规则覆盖新颖性权重")
    ap.add_argument("--diversity-hops", type=int, default=4, help="空间多样性计算时考虑的最大图距离")
    ap.add_argument("--diversity-min-factor", type=float, default=0.35, help="多样性约束对高质量候选保留的最小系数")
    
    # 新增参数
    ap.add_argument("--location-file", type=Path, help="add_location.txt文件路径，包含特定位置的分解规则")
    ap.add_argument("--average-mode", action="store_true", help="启用average模式，限制每种规则的最大使用次数")
    ap.add_argument("--max-rule-use", type=int, help="每种规则最大使用次数（仅在average模式下有效）")
    ap.add_argument("--trojanop", type=int, default=0, help="对木马门执行变换的次数")
    
    # 批量生成参数
    ap.add_argument("--batch", action="store_true", help="启用批量生成模式")
    ap.add_argument("--iter-start", type=int, default=10, help="批量生成：迭代次数起始值")
    ap.add_argument("--iter-end", type=int, default=50, help="批量生成：迭代次数结束值")
    ap.add_argument("--iter-step", type=int, default=10, help="批量生成：迭代次数步长")
    ap.add_argument("--output-dir", type=Path, default="output_batch", help="批量生成：输出文件夹")
    ap.add_argument("--log-dir", type=Path, help="批量生成：日志文件夹（默认: output_dir/log_file）")
    
    ap.add_argument("--netlist-id", type=str, help="唯一网表ID，默认取文件名")
    ap.add_argument("--mapping-out", type=str, help="映射关系输出路径 (JSON)")
    args = ap.parse_args()


    netlist_id = args.netlist_id if args.netlist_id else os.path.basename(args.infile)
    # 检查参数
    if args.batch:
        # 批量生成模式
        if not args.infile:
            print("[ERROR] 批量生成模式需要指定输入文件")
            sys.exit(1)
        run_batch_generation(args)
    else:
        trans_dir = Path("trans")
        mappings_dir = Path("mappings")
        trans_dir.mkdir(exist_ok=True)
        mappings_dir.mkdir(exist_ok=True)
        if args.out:
            args.out = str(trans_dir / os.path.basename(args.out))
        if args.mapping_out:
            args.mapping_out = str(mappings_dir / os.path.basename(args.mapping_out))
        # 单个生成模式
        if not args.out:
            print("[ERROR] 单个生成模式需要指定输出文件")
            sys.exit(1)
        
        # 加载库和映射
        lib_ports, lib_outs, lib_ins = parse_lib_info(Path(args.lib).read_text(encoding="utf-8", errors="ignore"))
        gate_simplification = load_py_dict_from_file(Path(args.map), "gate_simplification")
        gate_equivalences   = load_py_dict_from_file(Path(args.rules), "gate_equivalences")

        # 解析输入网表
        timescale, mod = parse_gatelevel_verilog(Path(args.infile).read_text(encoding="utf-8", errors="ignore"))
        
        print(f"[INFO] 输入模块: {mod.name}, 门数: {len(mod.instances)}")
        print(f"[INFO] 执行门增加重写模式")

        # 解析location文件
        location_map = {}
        if args.location_file:
            location_map = parse_location_file(args.location_file)
        mod_scope = None
        if args.scope_file:
            mod_scope = parse_scope_file(args.scope_file)
        
        # 执行门增加重写
        limits = RewriteLimits(
            strength=max(0.0, min(1.0, args.strength)),
            max_rewrites=max(0, args.max_rewrites),
            max_growth=max(0.0, args.max_growth),
            per_type_limit=max(0, args.per_type_limit),
            max_iterations=max(1, args.max_iterations),
            max_inv_buf_expand=max(0, args.max_inv_buf_expand),
            first_rule_prob=max(0.0, min(1.0, args.first_rule_prob)),
            average_mode=args.average_mode,
            max_rule_use=args.max_rule_use,
            modification_scope=mod_scope,
            location_file=args.location_file,
            local_size=args.local_size,
            local_depth=args.local_depth,
            selection_mode=args.selection_mode,
            region_focus=args.region_focus,
            score_temperature=max(1e-6, args.score_temperature),
            score_topk=max(0, args.score_topk),
            risk_threshold=args.risk_threshold,
            weight_position=args.weight_position,
            weight_scale=args.weight_scale,
            weight_rare=args.weight_rare,
            weight_observability=args.weight_observability,
            weight_controllability=args.weight_controllability,
            weight_camouflage=args.weight_camouflage,
            weight_rule_diversity=args.weight_rule_diversity,
            max_score_impact=max(0.0, args.max_score_impact),
            max_ctrl_delta=max(0.0, args.max_ctrl_delta),
            max_obs_delta=max(0.0, args.max_obs_delta),
            max_naturalness_delta=max(0.0, args.max_naturalness_delta),
            expansion_mode=args.expansion_mode,
            expansion_score_weight=max(0.0, min(1.0, args.expansion_score_weight)),
            reordered_rules_out=args.dump_reordered_rules,
            weight_expand_quality=args.weight_expand_quality,
            weight_stage2_decomp=args.weight_stage2_decomp,
            weight_stage2_merge=args.weight_stage2_merge,
            global_score_csv=args.global_score_csv,
            global_score_json=args.global_score_json,
            global_score_topn=max(1, args.global_score_topn),
            diversity_weight=max(0.0, min(1.0, args.diversity_weight)),
            diversity_spatial_weight=max(0.0, args.diversity_spatial_weight),
            diversity_type_weight=max(0.0, args.diversity_type_weight),
            diversity_rule_weight=max(0.0, args.diversity_rule_weight),
            diversity_hops=max(1, args.diversity_hops),
            diversity_min_factor=max(0.0, min(1.0, args.diversity_min_factor)),
        )
        
        # 日志（单个生成模式）
        log_writer = None
        if args.log_file:
            args.log_file.parent.mkdir(parents=True, exist_ok=True)
            log_fp = open(args.log_file, "w", encoding="utf-8")
            log_fp.write("门增加重写日志文件\n")
            log_fp.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_fp.write(f"输入文件: {args.infile}\n")
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

        expander = GateExpander(
            lib_ports=lib_ports,
            lib_outs=lib_outs,
            lib_ins=lib_ins,
            gate_simplification=gate_simplification,
            gate_equivalences=gate_equivalences,
            seed=args.seed,
            location_map=location_map,
            log_writer=log_writer,
            netlist_id=netlist_id,
        )
        if args.load_usage:
            expander.stats.load_from_file(args.load_usage)

        # 执行变换
        out_mod = expander.expand(mod, limits, name_suffix=args.suffix, trojan_op=args.trojanop)

        # 【核心修改：生成并保存整合后的 Mapping】
        if args.mapping_out:
            # 获取最终网表中所有存在的实例名字（用于剔除中间被删掉的门）
            final_gate_names = {inst.name for inst in out_mod.instances}
            
            # 整合 mapping
            final_alignment = {}
            for entry in expander.node_mappings:
                orig = entry["src"] 
                trans = entry["dst"]
                
                # 只有当变换后的门最终还留在网表里，才算有效的映射
                if trans in final_gate_names:
                    if orig not in final_alignment:
                        final_alignment[orig] = []
                    if trans not in final_alignment[orig]:
                        final_alignment[orig].append(trans)
            
            # 保存到文件
            import json
            output_data = {
                "netlist_id": netlist_id,
                "src_verilog": args.infile,
                "dst_verilog": args.out,
                "node_alignment": final_alignment
            }
            with open(args.mapping_out, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=4)
            print(f"[OK] 映射关系已保存至: {args.mapping_out}")
        
        # 保存操作记录
        if args.save_usage:
            expander.stats.save_to_file(args.save_usage)

        
        print(f"[INFO] 最终门数: {len(out_mod.instances)}")
        
        # 生成输出
        verilog_out = emit_verilog(timescale, out_mod, lib_ports)
        Path(args.out).write_text(verilog_out, encoding="utf-8")
        print(f"[OK] 写入输出文件: {args.out}")
        if args.log_file:
            try:
                log_fp.write(f"输出文件: {args.out}\n")
                log_fp.write(f"最终门数: {len(out_mod.instances)}\n")
                log_fp.write(f"原始门数: {len(mod.instances)}\n")
                log_fp.write("="*80 + "\n")
                log_fp.close()
            except Exception:
                pass
        out_path = Path(args.out)
        csv_dir = out_path.parent / "log"
        csv_dir.mkdir(exist_ok=True)
        csv_name = csv_dir / f"{out_path.stem}.csv"
        
        import csv
        with open(csv_name, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["变换门名称", "变换门类型", "使用规则序号", "变换比例"])
            writer.writeheader()
            writer.writerows(expander.stats.csv_records)
            
            # --- 修改：追加汇总信息 ---
            f.write("\n" + "="*15 + " 变换汇总统计 " + "="*15 + "\n")
            sd = expander.stats.summary_data
            f.write(f"原始木马门总数,{sd['原木马门数']}\n")
            f.write(f"原始普通门总数,{sd['原普通门数']}\n")
            f.write(f"变换后木马门总数,{sd['变换后木马门数']}\n")
            f.write(f"变换后普通门总数,{sd['变换后普通门数']}\n")
            f.write(f"门数净增加总量,{expander.stats.total_added_gates}\n")
            f.write(f"总变换操作次数,{expander.stats.total_rewrites}\n")
            
        print(f"[OK] 变换日志及汇总已保存至: {csv_name}")

if __name__ == "__main__":
    main()