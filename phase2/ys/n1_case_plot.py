"""n1_case_plot.py —— N1 样例电路图的**新版绘制**（分层布局 + 分数标注 + 右栏 Top-8 ✓）。

设计 ✓：
  · **分层布局**：x = 距"无入度节点"的跳数 ✓、y = 层内均匀分布 ✓（不用 spring ✗ → 规整 ✓）
  · 节点：圆=组合门 ✓ / 方=DFF ✓；**粗黑边 = 标签正样本 ✓**；颜色 = 模型分数 ✓
  · 标注两行：`门类` + `分数` ✓（有实例名则用名字 ✓）
  · 右栏：图例 ✓ + colorbar ✓ + **Top-8 分数表** ✓ + 统计 ✓
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def short(nm: str) -> str:
    u = nm.upper()
    for k in ("DFF", "MUX", "XNOR", "XOR", "NAND", "NOR", "INV", "AND", "OR", "BUF"):
        if k in u:
            return "DFF" if k == "DFF" else k
    return nm[:4]


def ego_nodes(edges: dict, seeds: list[int], hops: int = 2, cap: int = 120) -> set[int]:
    """保留：正样本 ∪ 反向 2 跳（触发侧 ✓）∪ 正向 2 跳（输出侧 ✓）。"""
    keep = set(seeds)
    fr = set(seeds)
    for _ in range(hops):
        nxt = set()
        for v in fr:
            nxt |= edges.get(v, set())
        fr = nxt - keep
        keep |= nxt
        if len(keep) >= cap:
            break
    return keep


def layered_pos(G: nx.DiGraph, max_per_col: int = 12):
    """分层布局（修版 ✓）：
    · x = 拓扑层 ✓（同层可**折列**，每列 ≤ max_per_col ✓ → 不会一根柱子堆到底 ✗）
    · y 归一化到 [-0.5, 0.5] ✓（否则列高差会把整图压成一条 ✗）
    """
    nl = list(G.nodes())
    layer = {v: 0 for v in nl}
    for _ in range(len(nl)):
        changed = False
        for a, b in G.edges():
            if layer[b] < layer[a] + 1:
                layer[b] = layer[a] + 1
                changed = True
        if not changed:
            break
    groups: dict[int, list[int]] = {}
    for v in nl:
        groups.setdefault(layer[v], []).append(v)
    pos = {}
    nL = max(1, max(groups) if groups else 1)
    for L, vs in groups.items():
        vs = sorted(vs)
        n = len(vs)
        cols = max(1, int(np.ceil(n / max_per_col)))
        per = int(np.ceil(n / cols))
        for i, v in enumerate(vs):
            c, r = divmod(i, per)
            x = (L + (c / max(1, cols)) * 0.8) / nL if nL else 0.0
            y = ((per - 1) / 2 - r) / max(1, per - 1) if per > 1 else 0.0
            pos[v] = (x, y)
    return pos, layer


def draw_case(view: str, idx: np.ndarray, y: np.ndarray, s: np.ndarray,
              src: np.ndarray, dst: np.ndarray, gname: np.ndarray,
              out_dir: Path, tag: str = "", names_list: list | None = None):
    pos_mask = y == 1
    if int(pos_mask.sum()) == 0:
        return None
    seeds = list(np.asarray(idx)[pos_mask][:20])
    edge_map: dict[int, set[int]] = {}
    for a, b in zip(src, dst):
        edge_map.setdefault(int(a), set()).add(int(b))
        edge_map.setdefault(int(b), set()).add(int(a))
    keep = ego_nodes(edge_map, seeds, hops=2, cap=120)
    G = nx.DiGraph()
    G.add_nodes_from(sorted(keep))
    G.add_edges_from([(a, b) for a, b in zip(src, dst) if a in keep and b in keep])
    if G.number_of_nodes() < 3:
        return None

    local = {int(v): k for k, v in enumerate(idx)}
    pos, layer = layered_pos(G, max_per_col=12)
    nl = list(G.nodes())
    sc = {v: float(s[local[v]]) for v in nl}
    vmin, vmax = min(sc.values()), max(sc.values())
    norm = Normalize(vmin=vmin, vmax=vmax if vmax > vmin else vmin + 1e-6)

    def _lab(v):
        if names_list is not None:
            return str(names_list[local[v]]).split(".")[0][-14:]
        return short(gname[local[v]])

    fig = plt.figure(figsize=(12.6, 7.8))
    gs = fig.add_gridspec(1, 20)
    ax = fig.add_subplot(gs[0, :15])
    axr = fig.add_subplot(gs[0, 16:])
    # ★ 图里是**对称邻接**（98.96% 边有反向孪生 ✗）→ 只画"层号严格 +1"的边 ✓ = 数据流单向 ✓
    flow_edges = [(a, b) for a, b in G.edges() if layer[b] == layer[a] + 1]
    nx.draw_networkx_edges(G, pos, edgelist=flow_edges, ax=ax, arrows=True, arrowsize=10,
                           edge_color="#9aa0a6", width=0.9, alpha=0.85,
                           connectionstyle="arc3,rad=0.06")
    comb = [v for v in nl if "DFF" not in gname[local[v]].upper()]
    dff = [v for v in nl if "DFF" in gname[local[v]].upper()]
    nx.draw_networkx_nodes(G, pos, nodelist=comb, ax=ax, node_shape="o",
                           node_color=[plt.cm.RdYlGn(norm(sc[v])) for v in comb],
                           node_size=[(560 if y[local[v]] == 1 else 260) if len(nl) <= 70 else (300 if y[local[v]] == 1 else 150) for v in comb],
                           linewidths=[2.8 if y[local[v]] == 1 else 0.7 for v in comb],
                           edgecolors="k")
    if dff:
        nx.draw_networkx_nodes(G, pos, nodelist=dff, ax=ax, node_shape="s",
                               node_color=[plt.cm.RdYlGn(norm(sc[v])) for v in dff],
                               node_size=[(520 if y[local[v]] == 1 else 260) if len(nl) <= 70 else (280 if y[local[v]] == 1 else 150) for v in dff],
                               linewidths=[2.8 if y[local[v]] == 1 else 0.7 for v in dff],
                               edgecolors="k")
    nx.draw_networkx_labels(G, pos, {v: f"{_lab(v)}\n{sc[v]:.2f}" for v in nl},
                            font_size=6.2 if len(nl) <= 70 else 4.8, ax=ax)
    ax.set_title(f"N1 case — {view}\nAP={average_precision_score(y, s):.3f}   "
                 f"AUC={roc_auc_score(y, s):.3f}   pos={int(pos_mask.sum())}/{len(y)}   "
                 f"shown {G.number_of_nodes()}n/{G.number_of_edges()}e"
                 + (f"   [{tag}]" if tag else "") + "   (arrows = data-flow only)", fontsize=9.5)
    ax.set_aspect("auto")
    ax.margins(0.06)
    ax.axis("off")

    axr.axis("off")
    axr.text(0.0, 1.0, "Legend", fontsize=9, weight="bold", va="top")
    axr.scatter([0.05], [0.93], s=110, c="#bbbbbb", edgecolors="k", marker="o")
    axr.text(0.15, 0.93, "comb. gate", fontsize=7.5, va="center")
    axr.scatter([0.05], [0.87], s=110, c="#bbbbbb", edgecolors="k", marker="s")
    axr.text(0.15, 0.87, "DFF (boundary)", fontsize=7.5, va="center")
    axr.scatter([0.05], [0.81], s=130, c="#bbbbbb", edgecolors="k", linewidths=2.8, marker="o")
    axr.text(0.15, 0.81, "trojan node (label=1)", fontsize=7.5, va="center")
    top = sorted(nl, key=lambda v: -sc[v])[:8]
    axr.text(0.0, 0.72, "Top-8 by score", fontsize=9, weight="bold", va="top")
    for i, v in enumerate(top):
        mark = "P" if y[local[v]] == 1 else "-"
        axr.text(0.0, 0.655 - i * 0.052,
                 f"{mark} {_lab(v)[:12]:<12s} {sc[v]:.3f} L{layer[v]}",
                 fontsize=6.8, va="top", family="monospace")
    axr.text(0.0, 0.20,
             f"DFF shown: {len(dff)}\npositives shown: {int(y[[local[v] for v in nl]].sum())}\n"
             f"mean score: {np.mean(list(sc.values())):.3f}\ncolour: red=low, green=high",
             fontsize=7, va="top")
    sm = plt.cm.ScalarMappable(cmap="RdYlGn", norm=norm)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=axr, fraction=0.09, pad=0.04, aspect=14)
    cb.ax.tick_params(labelsize=6.5)
    cb.set_label("score", fontsize=7)

    out_dir.mkdir(parents=True, exist_ok=True)
    nm = view.split("__", 1)[1][:34] + (("_" + tag) if tag else "")
    pth = out_dir / f"N1_case_{nm}.png"
    fig.tight_layout()
    fig.savefig(pth, dpi=170)
    plt.close(fig)
    print(f"[fig] {pth.name}")
    return dict(view=view, nodes=int(G.number_of_nodes()), pos=int(pos_mask.sum()),
                ap=float(average_precision_score(y, s)), auc=float(roc_auc_score(y, s)),
                png=str(pth.relative_to(ROOT)))
