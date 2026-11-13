# -*- coding: utf-8 -*-
"""
assign_to_gates.py —— 把 yosys 生成的"表达式风格"等价网表转换成"库单元风格"。

为什么要这一步：
  yosys 综合后输出的是内部单元和 `assign X = A & B;` 这种表达式，而本仓库的 GNN 数据流水线
  用的是 parser2，它只认"门单元实例 + 简单 assign"。直接写 techmap 让 yosys 输出库单元也不行——
  write_verilog 会把 verilog_lib.v 里的库单元定义一起写出来，再读回去就撞"模块重复定义"。
  所以改成在这里转换：yosys 照旧输出表达式（这批已经 CEC 全过），
  我们用**自己的**表达式解析器把每个 assign 拆成门单元，再用 netlist_lib 的发射器写回去。

转换规则（都取设计库里真实存在的单元）：
    ~a        → INVX0 / INVX1_RS
    a & b     → AND2X1
    a | b     → OR2X1
    a ^ b     → XOR2X1
    a ^~ b    → XNOR2X1
    c ? a : b → MX2X1_RS / MUX21X1
    多输入     → 嵌套成二叉
    常量、纯别名、拼接 → 原样保留成简单 assign（parser2 认这种）

转换完必须重跑 CEC（本脚本不跑，交给外层的 CEC 脚本），确认没转错。

用法：
    py phase2/ys/assign_to_gates.py --manifest generate_trans/yosys_netlists_beta/ys_manifest.csv \
        --ys-root generate_trans/yosys_netlists_beta --out-root generate_trans/yslib_beta
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

from phase2 import netlist_lib as NL  # noqa: E402
from phase2.ys import netlist_feats as NF  # noqa: E402

LIB_DEFAULT = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"


def _san(n: str) -> str:
    """新网名只能含字母数字下划线。左值可能是位选（xmit_dataH[0]）或转义标识符，
    直接拿来当前缀会生成 `wire xmit_dataH[0]__g1` 这种非法声明。"""
    import re
    s = re.sub(r"[^A-Za-z0-9_]", "_", str(n))
    return s if s and s[0].isalpha() else "n_" + s


PREF = {
    "&": ["AND2X2", "AND2X1", "AND2X1_RS"],
    "|": ["OR2X1", "OR2X1_RS", "NOR2X0"],
    "^": ["XOR2X1", "XOR2X1_RS", "XNOR2X1"],
    "^~": ["XNOR2X1", "XNOR2X1_RS", "XOR2X1"],
    "~": ["INVX0", "INVX1_RS"],
    "?": ["MX2X1_RS", "MUX21X1", "MUX21X2"],
}


def parse_args():
    ap = argparse.ArgumentParser(description="yosys 表达式网表 → 库单元网表")
    ap.add_argument("--manifest", type=Path,
                    default=ROOT / "generate_trans" / "yosys_netlists_beta" / "ys_manifest.csv")
    ap.add_argument("--ys-root", type=Path,
                    default=ROOT / "generate_trans" / "yosys_netlists_beta")
    ap.add_argument("--out-root", type=Path, default=ROOT / "generate_trans" / "yslib_beta")
    ap.add_argument("--lib", type=Path, default=LIB_DEFAULT)
    ap.add_argument("--only-pass", action="store_true", default=True)
    ap.add_argument("--flatten-aliases", action="store_true",
                    help="展平别名 assign（**默认关闭**：冒烟实测它会破坏等价性，见文件头注释）")
    ap.add_argument("--no-final", action="store_true", help="诊断用：关掉最外层直驱原名")
    ap.add_argument("--limit", type=int, default=0)
    return ap.parse_args()


class Conv:
    def __init__(self, nl: NL.Netlist, lib: dict):
        self.nl, self.lib = nl, lib
        self.k = 0
        self.declared = set()
        self.keep: list = []            # 需要保留成简单 assign 的 (网名, 右值)
        self.prov: dict = {}            # 生成的中间网名 → 它原本属于哪条 assign 的左值
                                        # （下游靠它把"转换后的节点"绑回原始网名）
        # P1（A3 收尾）：**门实例级**溯源 —— 每个新造的门实例 → 它最终驱动的**原始网名**。
        # 下游图网络的节点=实例，靠这张表就能把标签从源实例传到转换后的门实例上，
        # 不必再依赖"名字有没有活下来"（见 10.15/.../A3_keep三方案/说明.md §0 P1）。
        self.inst_prov: dict = {}

    def new_net(self, base: str) -> str:
        self.k += 1
        n = f"{_san(base)}__g{self.k}"
        self.prov[n] = str(base)
        return n

    def cell(self, op: str, ins: list, out: str, base: str) -> None:
        gate = NL.pick_gate(self.lib, len(ins), PREF[op])
        if gate is None:
            raise RuntimeError(f"库里找不到能实现 {op} 的 {len(ins)} 输入单元")
        tpl = self.lib.get(gate)
        if tpl is None:
            raise RuntimeError(f"库模板缺失：{gate}")
        ports, out_ports = tpl["inputs"], tpl["outputs"]
        if len(ports) != len(ins):
            raise RuntimeError(f"{gate} 的输入端口数 {len(ports)} 与 {len(ins)} 不符")
        if len(out_ports) != 1:
            raise RuntimeError(f"{gate} 的输出端口不是单个：{out_ports}")
        conns = [(p, n) for p, n in zip(ports, ins)]
        conns.append((out_ports[0], out))
        self.k += 1
        self.nl.insts.append(NL.Inst(gate=gate, name=f"g_{base}_{self.k}", conns=conns))
        if out not in self.declared:            # 中间网要写进声明，否则 parser2 认不出
            self.nl.port_decls.append(f"wire {out}")
            self.declared.add(out)

    def build(self, e: NF.Expr, base: str, final: str | None = None):
        """返回 (网名, 是否引入常量/拼接)。

        `final` 只用在**最外层**：让最后一级单元直接驱动原始左值网名，
        不再补一条 `assign lhs = lhs__gK;` 的别名（别名是链路断掉的根源）。
        """
        if e.op == "var":
            return e.name, False
        if e.op == "const":
            n = self.new_net(base)
            self.keep.append((n, e.const))
            if n not in self.declared:
                self.nl.port_decls.append(f"wire {n}")
                self.declared.add(n)
            return n, True
        if e.op == "~":
            a, ka = self.build(e.a, base)
            out = final or self.new_net(base)
            self.cell("~", [a], out, base)
            return out, ka
        if e.op in ("?", "&", "|", "^", "^~"):
            a, ka = self.build(e.a, base)
            b, kb = self.build(e.b, base)
            if e.op == "?":
                c, kc = self.build(e.c, base)
                out = final or self.new_net(base)
                # 库里的 mux 是 Q = S ? IN2 : IN1，而解析出来的是 S ? then : else
                self.cell("?", [c, b, a], out, base)
                return out, True
            out = final or self.new_net(base)
            self.cell(e.op, [a, b], out, base)
            return out, (ka or kb)
        raise RuntimeError(f"不支持的操作：{e.op}")


def flatten_aliases(nl: NL.Netlist, keep: list) -> tuple:
    """把纯别名（`assign a = b;`）展平：按并查集合并、连接处改用代表名，别名行不再输出。

    代表名的选择有**偏好**，不能随便挑：
        端口名 > 名字里含 `Trojan` 的 > 其它（都同优先时取左值）。
    因为这些名字是下游做锚点/绑定用的，挑错了会把锚点抹掉。
    """
    alias = [(l, r) for l, r in keep if re.fullmatch(r"\\?[^\s(){}]+", str(r).strip())]
    if not alias:
        return keep, 0
    aset = {str(l) for l, _r in alias} | {str(r) for _l, r in alias}
    par = {n: n for n in aset}

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    def rank(n: str) -> int:
        if n in nl.inputs or n in nl.outputs:
            return 3
        if "trojan" in n.lower():
            return 2
        return 1

    for l, r in alias:
        a, b = find(str(l)), find(str(r))
        if a == b:
            continue
        # 优先级高的当代表；平手时保留左值（下游按左值找）
        if (rank(b), 0) > (rank(a), 1):
            par[a] = b
        else:
            par[b] = a
    rep = {n: find(n) for n in aset}
    n_fix = 0
    for inst in nl.insts:
        new_conns = []
        for p, n in inst.conns:
            m = rep.get(str(n))
            if m is not None and m != str(n):
                n_fix += 1
                n = m
            new_conns.append((p, n))
        inst.conns = new_conns
    return [row for row in keep if not (str(row[0]) in rep and row in alias)], n_fix


    def cell(self, op: str, ins: list, out: str, base: str) -> None:
        gate = NL.pick_gate(self.lib, len(ins), PREF[op])
        if gate is None:
            raise RuntimeError(f"库里找不到能实现 {op} 的 {len(ins)} 输入单元")
        tpl = self.lib.get(gate)
        if tpl is None:
            raise RuntimeError(f"库模板缺失：{gate}")
        ports, out_ports = tpl["inputs"], tpl["outputs"]
        if len(ports) != len(ins):
            raise RuntimeError(f"{gate} 的输入端口数 {len(ports)} 与 {len(ins)} 不符")
        if len(out_ports) != 1:
            raise RuntimeError(f"{gate} 的输出端口不是单个：{out_ports}")
        conns = [(p, n) for p, n in zip(ports, ins)]
        conns.append((out_ports[0], out))
        self.k += 1
        self.nl.insts.append(NL.Inst(gate=gate, name=f"g_{base}_{self.k}", conns=conns))
        if out not in self.declared:            # 中间网要写进声明，否则 parser2 认不出
            self.nl.port_decls.append(f"wire {out}")
            self.declared.add(out)

    def build(self, e: NF.Expr, base: str):
        """返回 (网名, 是否引入常量/拼接)。"""
        if e.op == "var":
            return e.name, False
        if e.op == "const":
            n = self.new_net(base)
            self.keep.append((n, e.const))
            if n not in self.declared:
                self.nl.port_decls.append(f"wire {n}")
                self.declared.add(n)
            return n, True
        if e.op == "~":
            a, ka = self.build(e.a, base)
            out = self.new_net(base)
            self.cell("~", [a], out, base)
            return out, ka
        if e.op in ("?", "&", "|", "^", "^~"):
            a, ka = self.build(e.a, base)
            b, kb = self.build(e.b, base)
            if e.op == "?":
                c, kc = self.build(e.c, base)
                out = self.new_net(base)
                # 库里的 mux 是 Q = S ? IN2 : IN1，而解析出来的是 S ? then : else
                self.cell("?", [c, b, a], out, base)
                return out, True
            out = self.new_net(base)
            self.cell(e.op, [a, b], out, base)
            return out, (ka or kb)
        raise RuntimeError(f"不支持的操作：{e.op}")


def has_unsupported(e) -> bool:
    """拼接、常量等一律不处理，整条 assign 原样保留。"""
    if e is None:
        return True
    if e.op in ("cat", "const"):
        return True
    for ch in (e.a, e.b, e.c):
        if ch is not None and has_unsupported(ch):
            return True
    return False


def _protect_escaped(text: str) -> str:
    """给转义标识符补上"分界空格"。

    Verilog 的转义标识符以 `\\` 开头、**到第一个空白为止**。
    yosys 输出里会有 `wire \\TrojanAHJ.Y ;` 这种网名（单元名.端口名），
    而 netlist_lib 的发射器在写声明时是 `f"  {d};"`，正好把这个保护空格丢了，
    于是分号被吞进标识符里 → yosys 报 syntax error。
    这里统一兜一层：凡是转义标识符后面紧跟 `;` `,` `)` `=` 的，插一个空格。
    """
    return re.sub(r"(\\[^\s;),=]*)(?=[;),=])", r"\1 ", text)


def main() -> int:
    a = parse_args()
    import pandas as pd
    lib = NL.load_library(a.lib)
    man = pd.read_csv(a.manifest)
    if a.only_pass and "cec" in man.columns:
        man = man[man["cec"].astype(str).str.contains("PASS", na=False)]
    if a.limit:
        man = man.head(a.limit)
    print(f"[INFO] 待转换 {len(man)} 个变体")

    rows = []
    for r in man.itertuples():
        src = a.ys_root / r.host / f"{r.stem}__ys_{r.recipe}.v"
        if not src.exists():
            continue
        try:
            nl = NL.parse_netlist(src, lib)
            # 清掉 yosys 的头注释：parser 会把它塞进 tail_head，而发射器会在后面补一个分号，
            # 于是变成 `*/;`，再读就报 syntax error（这个坑是实测撞出来的）。
            nl.tail_head = ""
            nl.tail = ""
            conv = Conv(nl, lib)
            keep = []
            n_conv = n_raw = 0
            for lhs, rhs in nl.assigns:
                e = NF.parse_expr(rhs)
                if e is None or e.op == "var" or has_unsupported(e):
                    keep.append((lhs, rhs))
                    n_raw += 1
                    continue
                # 最外层直接驱动**原始左值网名**，不再补 `assign lhs = lhs__gK;` 别名
                n_before = len(nl.insts)
                out, _k = conv.build(e, lhs.replace("\\", "_"),
                                     final=(None if a.no_final else lhs))
                # P1：逐个新造的门实例记「门实例 → 它驱动的**原始网名**」。
                # Conv.cell 保证**末位连接是输出端口**；中间网经 prov 折回原左值，
                # 最外层那级驱动就是 lhs 本身 —— 于是下游可以按实例绑标签，不必看名字。
                for _inst in nl.insts[n_before:]:
                    _o = str(_inst.conns[-1][1])
                    conv.inst_prov[str(_inst.name)] = str(conv.prov.get(_o, _o))
                if out != lhs:
                    keep.append((lhs, out))
                n_conv += 1
            # 别名展平**默认关闭**：冒烟实测它会破坏等价性（同一输入下 CEC 从 272/272 PASS
            # 变成 102/92/10 FAIL）。原因是并查集合并后代表名的选择会改动驱动方向，
            # 把某些"驱动网"合并掉、留下没有驱动的网。需要时用 --flatten-aliases 显式打开并重跑 CEC。
            if a.flatten_aliases:
                keep, n_fix = flatten_aliases(nl, keep)
            else:
                n_fix = 0
            nl.assigns = keep + conv.keep
            dst = a.out_root / r.host / f"{r.stem}__ys_{r.recipe}.v"
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(_protect_escaped(NL.emit_netlist(nl)), encoding="utf-8")
            # 绑定用出处表：① 中间网名 → 原左值网名；② **门实例名 → 它驱动的原始网名**（P1）
            dst.with_suffix(".map.json").write_text(
                json.dumps({"view": f"{r.stem}__ys_{r.recipe}",
                            "n_alias_flattened": n_fix,
                            "prov": conv.prov, "inst_prov": conv.inst_prov},
                           ensure_ascii=False, indent=0), encoding="utf-8")
            lint = NL.lint(nl)
            rows.append({"host": r.host, "stem": r.stem, "recipe": r.recipe,
                         "n_assign_in": n_conv + n_raw, "n_converted": n_conv,
                         "n_kept_raw": n_raw, "n_alias_flattened": n_fix,
                         "n_prov": len(conv.prov), "n_inst_prov": len(conv.inst_prov),
                         "n_inst_out": len(nl.insts),
                         "clean": bool(lint["clean"]),
                         "dangling": int(lint.get("n_dangling", -1)),
                         "multi": int(lint.get("n_multi", -1)),
                         "undriven_out": int(lint.get("n_undriven_out", -1)),
                         "file": str(dst)})
        except Exception as ex:                                 # noqa: BLE001
            rows.append({"host": r.host, "stem": r.stem, "recipe": r.recipe,
                         "n_assign_in": -1, "n_converted": -1, "n_kept_raw": -1,
                         "n_inst_out": -1, "n_inst_prov": -1, "clean": False, "dangling": -1,
                         "multi": -1, "undriven_out": -1, "file": f"ERROR: {ex}"})
    d = pd.DataFrame(rows)
    a.out_root.mkdir(parents=True, exist_ok=True)
    d.to_csv(a.out_root / "convert_manifest.csv", index=False, encoding="utf-8-sig")
    ok = d[d.file.str.startswith("ERROR") == False]             # noqa: E712
    print(f"[OK] 成功 {len(ok)} / {len(d)}   合法(clean) {int(ok.clean.sum())}")
    if len(d) - len(ok):
        print(d[d.file.str.startswith("ERROR")].file.head(3).to_string())
    print(f"[导出] {a.out_root / 'convert_manifest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
