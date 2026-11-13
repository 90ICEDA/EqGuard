#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
equiv_rewrite_netlist.py v0.4.0 (label-blind decomposition rewrite)

功能：
1. 从 orig/ 目录读取原始网表，生成 label-blind 等价变换视图
2. 自动生成日志文件
3. 从 add_location.txt 读取特定位置的分解规则
4. 输出 mapping JSON、view-level metadata CSV、节点对齐明细 CSV

注：
- --in 只需传文件名，脚本会从 orig/ 目录查找
- --out 的父目录会被忽略，一律写入 trans/
- mapping JSON 和 view_metadata CSV 里的 src/dst 都是纯文件名

用法：
    python add_gate_test4.py --lib verilog_lib.v --map map.txt --rules rule_expand1.txt --seed 42 --in rs232t1000.v --out rs232t1000tr42.v --mapping-out rs232t1000tr42.JSON --operator-family decomp --max-rewrites 50
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
        while rewrite_count < limits.max_rewrites:
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


def build_operator(family_name: str, **kwargs) -> BaseOperator:
    """工厂函数：按 family_name 返回对应的 operator 实例。"""
    if family_name == "decomp":
        return DecompOperator(**kwargs)
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
        while rewrite_count < limits.max_rewrites:
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
                    choices=["decomp", "balance", "refactor", "resub"],
                    help="算子家族，默认 decomp")
    ap.add_argument("--orig-dir", type=Path, default=Path("orig"),
                    help="原始网表所在目录，默认 orig/")
    args = ap.parse_args()

    # ---------- 输出目录 ----------
    trans_dir = Path("trans")
    mappings_dir = Path("mappings")
    trans_dir.mkdir(exist_ok=True)
    mappings_dir.mkdir(exist_ok=True)

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
    )

    out_mod, stats, final_alignment = operator.apply(mod, limits)
    out_mod.name = f"{mod.name}_{args.suffix}"

    # ============================================================
    # 1) 保存 mapping JSON
    # ============================================================
    if mapping_out_path:
        import json
        output_data = {
            "netlist_id": netlist_id,
            "src_verilog": infile_path.name,     # 只取文件名
            "dst_verilog": out_path.name,        # 只取文件名
            "operator_family": args.operator_family,
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
    # 3) view 元数据 CSV（追加模式）
    # ============================================================
    view_meta_path = out_path.parent / "view_metadata.csv"
    view_meta_row = {
        "view_name": out_mod.name,
        "src_verilog": infile_path.name,     # 只取文件名
        "dst_verilog": out_path.name,        # 只取文件名
        "operator_family": args.operator_family,
        "seed": args.seed,
        "strength": args.strength,
        "max_rewrites": args.max_rewrites,
        "orig_gate_count": len(mod.instances),
        "final_gate_count": len(out_mod.instances),
        "edit_count": len(stats.csv_records),
        "gate_expansion": len(out_mod.instances) - len(mod.instances),
        "total_added_gates": stats.total_added_gates,
        "successful_rewrite_count": stats.total_rewrites,
        "rule_use_counts_json": json.dumps(
            {k: {str(kk): vv for kk, vv in v.items()}
             for k, v in stats.rule_use_counts.items()},
            ensure_ascii=False
        ),
    }
    file_exists = view_meta_path.exists()
    with open(view_meta_path, 'a', encoding='utf-8-sig', newline='') as vf:
        writer = csv.DictWriter(vf, fieldnames=list(view_meta_row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(view_meta_row)
    print(f"[OK] view metadata 已追加至: {view_meta_path}")

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