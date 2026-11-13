# -*- coding: utf-8 -*-
"""
netlist_feats.py —— 从 Verilog 网表抽「结构特征 + 功能特征」。

两条关键设计：

1) **精确门语义**：不猜 AOI/OAI 的表达，直接读 `verilog_lib.v` 里每个单元的
   `assign` 语句当公式（例：`AOI221X1: QN = ~((IN1&IN2)|(IN3&IN4)|IN5)`；
   顺便发现 `NBUFFX2` 其实是反相器 `Q = ~IN`）。
   这既服务于功能特征（信号概率/可控性），也让"结构不同但功能等价"的比较有意义。

2) **一个表达式解析器两用**：
   * 解析库单元的 RHS → 得到单元的布尔函数；
   * 解析 yosys 变体里的 `assign Y = a & b;` → 把它**分解成多个算子节点**，
     这样 yosys 网表和原网表都能用同一套特征定义（yosys 会把组合逻辑写成表达式）。

功能特征（第三块要补的）：
  sp  信号概率（PI=0.5，独立输入模型，按拓扑序传播）
  tr  toggle rate = 2·sp·(1−sp)
  cc0/cc1  SCOAP 式 0/1 可控性
  co  SCOAP 式可观测性
  fanin_support  log1p(传递扇入锥里的 PI/FF 输出个数)
  reach_po       log1p(传递扇出可达的输出端口数)
  reach_dff      log1p(传递扇出可达的 FF 数据端数)
  mi_in          节点的输出与各输入之间互信息之和（用两端的 sp 估）
  depth          从 PI/FF 输出的最短逻辑深度
"""
from __future__ import annotations

import math
import re
from pathlib import Path

# --------------------------------------------------------------------------
# 1) 表达式：tokenizer + 递归下降解析
# --------------------------------------------------------------------------
TOKEN_RE = re.compile(r"""
    (?P<num>\d*'[bodhBODH][0-9a-fA-FxXzZ_]+)
  | (?P<esc>\\[^\s()&|^~!?:,{}]+)
  | (?P<net>[A-Za-z_][\w$\\./]*(?:\s*\[[^\]]*\])*)
  | (?P<op>\^~|~\^|>>|<<|&&|\|\||[()&|^~!?:])
  | (?P<brace>[{}])
  | (?P<comma>,)
  | (?P<ws>\s+)
""", re.X)


def tokenize(s: str):
    out, i = [], 0
    while i < len(s):
        m = TOKEN_RE.match(s, i)
        if not m:
            return None                      # 有无法识别的字符 → 放弃该表达式
        i = m.end()
        if m.lastgroup == "ws":
            continue
        out.append(("id" if m.lastgroup == "net" else m.lastgroup, m.group()))
    return out


class Expr:
    """布尔/位运算表达式 AST。op in {'&','|','^','^~','~','?','const','var'}"""
    __slots__ = ("op", "a", "b", "c", "name", "const")

    def __init__(self, op, a=None, b=None, c=None, name=None, const=None):
        self.op, self.a, self.b, self.c = op, a, b, c
        self.name, self.const = name, const

    def leaves(self, acc=None):
        acc = [] if acc is None else acc
        if self.op == "var":
            acc.append(self.name)
        elif self.op == "const":
            pass
        else:
            for ch in (self.a, self.b, self.c):
                if ch is not None:
                    ch.leaves(acc)
        return acc


class _P:
    """递归下降：ternary -> or -> and -> xor -> unary -> primary"""
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def eat(self, val=None):
        k, v = self.peek()
        if val is not None and v != val:
            raise ValueError(f"expect {val} got {v}")
        self.i += 1
        return v

    def parse(self):
        e = self.ternary()
        if self.i != len(self.t):
            raise ValueError("trailing tokens")
        return e

    def ternary(self):
        c = self.or_()
        if self.peek()[1] == "?":
            self.eat("?"); a = self.ternary(); self.eat(":"); b = self.ternary()
            return Expr("?", c, a, b)
        return c

    def or_(self):
        e = self.and_()
        while self.peek()[1] in ("|", "||"):
            self.eat(); e = Expr("|", e, self.and_())
        return e

    def and_(self):
        e = self.xor()
        while self.peek()[1] in ("&", "&&"):
            self.eat(); e = Expr("&", e, self.xor())
        return e

    def xor(self):
        e = self.unary()
        while self.peek()[1] in ("^", "^~", "~^"):
            op = self.eat(); e = Expr(op if op != "~^" else "^~", e, self.unary())
        return e

    def unary(self):
        if self.peek()[1] in ("~", "!"):
            self.eat(); return Expr("~", self.unary())
        return self.primary()

    def primary(self):
        k, v = self.peek()
        if v == "(":
            self.eat("("); e = self.ternary(); self.eat(")")
            return e
        if v == "{":                                  # 拼接：语义未知但**保留连通性**
            self.eat("{")
            parts = [self.ternary()]
            while self.peek()[1] == ",":
                self.eat(","); parts.append(self.ternary())
            self.eat("}")
            e = parts[0]
            for p in parts[1:]:
                e = Expr("cat", e, p)
            return e
        if k == "num":
            self.eat(); return Expr("const", const=v)
        if k in ("id", "esc"):
            self.eat(); return Expr("var", name=v)
        raise ValueError(f"bad primary {v!r}")


def parse_expr(s: str):
    """解析失败返回 None（调用方按"语义未知"记账，不要静默当 0）。"""
    toks = tokenize(s)
    if not toks:
        return None
    try:
        return _P(toks).parse()
    except Exception:
        return None


# --------------------------------------------------------------------------
# 4) 功能特征：算子级公式（信号概率 / SCOAP 可控性 / 布尔影响度）
# --------------------------------------------------------------------------
INF = 1e6          # 哨兵：不可达 / 不可控（只有"真不可达"才用它）
CAP = 1e5          # 有界算术上限：可达到但很深的路径封顶到 CAP，避免 INF 污染统计
CONST_BODY_RE = re.compile(r"'[bBdDhH]?([0-9a-fA-F_xXzZ]+)$")


def const_value(c: str) -> float:
    m = CONST_BODY_RE.search(c)
    if not m:
        return 0.5
    d = m.group(1).replace("_", "")
    if set(d) <= {"0"}:
        return 0.0
    if set(d) <= {"1"}:
        return 1.0
    return 0.5                     # x/z/多值 → 未知


def prob(e: Expr, pm: dict) -> float:
    """独立输入模型下的信号概率（PI 先验 0.5）。"""
    o = e.op
    if o == "const":
        return const_value(e.const)
    if o == "var":
        return pm.get(e.name, 0.5)
    if o == "~":
        return 1.0 - prob(e.a, pm)
    p1 = prob(e.a, pm)
    if e.b is None:
        return p1
    p2 = prob(e.b, pm)
    if o == "&":
        return p1 * p2
    if o == "|":
        return 1.0 - (1.0 - p1) * (1.0 - p2)
    if o == "^":
        return p1 + p2 - 2 * p1 * p2
    if o == "^~":
        return 1.0 - (p1 + p2 - 2 * p1 * p2)
    if o == "?":
        return p1 * p2 + (1.0 - p1) * prob(e.c, pm)
    return 0.5


def cc(e: Expr, cm: dict, want0: bool) -> float:
    """公开入口：**有界**（封顶 CAP），这样 INF 只会来自"真不可控"。
    内部递归仍走本函数，因此每一层都被压住，不会指数级放大。
    """
    return min(_cc_raw(e, cm, want0), CAP)


def _cc_raw(e: Expr, cm: dict, want0: bool) -> float:
    """SCOAP 式 0/1 可控性（PI/FF 输出 = 1）。"""
    o = e.op
    if o == "const":
        v = const_value(e.const)
        return {0.0: (0.0, INF), 1.0: (INF, 0.0)}.get(v, (INF, INF))[0 if want0 else 1]
    if o == "var":
        return cm.get(e.name, (1.0, 1.0))[0 if want0 else 1]
    if o == "~":
        return cc(e.a, cm, not want0)
    c0a, c1a = cc(e.a, cm, True), cc(e.a, cm, False)
    if e.b is None:
        return c0a if want0 else c1a
    c0b, c1b = cc(e.b, cm, True), cc(e.b, cm, False)
    if o == "&":
        return (min(c0a, c0b) + 1) if want0 else (c1a + c1b + 1)
    if o == "|":
        return (c0a + c0b + 1) if want0 else (min(c1a, c1b) + 1)
    if o == "^":
        return (min(c0a + c1b, c1a + c0b) + 1) if want0 else (min(c0a + c0b, c1a + c1b) + 1)
    if o == "^~":
        return cc(Expr("^", e.a, e.b), cm, not want0)
    if o == "?":
        c0c, c1c = cc(e.c, cm, True), cc(e.c, cm, False)
        return (min(c0a + c0b, c1a + c0c) + 1) if want0 else (min(c0a + c1b, c1a + c1c) + 1)
    return INF


def influence(e: Expr, pm: dict, ins) -> float:
    """Σ_i P(f|_{xi=0} ≠ f|_{xi=1})：局部相关性/布尔影响力的精确近似（独立模型下）。"""
    tot = 0.0
    for n in ins:
        p0 = prob(e, {**pm, n: 0.0})
        p1 = prob(e, {**pm, n: 1.0})
        tot += p0 * (1.0 - p1) + p1 * (1.0 - p0)
    return tot


FEATS = ["sp", "toggle_rate", "cc0", "cc1", "co", "influence_in", "fanin_support",
         "reach_po", "reach_dff", "depth", "hops_to_po", "n_inputs", "degree",
         "fanin_2hop", "fanout_2hop", "is_ff", "is_pi", "is_po",
         "op_and", "op_or", "op_xor", "op_not", "op_mux", "op_unknown",
         # ---- 局部 cut 功能签名（第三块）----
         "cut_n_leaves", "cut_sp", "cut_entropy", "cut_reliability",
         "cut_bd_sum", "cut_bd_max"]


def _ff_data_nets(g, ins_r, clk_re):
    """FF 的**数据端**网（排除时钟/复位/扫描控制端口）—— 这些才是"可观测点"。"""
    out = []
    pr = list(g.ports or [])
    for k, net in enumerate(ins_r):
        p = pr[k] if k < len(pr) else ""
        if clk_re.match(p or ""):
            continue
        out.append((p, net))
    return out


def circuit_features(nl, sem):
    """返回 (gates, rows, info)。rows[i] 是与 gates[i] 对应的特征字典。"""
    from collections import deque
    gates, alias, unknown = build_circuit(nl, sem)
    n = len(gates)
    if n == 0:
        return gates, [], {"n_gates": 0, "n_unknown_sem": unknown}

    def rs(nm):
        seen = set()
        while nm in alias and nm not in seen:
            seen.add(nm)
            nm = alias[nm]
        return nm

    drv = {}
    for gi, g in enumerate(gates):
        if g.out and g.out not in drv:
            drv[g.out] = gi
    ins_r = [[rs(x) for x in g.ins] for g in gates]
    pis = {rs(x) for x in nl.inputs}
    pos = {rs(x) for x in nl.outputs}
    fan = {}
    for gi, xs in enumerate(ins_r):
        for x in set(xs):
            fan.setdefault(x, []).append(gi)

    # ---- 拓扑序（Kahn）----
    # 关键：**FF 节点视为源**（它的 Q 与 D 无关）——否则"D 逻辑 ↔ Q"会形成假环，
    # 拓扑序失效 → 可控性/可观测性全部爆成 INF。
    deps = [[] if gates[gi].kind == "ff" else
            sorted({drv[x] for x in set(ins_r[gi]) if x in drv and drv[x] != gi})
            for gi in range(n)]
    indeg = [len(d) for d in deps]
    ch = [[] for _ in range(n)]
    for gi, ds in enumerate(deps):
        for d in ds:
            ch[d].append(gi)
    q = deque([i for i in range(n) if indeg[i] == 0])
    order = []
    while q:
        i = q.popleft()
        order.append(i)
        for j in ch[i]:
            indeg[j] -= 1
            if indeg[j] == 0:
                q.append(j)
    if len(order) < n:                       # 有环：把剩下的按原序补上（记到 info）
        order += [i for i in range(n) if i not in set(order)]
    back = list(reversed(order))

    pm, cm, depth, sup = {}, {}, {}, {}
    for gi in order:
        g = gates[gi]
        ins = ins_r[gi]
        d = max([depth.get(x, 0) for x in ins], default=0)
        depth[g.out] = 0 if g.kind in ("ff",) else d + 1
        s = set()
        for x in ins:
            if x in sup:
                s |= sup[x]
            elif x in pis or x in drv and gates[drv[x]].kind == "ff":
                s.add(x)
        sup[g.out] = s if len(s) < 4096 else set(list(s)[:4096])
        if g.expr is not None:
            pm[g.out] = prob(g.expr, pm)
            cm[g.out] = (cc(g.expr, cm, True), cc(g.expr, cm, False))
        else:
            pm.setdefault(g.out, 0.5)
            cm.setdefault(g.out, (1.0, 1.0))

    # ---- 可观测性播种：**必须在反向遍历之前**把"观测点"全部种上 ----
    # 教训：原先是在反向遍历里、处理到 FF 节点时才给它数据端种 co=0；但 FF 现在
    # 被视为无依赖（为了打破 D↔Q 假环），它在拓扑序里可能排在最前 ⇒ 反向遍历时
    # 它被**最后**处理，播种发生在整个扇入锥算完之后 → 59~77% 的网假性 INF。
    CLK_RE = re.compile(r"(?i)^(ck|clk|clock|rn|sn|rst|reset|se|si|test|tm|te|scan)")
    co2 = {p: 0.0 for p in pos}
    for gi, g in enumerate(gates):
        if g.kind != "ff":
            continue
        for (port, net) in _ff_data_nets(g, ins_r[gi], CLK_RE):
            co2.setdefault(net, 0.0)
    hops = {p: 0 for p in pos}
    rpo = {p: {p} for p in pos}
    rdff = {p: set() for p in pos}
    for gi in back:
        g = gates[gi]
        o = g.out
        co_o = co2.get(o, INF)
        h_o = hops.get(o, INF)
        rp = rpo.get(o, set())
        rd = rdff.get(o, set())
        if g.kind == "ff":
            for x in ins_r[gi]:
                hops[x] = min(hops.get(x, INF), h_o + 1)
                rpo[x] = rpo.get(x, set()) | rp
                rdff[x] = rdff.get(x, set()) | {o} | rd
            continue
        xs = ins_r[gi]
        for k, x in enumerate(xs):
            others = [y for j, y in enumerate(xs) if j != k]
            if g.cell == "?" and len(xs) == 3:
                s_ = 1.0 if k == 0 else 0.0
                sens = (min(cm.get(xs[1], (1, 1))[0] + cm.get(xs[2], (1, 1))[1],
                            cm.get(xs[1], (1, 1))[1] + cm.get(xs[2], (1, 1))[0]) + 1) \
                    if k == 0 else (cm.get(xs[0], (1, 1))[0 if k == 1 else 1] + 1)
                sens = min(sens, INF)
            elif g.cell == "&":
                sens = cm.get(others[0], (1, 1))[1] + 1 if others else 1
            elif g.cell == "|":
                sens = cm.get(others[0], (1, 1))[0] + 1 if others else 1
            elif g.cell in ("^", "^~"):
                c = cm.get(others[0], (1, 1)) if others else (1, 1)
                sens = min(c[0], c[1]) + 1
            else:
                sens = 1.0
            if co_o < INF / 2:                      # 不可观测的门不能"传出"可观测性
                co2[x] = min(co2.get(x, INF), min(co_o + sens, CAP))
            hops[x] = min(hops.get(x, INF), h_o + 1)
            rpo[x] = rpo.get(x, set()) | rp
            rdff[x] = rdff.get(x, set()) | rd

    cuts = cut_signatures(gates, ins_r, drv)
    rows = []
    for gi, g in enumerate(gates):
        o, ins = g.out, ins_r[gi]
        fin2, fout2 = set(), set()
        for x in ins:
            fin2 |= set(ins_r[drv[x]]) if x in drv else set()
        for j in fan.get(o, []):
            fout2 |= set(ins_r[j])
            for m in gates[j].out,:
                fout2 |= {m}
        p = pm.get(o, 0.5)
        c0, c1 = cm.get(o, (1.0, 1.0))
        cd = g.cell if isinstance(g.cell, str) else ""
        rows.append({
            "net": o, "kind": g.kind, "cell": cd, "sem_ok": g.sem_ok,
            "n_inputs": float(len(ins)),
            "sp": p, "toggle_rate": 2 * p * (1 - p),
            "cc0": min(c0, INF), "cc1": min(c1, INF),
            "co": min(co2.get(o, INF), INF),
            "influence_in": influence(g.expr, pm, ins) if g.expr is not None else 0.0,
            "fanin_support": float(len(sup.get(o, ()))),
            "reach_po": float(len(rpo.get(o, ()))), "reach_dff": float(len(rdff.get(o, ()))),
            "depth": float(depth.get(o, 1)),
            "hops_to_po": float(min(hops.get(o, INF), 1e3)),
            "degree": float(len(ins) + len(fan.get(o, ()))),
            "fanin_2hop": float(len(fin2)), "fanout_2hop": float(len(fout2)),
            "is_ff": float(g.kind == "ff"), "is_pi": float(rs(o) in pis),
            "is_po": float(rs(o) in pos),
            "op_and": float(cd == "&"), "op_or": float(cd == "|"),
            "op_xor": float(cd in ("^", "^~")), "op_not": float(cd == "~"),
            "op_mux": float(cd == "?"), "op_cat": float(cd == "cat"),
            "op_unknown": float((not g.sem_ok) or cd in ("cat", "assign")),
            **cuts[gi],
        })
    info = {"n_gates": n, "n_unknown_sem": unknown,
            "n_ff": sum(1 for g in gates if g.kind == "ff")}
    return gates, rows, info


# --------------------------------------------------------------------------
# 5) 局部 cut 功能签名（第三块："局部 cut 功能签名"）
#    对每个门往回取**有界 fan-in cut**（最多 CUT_K 个叶子），在 2^CUT_K 个输入组合上
#    用**精确门语义**求值 → 得到该门的局部功能真值表，再投影成一小组标量特征。
#    这样功能比较是「按 cut 固定输入输出」的，而不是对整个 region 一锅平均。
# --------------------------------------------------------------------------
CUT_K = 4                      # cut 叶子数上限（2^4 = 16 个输入组合）
CUT_EPS = 0.05                 # reliability 的单叶子出错率
_REL_W = {}


def _popcount(x: int) -> int:
    return bin(x).count("1")


def _rel_weights(K: int = CUT_K, eps: float = CUT_EPS):
    """reliability 的转移权重：w[d] = eps^d (1-eps)^(K-d)。按 K 缓存。"""
    if K not in _REL_W:
        _REL_W[K] = [eps ** d * (1 - eps) ** (K - d) for d in range(K + 1)]
    return _REL_W[K]


def _permute(tt: int, s: int, K: int) -> int:
    """真值表按"翻转第 s 个叶子"重排：下标 j → j ^ (1<<s)。"""
    out = 0
    for j in range(1 << K):
        if (tt >> j) & 1:
            out |= 1 << (j ^ (1 << s))
    return out


def _cut_one(gi, gates, ins_r, drv, K=CUT_K):
    """单个门的局部 cut 签名（返回标量特征字典）。

    注意：K 只是**反向展开的预算上限**；实际叶子数 n_leaf 可能比 K 多一点点
    （一个多输入门整块展开），此时按 2^{n_leaf} 求值即可 —— 不要因为超预算就整条丢弃。
    """
    leaves, cone, state = [], [], {}

    def visit(i):
        if i in state:
            return
        if gates[i].kind in ("ff", "buf", "unknown") or not ins_r[i]:
            state[i] = "leaf"
            if gates[i].out not in leaves:
                leaves.append(gates[i].out)
            return
        # 预估展开这个门会新增几个叶子；超预算就整门当叶子（保证 n_leaf ≤ K）
        cand = []
        for x in ins_r[i]:
            d = drv.get(x)
            nm = x if (d is None or gates[d].kind in ("ff", "buf", "unknown")) else gates[d].out
            if nm not in leaves and nm not in cand:
                cand.append(nm)
        if len(leaves) + len(cand) > K:
            state[i] = "leaf"
            if gates[i].out not in leaves:
                leaves.append(gates[i].out)
            return
        for x in ins_r[i]:
            d = drv.get(x)
            if d is None or gates[d].kind in ("ff", "buf", "unknown"):
                if x not in leaves:
                    leaves.append(x)
            else:
                visit(d)
        state[i] = "node"
        cone.append(i)

    visit(gi)
    n_leaf = len(leaves)
    if n_leaf == 0 or n_leaf > 6:      # 位向量宽度=2^{n_leaf}，超过 6 会爆掉且无意义
        return {}
    K2 = 1 << n_leaf
    val = {}
    for slot, net in enumerate(leaves):
        v = 0
        for j in range(K2):
            if (j >> slot) & 1:
                v |= 1 << j
        val[net] = v
    for i in cone:
        xs = [val.get(x, 0) for x in ins_r[i]]
        o = gates[i].cell
        if o == "~":
            t = (~xs[0]) & (K2 - 1)
        elif o == "&":
            t = (xs[0] & xs[1]) if len(xs) > 1 else xs[0]
        elif o == "|":
            t = (xs[0] | xs[1]) if len(xs) > 1 else xs[0]
        elif o == "^":
            t = (xs[0] ^ xs[1]) if len(xs) > 1 else xs[0]
        elif o == "^~":
            t = (~(xs[0] ^ xs[1])) & (K2 - 1)
        elif o == "?" and len(xs) == 3:
            t = (xs[0] & xs[1]) | (((~xs[0]) & (K2 - 1)) & xs[2])
        else:
            t = xs[0] if xs else 0
        val[gates[i].out] = t
    tt = val.get(gates[gi].out, 0)
    p = _popcount(tt) / K2
    ent = 0.0 if p in (0.0, 1.0) else -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
    w = _rel_weights(n_leaf)
    rel = 0.0
    for j in range(K2):
        # 该输入组合下"敏感"的叶子数（翻转它会改变输出）
        ns = sum(1 for s in range(n_leaf)
                 if ((tt >> j) & 1) != ((tt >> (j ^ (1 << s))) & 1))
        # **单故障可靠性**：要么没有叶子翻转，要么恰好一个（且在 j 处敏感的）翻转
        rel += (w[0] + ns * (CUT_EPS * (1 - CUT_EPS) ** max(n_leaf - 1, 0))) / K2
    bds = [_popcount(tt ^ _permute(tt, s, n_leaf)) / K2 for s in range(n_leaf)]
    return {"cut_n_leaves": float(n_leaf), "cut_sp": float(p), "cut_entropy": float(ent),
            "cut_reliability": float(rel),
            "cut_bd_sum": float(sum(bds)), "cut_bd_max": float(max(bds) if bds else 0.0)}


def cut_signatures(gates, ins_r, drv):
    """对所有门算一遍局部 cut 签名（返回与 gates 对齐的 dict 列表）。"""
    return [_cut_one(gi, gates, ins_r, drv) for gi in range(len(gates))]


def subst(e: Expr, mp: dict) -> Expr:
    """把公式里的端口名替换成网名。"""
    if e.op == "var":
        return Expr("var", name=mp.get(e.name, e.name))
    if e.op == "const":
        return e
    return Expr(e.op, subst(e.a, mp) if e.a is not None else None,
                subst(e.b, mp) if e.b is not None else None,
                subst(e.c, mp) if e.c is not None else None)


# --------------------------------------------------------------------------
# 2) 库语义：从 verilog_lib.v 抽「每单元的输出端口 + 公式 + 是否时序」
# --------------------------------------------------------------------------
MOD_RE = re.compile(r"^\s*module\s+(\\?\S+)\s*(?:#\s*\([^)]*\)\s*)?\((.*?)\)\s*;", re.S | re.M)
DECL_RE = re.compile(r"^\s*(input|output|inout)\s+(?:reg\s+|wire\s+)?(?:\[[^\]]*\]\s*)?([^;]+);", re.M)


def load_cell_semantics(lib_path: Path) -> dict:
    text = Path(lib_path).read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    sem: dict = {}
    for m in MOD_RE.finditer(text):
        name = m.group(1).lstrip("\\")
        body_start = m.end()
        end = text.find("endmodule", body_start)
        body = text[body_start:end if end > 0 else len(text)]
        indir, outdir = [], []
        for d in DECL_RE.finditer(body):
            kind, names = d.group(1), d.group(2)
            ns = [x.strip().lstrip("\\") for x in names.replace("\n", " ").split(",") if x.strip()]
            (indir if kind == "input" else outdir).extend(ns)
        exprs = {}
        for a in re.finditer(r"assign\s+([^\s=]+)\s*=\s*([^;]+);", body):
            e = parse_expr(a.group(2))
            if e is not None:
                exprs[a.group(1).lstrip("\\")] = e
        sem[name] = {"ins": indir, "outs": outdir, "exprs": exprs,
                     # 有时钟沿 ⇒ 时序单元（它的 Q 是状态，不是组合输出）
                     "seq": bool(re.search(r"always\s*@\s*\(\s*posedge", body))}
    return sem


# --------------------------------------------------------------------------
# 3) 构图：节点 = "一个输出网"（库单元 / 表达式算子 / FF / 输入端口）
# --------------------------------------------------------------------------
class Gate:
    __slots__ = ("name", "kind", "cell", "out", "ins", "expr", "seq", "sem_ok", "ports")

    def __init__(self, name, kind, cell, out, ins, expr=None, seq=False, sem_ok=True,
                 ports=None):
        self.name, self.kind, self.cell = name, kind, cell
        self.out, self.ins = out, ins
        self.expr, self.seq, self.sem_ok = expr, seq, sem_ok
        self.ports = ports            # 与 ins 对齐的端口名（用于区分 D / CK / SE）


def _decompose(e: Expr, lhs: str, gates: list, tag: str, cnt=None):
    """把表达式拆成"每算子一个节点"。返回 (代表该表达式的网名, 根节点下标或 None)。

    统一成 1/2 输入算子后：原网表（复杂库单元）和 yosys 网表（assign 表达式）
    的**节点粒度一致**，特征才可比。
    """
    cnt = cnt if cnt is not None else [0]
    if e.op in ("var", "const"):
        return (e.name if e.op == "var" else "1'b0"), None
    a, _ai = _decompose(e.a, lhs, gates, tag, cnt)
    b, _bi = (_decompose(e.b, lhs, gates, tag, cnt) if e.b is not None else (None, None))
    c, _ci = (_decompose(e.c, lhs, gates, tag, cnt) if e.c is not None else (None, None))
    cnt[0] += 1
    out = f"{lhs}#{cnt[0]}"
    gates.append(Gate(f"{tag}#{cnt[0]}", "op", e.op, out,
                      [x for x in (a, b, c) if x], expr=e, seq=False))
    return out, len(gates) - 1


def build_circuit(nl, sem: dict):
    """统一分解形式。返回 (gates, alias, n_unknown_sem)。

    节点类型：`op`(1/2 输入算子) / `ff`(时序输出) / `buf`(未知语义单元的输出) / `unknown`。
    每个节点的 `cell` 保留**来源**（算子符号，或原库单元名），便于回溯。
    """
    gates: list = []
    alias: dict = {}
    unknown = 0
    for i in nl.insts:
        s = sem.get(i.gate)
        portnet = {p: n for p, n in i.conns}
        outs = nl.outs(i)
        in_ports = [p for p, _n in nl.ins(i)]
        in_nets = [n for _p, n in nl.ins(i)]
        if s is None:
            unknown += 1
            for p, n in outs:
                gates.append(Gate(f"{i.name}.{p}", "unknown", i.gate, n, in_nets,
                                  expr=None, seq=False, sem_ok=False, ports=in_ports))
            continue
        for p, n in outs:
            e = s["exprs"].get(p)
            if e is None:
                gates.append(Gate(f"{i.name}.{p}", "ff" if s["seq"] else "buf",
                                  i.gate, n, in_nets, expr=None, seq=s["seq"], sem_ok=True,
                                  ports=in_ports))
            else:
                ee = subst(e, portnet)
                ret, root = _decompose(ee, n, gates, f"{i.name}.{p}")
                if root is not None:
                    gates[root].cell = f"{i.gate}:{p}"     # 标记来源单元
                if ret and ret != n:
                    alias[n] = ret            # 真实网名 → 表达式根网名（否则扇出断开）
    for lhs, rhs in nl.assigns:
        r = rhs.strip()
        if re.fullmatch(r"[\w\\/$\[\]:.]+", r):            # 纯别名
            alias[lhs] = r
            continue
        e = parse_expr(r)
        if e is None:
            unknown += 1
            gates.append(Gate("assign:" + lhs, "unknown", "assign", lhs, [],
                              None, False, False))
            continue
        ret, _root = _decompose(e, lhs, gates, "assign:" + lhs)
        if ret and ret != lhs:
            alias[lhs] = ret              # 同上：把 lhs 接回表达式根
    return gates, alias, unknown
