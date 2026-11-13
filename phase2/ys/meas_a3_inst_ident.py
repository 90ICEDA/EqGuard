# -*- coding: utf-8 -*-
"""
meas_a3_inst_ident.py —— **实例级**可追溯性测量（A3 补充）。

背景：下游图网络的**节点 = 实例（门）**，信号名本身不是特征（名字"好不好听"不重要），
所以真正该问的是：**变换 + 转换之后，木马实例还能不能被认出来（绑到标签）**。
keep_ablation.py 里那套「名字存活率」只回答"名字还在不在"✗，回答不了这个问题 ✗。

本脚本的口径（**两条通道分开数**）：
  通道 A｜**溯源通道（正解）**：
      转换器给每个门实例起名 `g_{base}_{k}`（assign_to_gates.Conv.cell，第 110 行），
      且 `map.json.prov[新网名] = 原网名`（第 92 行）。
      于是：门实例 →（名字/prov 解出 base）→ 源网 →（源网表 drivers）→ 源实例。
      能回到木马实例 = **可追溯** ✓（与名字是否 Trojan 开头无关）。
  通道 B｜**名字巧合通道（现状在用）**：
      转换后门实例名里直接含 `Trojan...` 锚名（如 `g_TrojanA_t1_102`）。
      它**只在 keep 保住网名时**才偶然成立 ✗，且一旦 base 被 abc/aig 抹成 `_193_` 就失效 ✗。

指标（每个 (recipe, scheme) 一行）：
  n_gates_parsed / n_gates_regex : 解析器 / 正则(`( .`) 两种口径的门实例数（交叉校验）
  prov_cov        : 门实例里能解出 base 原网名的比例
  recov_insts / anchor_inst_total : **溯源通道**能回到几个木马实例（核心）
  name_insts      : 名字巧合通道能认出几个（对照）
  recov_nets / anchor_net_total   : 4 个木马网能被定位几个
  hijack_recov    : 是否追到劫持点（源网 rec_readyH / rec_readyH_orig）
  unresolved      : 两通道都认不出的门实例数

用法：
    py phase2/ys/meas_a3_inst_ident.py --views rs232t1000__injalpha_d1_s42 --recipes abc,nand,aig
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CUR))

from phase2 import netlist_lib as NL        # noqa: E402
import keep_ablation as KA                  # noqa: E402  复用锚点判定 / 前缀读取

LIB_DEFAULT = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"
SRC_ROOT = ROOT / "generate_trans" / "hosts_bt2"
RAW_ROOT = ROOT / "generate_trans" / "keepab" / "out"
CONV_ROOT = ROOT / "generate_trans" / "keepab" / "conv"
GEN_RE = re.compile(r"^g_(?P<base>.+)_(?P<k>\d+)$")   # Conv.cell: f"g_{base}_{k}"
REGEX_INST = re.compile(r"\(\s*\.\w+")
# 文本级门实例（实例名允许点号/转义：full 方案会造出 `g__TrojanAT1.A_222`）
GATE_RE = re.compile(r"^\s*(\w+)\s+([\\\w.$\[\]]+)\s*\((.*)\)\s*$", re.S)
CONN_RE2 = re.compile(r"\.\s*(\w+)\s*\(\s*([^)]*)\)")


def norm(n: str) -> str:
    """去掉 Verilog 转义前缀 `\\`，便于比较。"""
    return n[1:] if n.startswith("\\") else n


class UF:
    """并查集：把源网表 `assign a = b;` 的别名网并成一组。"""

    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def src_facts(src: Path, lib) -> dict:
    """源网表：木马锚点实例/网 + 网归一化→驱动实例（含 assign 别名合并）。"""
    nl = NL.parse_netlist(src, lib)
    uf = UF()
    for lhs, rhs in nl.assigns:
        uf.union(norm(lhs), norm(rhs))
    net2inst, port2net = {}, {}
    for i in nl.insts:
        for port, n in i.conns:
            port2net[f"{i.name}.{port}"] = uf.find(norm(n))
        for _port, n in nl.outs(i):          # 需要 lib 才能认出输出端口
            net2inst.setdefault(uf.find(norm(n)), i.name)
    return {"nl": nl, "uf": uf, "net2inst": net2inst, "port2net": port2net}


def conv_gates(conv: Path) -> list:
    """转换后的门实例：[(实例名, 输出网)] —— **文本级**解析。

    为什么不用 netlist_lib：`full` 方案下转换器会造出带点号的实例名
    （`g__TrojanAT1.A_222`）✗，netlist_lib 的 INST_RE 认不出 → 会漏掉一片 ✗。
    转换器保证**最后一个连接是输出**（assign_to_gates.py 第 108 行）。
    """
    text = conv.read_text(encoding="utf-8", errors="replace") if isinstance(conv, Path) else str(conv)
    out = []
    for st in text.split(";"):
        m = GATE_RE.match(st)
        if not m:
            continue
        gate, name = m.group(1), m.group(2)
        if gate in ("module", "wire", "assign", "input", "output", "reg"):
            continue
        conns = CONN_RE2.findall(m.group(3))
        if conns:
            out.append((name, conns[-1][1].strip()))
    return out


def resolve(net: str, prov: dict, facts: dict) -> str | None:
    """转换后的网名 → 源网。

    三条路依次试：① `prov[新网名] → 原网名`；② 同名；
    ③ `<源实例>.<端口>`（full 方案下转换器会用这种遗留端口名当 base）。
    最后用并查集把 assign 别名归一，要求该组有驱动实例才算解析成功。
    """
    n = norm(net)
    for cand in (norm(prov.get(n, "")), n, facts["port2net"].get(n)):
        if not cand:
            continue
        r = facts["uf"].find(cand)
        if r in facts["net2inst"]:
            return r
    return None


def measure(src: Path, conv: Path, lib, prefix: str | None, detail: list | None = None) -> dict:
    facts = src_facts(src, lib)
    nl = facts["nl"]
    a_i = {i.name for i in nl.insts if KA.is_anchor(i.name, prefix)}
    a_n = {norm(x) for x in KA.nets_of(nl) if KA.is_anchor(x, prefix)}
    prov_p = conv.with_suffix(".map.json")
    prov = json.loads(prov_p.read_text(encoding="utf-8"))["prov"] if prov_p.exists() else {}
    text = conv.read_text(encoding="utf-8", errors="replace")

    gates = conv_gates(conv)
    recov_insts, name_insts, recov_nets, unresolved = set(), set(), set(), 0
    hijack = 0
    for name, onet in gates:
        m = GEN_RE.match(name)
        cands = [x for x in (m.group("base") if m else None, norm(onet),
                             norm(prov.get(norm(onet), ""))) if x]
        hit = None
        for c in cands:                       # 通道 A：溯源（源网 → 它的驱动实例）
            hit = resolve(c, prov, facts)
            if hit:
                break
        if hit:
            drv = facts["net2inst"].get(hit)
            if drv:
                if drv in a_i:
                    recov_insts.add(drv)
                if hit in a_n:
                    recov_nets.add(hit)
                if hit in ("rec_readyH", "rec_readyH_orig"):
                    hijack = 1
                if detail is not None and drv in a_i:
                    detail.append((name, m.group("base") if m else norm(onet), hit, drv))
        else:
            unresolved += 1
        for x in a_i | a_n:                   # 通道 B：名字巧合（门实例名里带锚名）
            if x in name:
                name_insts.add(x)
    return {
        "n_gates_parsed": len(gates),
        "n_gates_regex": len(REGEX_INST.findall(text)),
        "prov_cov": sum(1 for n, _ in gates if GEN_RE.match(n)) / max(1, len(gates)),
        "anchor_inst_total": len(a_i), "anchor_net_total": len(a_n),
        "recov_insts": len(recov_insts), "name_insts": len(name_insts),
        "recov_nets": len(recov_nets), "hijack_recov": hijack,
        "unresolved": unresolved,
        "recov_inst_names": ",".join(sorted(recov_insts)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", default="rs232t1000__injalpha_d1_s42")
    ap.add_argument("--recipes", default="abc,nand,aig")
    ap.add_argument("--schemes", default="none,cur,bnd,full")
    ap.add_argument("--detail", action="store_true", help="打印每条「门 → 源网 → 源实例」归因证据")
    ap.add_argument("--lib", type=Path, default=LIB_DEFAULT)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "10.15" / "01_数据与标签" / "A3_keep三方案" / "tables")
    a = ap.parse_args()

    lib = NL.load_library(a.lib)
    prefixes = KA.load_prefixes(SRC_ROOT)
    rows = []
    for view in a.views.split(","):
        host = view.split("__")[0]
        src = SRC_ROOT / host / f"{view}.v"
        prefix = prefixes.get(view)
        for recipe in a.recipes.split(","):
            for scheme in a.schemes.split(","):
                conv = CONV_ROOT / host / f"{view}__keep{scheme}__ys_{recipe}.v"
                if not (src.exists() and conv.exists()):
                    print(f"[跳过] {view} {recipe}/{scheme}：缺文件")
                    continue
                r = {"view": view, "recipe": recipe, "scheme": scheme}
                det = [] if a.detail else None
                r.update(measure(src, conv, lib, prefix, det))
                if det:
                    for gname, base, hit, drv in det[:8]:
                        print(f"        门 {gname} ｜ base={base} ｜ 源网={hit} ｜ 源实例={drv}")
                rows.append(r)
                print(f"[实例级] {view} {recipe}/{scheme}: "
                      f"溯源认出木马实例 {r['recov_insts']}/{r['anchor_inst_total']}"
                      f"（名字巧合 {r['name_insts']}）｜网 {r['recov_nets']}/{r['anchor_net_total']}"
                      f"｜劫持点 {'✓' if r['hijack_recov'] else '✗'}"
                      f"｜未解析门 {r['unresolved']}/{r['n_gates_parsed']}")
    if not rows:
        return 1
    d = pd.DataFrame(rows)
    a.out.mkdir(parents=True, exist_ok=True)
    f = a.out / "a3_inst_ident.csv"
    d.to_csv(f, index=False, encoding="utf-8-sig")
    print(f"[OK] {len(d)} 行 → {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
