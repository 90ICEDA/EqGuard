"""f8_rewrite_case.py —— F8：同一木马在两种 CEC 等价实现间的门级重写图（真实网表）。

  - 取该 spec 的 proved 节点对（node_pairs_sat_node.csv）
  - 解析两侧 .v（单元类型 + 引脚连线），从"木马种子单元"做 k 跳 BFS
  - 双栏子图：栏内真实门级连线，跨栏箭头 = SAT 已证对应信号
  - 落盘 figs/F8_rewrite_case.png + tables/F8_nodes.csv + tables/F8_pairs.csv

用法：
  ginvenv\\Scripts\\python.exe -X utf8 phase2/ys/f8_rewrite_case.py --host s38417t100 --inst injalpha --ra ys_id --rb ys_abc --k 2 --max-nodes 40
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import math
import re
from collections import defaultdict, deque
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

ROOT = Path(_eqguard_path(''))
BASE = ROOT / "10.15/06_统一评测协议/N4_三向泛化"
T = BASE / "tables"
FIGS = ROOT / "10.15/07_论文图表/figs"
VDIR = ROOT / "generate_trans/folds/hosts_bt31/trans"

INST_RE = re.compile(r"^\s*([A-Za-z_$][\w$]*)\s+(\\?[^\s(]+)\s*\((.*)\)\s*;\s*$")
PORT_RE = re.compile(r"\.(\w+)\s*\(\s*([^)]*?)\s*\)")
KW = {"module", "wire", "input", "output", "inout", "assign", "reg", "parameter",
      "localparam", "endmodule", "always", "initial", "supply0", "supply1", "tri"}
OUT_PINS = {"Q", "QN", "Y", "Z", "X", "CO", "S", "O", "ON"}


def parse_v(p: Path) -> dict:
    out = {}
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = INST_RE.match(ln.strip())
        if not m:
            continue
        typ, inst, ports = m.groups()
        if typ in KW:
            continue
        pins = {}
        for pin, net in PORT_RE.findall(ports):
            net = net.strip().lstrip("\\")
            if net:
                pins[pin] = net
        out[inst.lstrip("\\")] = (typ, pins)
    return out


def build_graph(cells: dict):
    drv = defaultdict(set)
    for c, (typ, pins) in cells.items():
        for pin, net in pins.items():
            if pin.upper() in OUT_PINS:
                drv[net].add(c)
    cons = {}
    for c, (typ, pins) in cells.items():
        up = set()
        for pin, net in pins.items():
            if pin.upper() not in OUT_PINS:
                up |= drv.get(net, set())
        cons[c] = up
    return drv, cons

def bfs(seed: set, cons: dict, drv: dict, cells: dict, k: int, cap: int) -> set:
    seen = set(seed)
    q = deque((s, 0) for s in seed)
    while q:
        c, d = q.popleft()
        if d >= k or len(seen) >= cap:
            continue
        nbrs = set(cons.get(c, set()))
        for pin, net in cells[c][1].items():
            if pin.upper() in OUT_PINS:
                nbrs |= drv.get(net, set())
        for n in nbrs:
            if n not in seen and len(seen) < cap:
                seen.add(n)
                q.append((n, d + 1))
    return seen


def layout(nodes: list, cons: dict, cols: int = 9) -> dict:
    """层级 + **网格换行** ✓：同层节点按 cols 折行，避免一条长排被压扁 ✗。"""
    if not nodes:
        return {}
    indeg = {n: len(cons.get(n, set())) for n in nodes}
    start = min(nodes, key=lambda n: (indeg[n], n))
    depth = {n: 10 ** 6 for n in nodes}
    depth[start] = 0
    q = deque([start])
    while q:
        c = q.popleft()
        for n in sorted(cons.get(c, set())):
            if n in depth and depth[n] > depth[c] + 1:
                depth[n] = depth[c] + 1
                q.append(n)
    mx = max(depth.values())
    for n in nodes:
        if depth[n] > 10 ** 5:
            depth[n] = mx + 1
    lay = defaultdict(list)
    for n in nodes:
        lay[depth[n]].append(n)
    pos = {}
    row = 0
    for d in sorted(lay):
        ns = sorted(lay[d])
        for i, n in enumerate(ns):
            r, c = divmod(i, cols)
            pos[n] = (c * 1.45, -(row + r) * 0.72)
        row += max(1, math.ceil(len(ns) / cols)) + 0.35
    return pos


def dot_pos(nodes: list, edges: list):
    """用 **graphviz dot** 算坐标 ✓（LR 分层 + 交叉最小化 ✓，比手写 BFS 排布干净 ✓）。

    返回 `{node: (x, y, w, h)}`；失败返回 `None`（调用方回退到手写布局 ✓）。
    """
    import subprocess
    if not nodes:
        return None
    idx = {n: f"n{i}" for i, n in enumerate(nodes)}
    lines = ["digraph G {", "rankdir=LR;", "nodesep=0.30;", "ranksep=0.70;",
             "splines=ortho;",                      # 正交走线 ✓（更像电路图 ✓）
             "node [shape=box, fontsize=8, width=1.45, height=0.42, fixedsize=true];",
             "edge [arrowsize=0.5];"]
    for n in nodes:
        lines.append(f'{idx[n]} [label="{n}"];')
    for u, v in edges:
        if u in idx and v in idx:
            lines.append(f"{idx[u]} -> {idx[v]};")
    lines.append("}")
    try:
        r = subprocess.run(["wsl", "-e", "bash", "-lc", "dot -Tplain"],
                           input="\n".join(lines), capture_output=True, text=True,
                           encoding="utf-8", timeout=90)
        out = r.stdout or ""
    except Exception:
        return None
    inv = {v: k for k, v in idx.items()}
    pos = {}
    for ln in out.splitlines():
        if not ln.startswith("node "):
            continue
        p = ln.split()
        if len(p) < 5:
            continue
        nid = p[1]
        if nid not in inv:
            continue
        try:
            x, y, w, h = float(p[2]), float(p[3]), float(p[4]), float(p[5])
        except Exception:
            continue
        pos[inv[nid]] = (x, -y, max(0.45, w), max(0.22, h))   # 翻 y ✓
    return pos or None


def draw_panel_dot(ax, pos, cells, cons, title):
    """按 dot 坐标画框/边 ✓（框尺寸取 dot 给的 w/h ✓，文字按框宽自适应 ✓）。"""
    for c, (x, y, w, h) in pos.items():
        typ = cells[c][0]
        fc = "#f6c6c6" if ("trojan" in c.lower()) else "#d7e8f7"
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, facecolor=fc,
                               edgecolor="#444", linewidth=0.55, zorder=3))
        fs = 5.2 if w > 0.62 else 4.4
        ax.text(x, y + 0.035, c[:16], ha="center", va="center", fontsize=fs, zorder=4)
        ax.text(x, y - 0.06, typ[:14], ha="center", va="center", fontsize=fs - 0.6,
                color="#333", zorder=4)
    for c, ups in cons.items():
        for u in ups:
            if u in pos and c in pos:
                ax.plot([pos[u][0], pos[c][0]], [pos[u][1], pos[c][1]],
                        color="#aaa", lw=0.35, zorder=1)
    ax.set_title(title, fontsize=8)
    xs = [v[0] for v in pos.values()]
    ys = [v[1] for v in pos.values()]
    ax.set_xlim(min(xs) - 0.8, max(xs) + 0.8)
    ax.set_ylim(min(ys) - 0.6, max(ys) + 0.6)
    ax.axis("off")


def draw_panel(ax, nodes, pos, cells, cons, title):
    for c in nodes:
        x, y = pos[c]
        typ = cells[c][0]
        fc = "#f6c6c6" if ("trojan" in c.lower()) else "#d7e8f7"
        ax.add_patch(Rectangle((x - 0.60, y - 0.22), 1.20, 0.44, facecolor=fc,
                               edgecolor="#444", linewidth=0.6, zorder=3))
        ax.text(x, y + 0.05, c[:15], ha="center", va="center", fontsize=4.4, zorder=4)
        ax.text(x, y - 0.11, typ[:14], ha="center", va="center", fontsize=4.0,
                color="#333", zorder=4)
    for c in nodes:
        for u in cons.get(c, set()):
            if u in pos:
                x0, y0 = pos[u]
                x1, y1 = pos[c]
                ax.plot([x0, x1], [y0 - 0.22, y1 + 0.22], color="#999", lw=0.4, zorder=1)
    ax.set_title(title, fontsize=8)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    ax.set_xlim(min(xs) - 1.0, max(xs) + 1.0)
    ax.set_ylim(min(ys) - 0.8, max(ys) + 0.8)
    ax.axis("off")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="s38417t100")
    ap.add_argument("--inst", default="injalpha")
    ap.add_argument("--ra", default="ys_id")
    ap.add_argument("--rb", default="ys_abc")
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--max-nodes", type=int, default=50)
    ap.add_argument("--seed-cap", type=int, default=12,
                    help="种子单元上限 ✓（优先 Trojan 命名、按度数排序 ✓，避免图糊 ✗）")
    ap.add_argument("--out", type=Path, default=FIGS / "F8_rewrite_case.png")
    a = ap.parse_args()

    pa = VDIR / f"{a.host}__{a.inst}_d1_s42__{a.ra}.v"
    pb = VDIR / f"{a.host}__{a.inst}_d1_s42__{a.rb}.v"
    if not (pa.exists() and pb.exists()):
        raise SystemExit(f"[ERROR] missing view {pa} / {pb}")
    cells_a, cells_b = parse_v(pa), parse_v(pb)
    drv_a, cons_a = build_graph(cells_a)
    drv_b, cons_b = build_graph(cells_b)

    np_csv = T / "node_pairs_sat_node.csv"
    pairs = pd.DataFrame(columns=["net_a", "net_b", "status"])
    if np_csv.exists():
        d = pd.read_csv(np_csv, encoding="utf-8-sig").fillna("")
        ra, rb = a.ra.replace("ys_", ""), a.rb.replace("ys_", "")
        m = ((d["host"] == a.host) & (d["inst_a"] == a.inst) & (d["inst_b"] == a.inst)
             & (d["recipe_a"] == ra) & (d["recipe_b"] == rb) & (d["status"] == "proved"))
        pairs = d[m][["net_a", "net_b", "status"]].drop_duplicates()
    print(f"[in] proved pairs = {len(pairs)}")

    # 种子：**只取木马单元** ✓（名字含 Trojan ✓）→ 图才画的是"同一个木马块" ✓
    seed_a = set(sorted(c for c in cells_a if "trojan" in c.lower())[: max(4, a.seed_cap)])
    seed_b = set(sorted(c for c in cells_b if "trojan" in c.lower())[: max(4, a.seed_cap)])
    if not seed_a or not seed_b:                      # 回退：用已配对 ✓
        for _, r in pairs.iterrows():
            ca = next(iter(drv_a.get(str(r["net_a"]), set())), None)
            cb = next(iter(drv_b.get(str(r["net_b"]), set())), None)
            if ca and cb and len(seed_a) < a.seed_cap:
                seed_a.add(ca)
                seed_b.add(cb)
    if not seed_a:
        seed_a = set(sorted(cells_a)[:3])
    if not seed_b:
        seed_b = set(sorted(cells_b)[:3])

    print(f"[seed] A={len(seed_a)} B={len(seed_b)}")

    na = bfs(seed_a, cons_a, drv_a, cells_a, a.k, a.max_nodes)
    nb = bfs(seed_b, cons_b, drv_b, cells_b, a.k, a.max_nodes)
    print(f"[subgraph] A={len(na)} B={len(nb)}")
    pos_a, pos_b = layout(sorted(na), cons_a), layout(sorted(nb), cons_b)

    fig, axes = plt.subplots(1, 2, figsize=(13, 7))
    edges_a = [(u, c) for c in na for u in cons_a.get(c, set()) if u in na]
    edges_b = [(u, c) for c in nb for u in cons_b.get(c, set()) if u in nb]
    dpa, dpb = dot_pos(sorted(na), edges_a), dot_pos(sorted(nb), edges_b)
    if dpa and dpb:                                  # graphviz 布局 ✓（交叉最小化 ✓）
        draw_panel_dot(axes[0], dpa, cells_a, cons_a,
                       f"{a.host} . {a.inst} . {a.ra} (pre-ABC)")
        draw_panel_dot(axes[1], dpb, cells_b, cons_b,
                       f"{a.host} . {a.inst} . {a.rb} (post-ABC)")
        pos_a = {k: (v[0], v[1]) for k, v in dpa.items()}
        pos_b = {k: (v[0], v[1]) for k, v in dpb.items()}
        print("[layout] graphviz dot")
    else:
        pos_a, pos_b = layout(sorted(na), cons_a), layout(sorted(nb), cons_b)
        draw_panel(axes[0], sorted(na), pos_a, cells_a, cons_a,
                   f"{a.host} . {a.inst} . {a.ra} (pre-ABC)")
        draw_panel(axes[1], sorted(nb), pos_b, cells_b, cons_b,
                   f"{a.host} . {a.inst} . {a.rb} (post-ABC)")
        print("[layout] fallback grid")

    n_match = 0
    one_side = 0
    for _, r in pairs.iterrows():
        ca = next(iter(drv_a.get(str(r["net_a"]), set())), None)
        cb = next(iter(drv_b.get(str(r["net_b"]), set())), None)
        if ca in pos_a and cb in pos_b:
            x0, y0 = pos_a[ca]
            x1, y1 = pos_b[cb]
            axes[0].annotate("", xy=(x1, y1), xytext=(x0, y0),
                             xycoords=axes[1].transData, textcoords=axes[0].transData,
                             arrowprops=dict(arrowstyle="-|>", color="#2a7", lw=0.9, alpha=0.85,
                                             connectionstyle="arc3,rad=0.06"))
            axes[1].scatter([x1], [y1], s=14, c="#2a7", zorder=5)
            n_match += 1
        elif (ca in pos_a) or (cb in pos_b):
            one_side += 1
    note = (f"proved pairs total {len(pairs)} | both-in-region {n_match} | "
            f"one-side {one_side} | host-only {len(pairs) - n_match - one_side}")
    for ax in axes:
        ax.text(0.01, 0.01, note, transform=ax.transAxes, fontsize=6, color="#444",
                va="bottom", ha="left")
    fig.suptitle(f"F8 . gate-level rewrite of the same trojan ({a.host}/{a.inst})"
                 f"  matched-signal arrows: {n_match}", fontsize=9)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(f"[out] {a.out} (arrows={n_match})")

    rows = []
    for side, nodes, cells, rcp in (("A", na, cells_a, a.ra), ("B", nb, cells_b, a.rb)):
        for c in sorted(nodes):
            typ, pins = cells[c]
            rows.append(dict(side=side, view=f"{a.host}__{a.inst}__{rcp}", cell=c,
                             gate_type=typ, n_pins=len(pins),
                             is_trojan_name=int("trojan" in c.lower())))
    pd.DataFrame(rows).to_csv(T / "F8_nodes.csv", index=False, encoding="utf-8-sig")
    pairs.to_csv(T / "F8_pairs.csv", index=False, encoding="utf-8-sig")
    print(f"[out] {T / 'F8_nodes.csv'} ({len(rows)} rows) | {T / 'F8_pairs.csv'} ({len(pairs)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


