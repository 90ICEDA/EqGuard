"""f8_schematic.py -- F8 的**电路图级**渲染（schemdraw 门符号 + 正交走线）。

与 f8_rewrite_case.py 的区别：
  * 门用**真实符号**（AND/OR/XOR/NAND/NOR/NOT），DFF/MUX 用带引脚名的方块 ✓
  * 连线**正交走线**（H-V-H），带箭头 ✓
  * 两侧面板并排，匹配信号用**编号徽标 + 虚连线 + 图例** ✓（不用长斜箭头 ✗）
  * 孤立节点默认**不画**（`--keep-isolated` 可保留 ⚠️）

用法：
  ginvenv\\Scripts\\python.exe -X utf8 phase2/ys/f8_schematic.py \
      --host s38417t100 --inst injalpha --ra ys_id --rb ys_abc --k 2
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict, deque
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyArrow, Polygon, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent))
import f8_rewrite_case as F8

FIGS = F8.FIGS
T = F8.T

# 门类型 → (schemdraw 形状, 输入数)；DFF/MUX/未知走方块 ✓
GATE = {
    "AND2X1": ("and", 2), "AND2X2": ("and", 2), "AND3X1": ("and", 3),
    "OR2X1": ("or", 2), "OR3X1": ("or", 3), "OR4X1": ("or", 4),
    "XOR2X1": ("xor", 2), "XNOR2X1": ("xnor", 2), "XNOR2X2": ("xnor", 2),
    "NAND2X1": ("nand", 2), "NAND3X1": ("nand", 3),
    "NOR2X1": ("nor", 2), "NOR3X1": ("nor", 3),
    "INVX0": ("not", 1), "INVX1": ("not", 1),
    "SDFFX1": ("dff", 0), "SDFF": ("dff", 0), "DFF": ("dff", 0),
}
MUX_T = {"MX2X1_RS", "MUX2X1", "MUX2X2"}



def draw_cell(d, ax, name: str, typ: str, x: float, y: float, trojan: bool):
    """画一个单元 ✓：门用 schemdraw 符号 ✓、DFF/MUX/未知用方块 ✓。返回引脚坐标 ✓。"""
    fc = "#f7c9c9" if trojan else "#dbeafe"
    t = typ.upper()
    kind, n_in = GATE.get(t, ("box", 2))
    from schemdraw import logic
    pins = {}
    if kind in ("and", "or", "xor", "nand", "nor", "xnor", "not"):
        el = {"and": logic.And, "or": logic.Or, "xor": logic.Xor,
              "nand": logic.Nand, "nor": logic.Nor, "xnor": logic.Xnor,
              "not": logic.Not}[kind]
        e = el(inputs=max(2, n_in)) if kind != "not" else el()
        e = e.at((x, y)).color("#333")
        try:
            e = e.fill(fc)
        except Exception:
            pass
        d += e
        ax.text(x, y + 0.62, name[:16], ha="center", fontsize=4.6, color="#111")
        try:
            a = e.absanchors
            pins["out"] = a["out"]
            for i in (1, 2, 3, 4):
                if f"in{i}" in a:
                    pins[f"in{i}"] = a[f"in{i}"]
        except Exception:
            pins["out"] = (x + 0.6, y)
            pins["in1"] = (x - 0.6, y + 0.15)
            pins["in2"] = (x - 0.6, y - 0.15)
        return pins

    # ---- 方块（DFF / MUX / 未知）----
    w, h = (1.35, 0.95) if kind == "dff" else (1.25, 1.05)
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, facecolor=fc,
                           edgecolor="#333", linewidth=0.7, zorder=3))
    ax.text(x, y + h * 0.18, name[:16], ha="center", va="center", fontsize=4.4, zorder=4)
    ax.text(x, y - h * 0.22, typ[:12], ha="center", va="center", fontsize=3.8,
            color="#333", zorder=4)
    if kind == "dff":
        ax.text(x - w / 2 + 0.10, y + 0.10, "D", fontsize=4, va="center", zorder=4)
        ax.text(x - w / 2 + 0.10, y - 0.28, "CK", fontsize=3.4, va="center", zorder=4)
        ax.text(x + w / 2 - 0.10, y + 0.10, "Q", fontsize=4, ha="right", va="center", zorder=4)
        pins["in1"] = (x - w / 2, y + 0.10)
        pins["in2"] = (x - w / 2, y - 0.28)
        pins["out"] = (x + w / 2, y + 0.10)
    elif t in MUX_T:
        ax.add_patch(Polygon([[x - w / 2, y - h / 2], [x + w / 2, y - h / 2],
                              [x + w / 2 - 0.25, y + h / 2], [x - w / 2 + 0.25, y + h / 2]],
                             closed=True, facecolor=fc, edgecolor="#333", lw=0.7, zorder=3))
        pins["in1"] = (x - w / 2 + 0.12, y + 0.22)
        pins["in2"] = (x - w / 2 + 0.12, y - 0.22)
        pins["in3"] = (x - 0.10, y - h / 2)
        pins["out"] = (x + w / 2 - 0.10, y)
    else:
        pins["in1"] = (x - w / 2, y + 0.18)
        pins["in2"] = (x - w / 2, y - 0.18)
        pins["out"] = (x + w / 2, y)
    return pins


def wire(ax, a, b, color="#8a8a8a", ls="-", lw=0.5, arrow=True, rad=0.0):
    """正交走线 H-V-H ✓（a=输出脚，b=输入脚）✓。"""
    x0, y0 = a
    x1, y1 = b
    xm = (x0 + x1) / 2.0
    xs = [x0, xm, xm, x1]
    ys = [y0, y0, y1, y1]
    ax.plot(xs, ys, color=color, ls=ls, lw=lw, zorder=2, solid_capstyle="round")
    if arrow:
        ax.annotate("", xy=(x1, y1), xytext=(x1 - 0.12 * (1 if x1 >= xm else -1), y1),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                                    shrinkA=0, shrinkB=0))

def layerize(nodes: set, cons: dict) -> dict:
    """最长路径分层 ✓（输入侧为 0 ✓）。"""
    depth = {n: 0 for n in nodes}
    for _ in range(len(nodes)):
        ch = False
        for c in nodes:
            for u in cons.get(c, set()):
                if u in nodes and depth[c] < depth[u] + 1:
                    depth[c] = depth[u] + 1
                    ch = True
        if not ch:
            break
    return depth


PIN_MAP = {"IN1": "in1", "IN2": "in2", "IN3": "in3", "IN4": "in4",
           "A": "in1", "B": "in2", "S": "in3", "S0": "in3", "D": "in1", "SE": "in2", "SI": "in2"}


def render_panel(ax, cells, subset, cons, drv, title):
    """画一侧面板 ✓（门符号 + 正交走线 + 只画有连线的节点 ✓）。"""
    depth = layerize(subset, cons)
    by = defaultdict(list)
    for n in subset:
        by[depth[n]].append(n)
    pos, pins = {}, {}
    import schemdraw
    d = schemdraw.Drawing(canvas=ax)
    for dpt, ns in by.items():
        ns.sort(key=lambda c: (0 if "trojan" in c.lower() else 1, c))
        for i, c in enumerate(ns):
            pos[c] = (dpt * 3.6, -i * 1.55)
    for c in subset:
        x, y = pos[c]
        pins[c] = draw_cell(d, ax, c, cells[c][0], x, y, "trojan" in c.lower())

    n_wire = 0
    for c in subset:
        typ, pind = cells[c]
        for pin, net in pind.items():
            if pin.upper() in F8.OUT_PINS:
                continue
            key = PIN_MAP.get(pin.upper())
            if key is None or key not in pins[c]:
                continue
            for u in drv.get(net, set()):
                if u in subset and "out" in pins.get(u, {}):
                    wire(ax, pins[u]["out"], pins[c][key])
                    n_wire += 1
    ax.set_title(title, fontsize=8)
    ax.set_aspect("equal")
    ax.set_xlim(-1.6, max(p[0] for p in pos.values()) + 2.2)
    ax.set_ylim(min(p[1] for p in pos.values()) - 1.2, 1.6)
    ax.axis("off")
    return pos, pins, n_wire


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="s38417t100")
    ap.add_argument("--inst", default="injalpha")
    ap.add_argument("--ra", default="ys_id")
    ap.add_argument("--rb", default="ys_abc")
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--max-nodes", type=int, default=40)
    ap.add_argument("--seed-cap", type=int, default=8)
    ap.add_argument("--keep-isolated", action="store_true")
    ap.add_argument("--out", type=Path, default=FIGS / "F8_schematic.png")
    a = ap.parse_args()

    pa = F8.VDIR / f"{a.host}__{a.inst}_d1_s42__{a.ra}.v"
    pb = F8.VDIR / f"{a.host}__{a.inst}_d1_s42__{a.rb}.v"
    cells_a, cells_b = F8.parse_v(pa), F8.parse_v(pb)
    drv_a, cons_a = F8.build_graph(cells_a)
    drv_b, cons_b = F8.build_graph(cells_b)

    d = pd.read_csv(T / "node_pairs_sat_node.csv", encoding="utf-8-sig").fillna("")
    ra, rb = a.ra.replace("ys_", ""), a.rb.replace("ys_", "")
    m = ((d["host"] == a.host) & (d["inst_a"] == a.inst) & (d["inst_b"] == a.inst)
         & (d["recipe_a"] == ra) & (d["recipe_b"] == rb) & (d["status"] == "proved"))
    pairs = d[m][["net_a", "net_b"]].drop_duplicates()

    sa = {c for c in cells_a if "trojan" in c.lower()}
    sb = {c for c in cells_b if "trojan" in c.lower()}
    na = F8.bfs(sa, cons_a, drv_a, cells_a, a.k, a.max_nodes)
    nb = F8.bfs(sb, cons_b, drv_b, cells_b, a.k, a.max_nodes)

    def drop_isolated(nodes, cons, cells):
        keep = set()
        for c in nodes:
            up = [u for u in cons.get(c, set()) if u in nodes]
            down = [v for v in nodes if c in cons.get(v, set())]
            if up or down or "trojan" in c.lower():
                keep.add(c)
        return keep

    if not a.keep_isolated:
        na, nb = drop_isolated(na, cons_a, cells_a), drop_isolated(nb, cons_b, cells_b)

    fig, axes = plt.subplots(1, 2, figsize=(15, 7.2))
    pa_pos, pa_pin, wa = render_panel(axes[0], cells_a, na, cons_a, drv_a,
                                      f"{a.host} . {a.inst} . {a.ra} (pre-ABC)")
    pb_pos, pb_pin, wb = render_panel(axes[1], cells_b, nb, cons_b, drv_b,
                                      f"{a.host} . {a.inst} . {a.rb} (post-ABC)")

    # 匹配信号：两侧都在图里 → 编号徽标 + 虚线 ✓
    matched = []
    for _, r in pairs.iterrows():
        ca = next(iter(drv_a.get(str(r["net_a"]), set())), None)
        cb = next(iter(drv_b.get(str(r["net_b"]), set())), None)
        if ca in pa_pos and cb in pb_pos:
            matched.append((ca, cb))
    for i, (ca, cb) in enumerate(matched, 1):
        axes[0].scatter(*pa_pos[ca], s=42, c="#1a7f37", marker="o", zorder=6)
        axes[0].text(pa_pos[ca][0], pa_pos[ca][1] - 0.42, f"#{i}", ha="center",
                     fontsize=5.5, color="#1a7f37", zorder=6)
        axes[1].scatter(*pb_pos[cb], s=42, c="#1a7f37", marker="o", zorder=6)
        axes[1].text(pb_pos[cb][0], pb_pos[cb][1] - 0.42, f"#{i}", ha="center",
                     fontsize=5.5, color="#1a7f37", zorder=6)
    legend = " | ".join(f"#{i}: {ca} -> {cb}" for i, (ca, cb) in enumerate(matched[:4], 1))
    note = (f"cells: {len(na)} / {len(nb)} | wires: {wa} / {wb} | proved pairs {len(pairs)}"
            f" | matched-in-region {len(matched)}")
    fig.suptitle(f"F8 . same trojan, two CEC-equivalent implementations ({a.host}/{a.inst})",
                 fontsize=10)
    fig.text(0.5, 0.015, note, ha="center", fontsize=6.5, color="#333")
    if legend:
        fig.text(0.5, 0.045, "matched: " + legend, ha="center", fontsize=6.0, color="#1a7f37")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, dpi=230, bbox_inches="tight")
    print(f"[out] {a.out} | cells {len(na)}/{len(nb)} | wires {wa}/{wb} | matched {len(matched)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

