"""n1_case_plot3.py —— N1 电路图 v5 ✓：**双面板**（输入路径 | 输出路径 ✓）。

为什么改 ✗→✓：单面板把"触发上游锥（输入路径 ✓）+ 载荷下游锥（输出路径 ✓）"塞进一张图 ✗，
60+ 个点必然挤 + 边交叉爆表 ✗。改成两个独立面板 ✓，各自**重新分层 + 重心排序** ✓：
  (a) **input path** —— 正样本的**上游**扇入 ✓（PI → trigger/payload ✓）
  (b) **output path** —— 正样本的**下游**扇出 ✓（payload/hijack → PO / DFF ✓）
两个面板共享同一**颜色归一化** ✓（分数可比 ✓）与同一角色配色 ✓（边框 ✓）。
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

from collections import Counter, deque

from n1_case_plot2 import (ROLE_COLOR, _savefig, layered_pos,  # noqa: E402
                           place_labels, select_nodes, short)

POS_ROLES = ("trigger", "payload", "hijack")


def _bfs_dist(G, anchors: set, direction: str = "in") -> dict:
    """从正样本出发，沿 preds（in ✓）或 succs（out ✓）做 BFS ✓ → {node: 距木马几跳} ✓。"""
    dist = {a: 0 for a in anchors}
    dq = deque(anchors)
    while dq:
        v = dq.popleft()
        nb = G.predecessors(v) if direction == "in" else G.successors(v)
        for u in nb:
            if u not in dist:
                dist[u] = dist[v] + 1
                dq.append(u)
    return dist


def _cone_pos(G, dist: dict, direction: str = "in", max_per_col: int = 20) -> dict:
    """**以正样本为原点**的锥形分层 ✓。

    (a) `direction="in"` ：上游 PI 在**最左** ✓、正样本在**最右** ✓（箭头 = 数据流向右 ✓）
    (b) `direction="out"`：正样本在左 ✓、PO/DFF 在右 ✓
    `max_per_col` 放大 ✓ → 同一"跳数层"尽量排成**一列** ✓（不再并排交错 ✗）。
    """
    lay = dict(dist)
    if direction == "in":                 # 上游在最左 ✓ 正样本在最右 ✓
        mx = max(lay.values()) if lay else 0
        lay = {v: mx - l for v, l in lay.items()}
    groups: dict[int, list] = {}
    for v, l in lay.items():
        groups.setdefault(l, []).append(v)
    nL = max(1, max(groups) if groups else 1)
    nbrs = G.successors if direction == "in" else G.predecessors
    pos: dict = {}
    for L in sorted(groups):
        vs = sorted(groups[L])
        if pos:
            def key(v, _p=pos):
                ys = [_p[u][1] for u in nbrs(v) if u in _p]
                return -(sum(ys) / len(ys)) if ys else 0.0
            vs = sorted(vs, key=key)
        n = len(vs)
        cols = max(1, int(np.ceil(n / max_per_col)))
        per = int(np.ceil(n / cols))
        for i, v in enumerate(vs):
            c, r = divmod(i, per)
            pos[v] = ((L + (c / max(1, cols)) * 0.8) / nL,
                      (((per - 1) / 2 - r) / max(1, per - 1)) if per > 1 else 0.0)
    return pos


def _reach(seed: set, adj: dict, depth: int | None = None) -> set:
    """邻接闭包 ✓；`depth` 给了就**只扩这么多跳** ✓（否则会一路扩到 PI ✗ 面板爆掉 ✗）。"""
    out = set(seed)
    fr = set(seed)
    k = 0
    while fr and (depth is None or k < depth):
        nxt = set()
        for v in fr:
            nxt |= adj.get(v, set())
        nxt -= out
        if not nxt:
            break
        out |= nxt
        fr = nxt
        k += 1
    return out


def draw_panel(ax, node_set: set, keep_edges: list, role: dict,
               sc: dict, y, local, gname, norm, lab, fontsize: float,
               title: str, anchors: set, direction: str) -> int:
    """画一个面板 ✓（只画 node_set 内的点/边 ✓，**以正样本为原点**分层 ✓）。返回边数 ✓。"""
    edges = [(a, b) for a, b in keep_edges if a in node_set and b in node_set]
    d: dict[int, int] = {}
    for a, b in edges:
        d[a] = d.get(a, 0) + 1
        d[b] = d.get(b, 0) + 1
    nodes = [n for n in node_set if d.get(n, 0) > 0 or role[n] in (POS_ROLES + ("flagged",))]
    if not nodes:
        ax.axis("off")
        return 0
    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    G.add_edges_from(edges)
    anchors_in = {a for a in anchors if a in G}
    dist = _bfs_dist(G, anchors_in, direction)
    nodes = [n for n in nodes if n in dist]          # ✓ 只留**在路径上**的点 ✓（其余不进面板 ✓）
    if not nodes:
        ax.axis("off")
        return 0
    G = G.subgraph(nodes).copy()
    edges = [(a, b) for a, b in edges if a in G and b in G]
    pos = _cone_pos(G, dist, direction)

    nx.draw_networkx_edges(G, pos, edgelist=edges, ax=ax, arrows=True, arrowsize=7,
                           edge_color="#b8bec4", width=0.7, alpha=0.9,
                           node_size=300, min_source_margin=5, min_target_margin=5)
    comb = [v for v in nodes if "DFF" not in gname[local[v]].upper()]
    dff = [v for v in nodes if "DFF" in gname[local[v]].upper()]
    small = len(nodes) > 45
    for grp, shape, base in ((comb, "o", 460), (dff, "s", 430)):
        if not grp:
            continue
        nx.draw_networkx_nodes(
            G, pos, nodelist=grp, ax=ax, node_shape=shape,
            node_color=[plt.cm.RdYlGn(norm(sc[v])) for v in grp],
            node_size=[(base if y[local[v]] == 1 else base * 0.55) * (0.62 if small else 1.0)
                       for v in grp],
            linewidths=[2.2 if y[local[v]] == 1 else 1.2 for v in grp],
            edgecolors=[ROLE_COLOR[role[v]] for v in grp])
    place_labels(ax.figure, ax, pos, {v: f"{lab(v)} {sc[v]:.2f}" for v in nodes},
                 prio={v: sc[v] for v in nodes}, fontsize=fontsize,
                 node_px=5.5 if small else 7.0, pad_px=1.6)
    ax.set_title(title, fontsize=10, weight="bold")
    ax.set_aspect("auto")
    ax.margins(0.05)
    ax.axis("off")
    return len(edges)



def draw_case(view: str, idx: np.ndarray, y: np.ndarray, s: np.ndarray,
              src: np.ndarray, dst: np.ndarray, gname: np.ndarray,
              out_dir: Path, tag: str = "", names_list: list | None = None,
              po: np.ndarray | None = None, hnet: str = "",
              in_hops: int = 3, out_hops: int = 4,
              max_nodes: int = 130, max_skip: int = 2,
              control: bool = False, flag_topk: int = 10):
    pos_mask = y == 1
    if int(pos_mask.sum()) == 0 and not control:
        return None
    if int(pos_mask.sum()) > 0:
        seeds = list(np.asarray(idx)[pos_mask][:20])
    else:                                   # ✓ 对照视图 ✓：没有真值 → 取**模型打分最高**的 k 个 ✓（= 误报展示 ✓）
        order = np.argsort(-np.asarray(s))[:flag_topk]
        seeds = list(np.asarray(idx)[order])
    und: dict[int, set[int]] = {}
    for a, b in zip(src, dst):
        und.setdefault(int(a), set()).add(int(b))
        und.setdefault(int(b), set()).add(int(a))
    keep = select_nodes(und, seeds, hops=4 if control else 3, cap=320)
    G = nx.DiGraph()
    G.add_nodes_from(sorted(keep))
    G.add_edges_from([(a, b) for a, b in zip(src, dst) if a in keep and b in keep])
    if G.number_of_nodes() < 3:
        return None
    local = {int(v): k for k, v in enumerate(idx)}

    lay0 = layered_pos(G)[1]
    flow0 = [(a, b) for a, b in G.edges() if lay0[b] > lay0[a]]
    deg: dict[int, int] = {}
    for a, b in flow0:
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
    G = G.subgraph({n for n in G.nodes() if deg.get(n, 0) > 0 or y[local[n]] == 1}).copy()
    pos, layer = layered_pos(G)
    flow = [(a, b) for a, b in G.edges() if layer[b] > layer[a]]
    preds = {n: set() for n in G.nodes()}
    succs = {n: set() for n in G.nodes()}
    for a, b in flow:
        preds[b].add(a)
        succs[a].add(b)

    role = {}
    if control and int(pos_mask.sum()) == 0:
        flag = set(seeds)
        for n in G.nodes():
            if n in flag:
                role[n] = "flagged"          # ✓ 模型误报（对照视图无真值 ✓）
            elif po is not None and bool(po[local[n]]):
                role[n] = "PO"
            else:
                role[n] = "other"
    else:
        for n in G.nodes():
            is_pos = y[local[n]] == 1
            has_pos_pred = any(y[local[m]] == 1 for m in preds[n])
            drives_out = ((po is not None and bool(po[local[n]]))
                          or any("DFF" in gname[local[m]].upper() for m in succs[n]))
            if is_pos and drives_out:
                role[n] = "hijack"
            elif is_pos and not has_pos_pred:
                role[n] = "trigger"
            elif is_pos:
                role[n] = "payload"
            elif has_pos_pred and drives_out:
                role[n] = "hijack"
            elif po is not None and bool(po[local[n]]):
                role[n] = "PO"
            else:
                role[n] = "other"

    keep_n = {n for n in G.nodes() if role[n] != "other"}
    fr = {n for n in keep_n if role[n] in ("trigger", "payload")}
    for _ in range(max(0, in_hops)):
        nxt = {a for a, b in flow if b in fr} - keep_n
        if not nxt or len(keep_n) >= max_nodes:
            break
        keep_n |= nxt
        fr = nxt
    fr = {n for n in keep_n if role[n] in ("payload", "hijack")}
    for _ in range(max(0, out_hops)):
        nxt = {b for a, b in flow if a in fr} - keep_n
        if not nxt or len(keep_n) >= max_nodes:
            break
        keep_n |= nxt
        fr = nxt
    G = G.subgraph(keep_n).copy()
    keep_edges = [(a, b) for a, b in flow if a in keep_n and b in keep_n]
    keep_edges = [(a, b) for a, b in keep_edges
                  if not (role[a] == "other" and role[b] == "other"
                          and (layer[b] - layer[a]) > max_skip)]
    nl = list(G.nodes())
    sc = {v: float(s[local[v]]) for v in nl}
    vmin, vmax = min(sc.values()), max(sc.values())
    norm = Normalize(vmin=vmin, vmax=vmax if vmax > vmin else vmin + 1e-6)

    def lab(v):
        return short(gname[local[v]])

    def nm(v):
        if names_list is not None:
            return str(names_list[local[v]]).split(".")[0][-14:]
        return f"n{int(v)}"

    # ⑦ 拆双面板 ✓：上游（输入路径 ✓）| 下游（输出路径 ✓）
    anchor_roles = POS_ROLES + (("flagged",) if control else ())
    posn = {n for n in G.nodes() if role[n] in anchor_roles}
    gn = set(G.nodes())
    up_set = _reach(posn, preds, depth=max(1, in_hops)) & gn
    dn_set = _reach(posn, succs, depth=max(1, out_hops)) & gn

    fig = plt.figure(figsize=(19.0, 10.0))
    gs = fig.add_gridspec(1, 26)
    ax_i = fig.add_subplot(gs[0, 0:11])
    ax_o = fig.add_subplot(gs[0, 11:22])
    axr = fig.add_subplot(gs[0, 23:26])
    fsi = 4.6 if len(up_set) <= 40 else 4.2
    fso = 4.6 if len(dn_set) <= 40 else 4.2
    ei = draw_panel(ax_i, up_set, keep_edges, role, sc, y, local, gname, norm, lab, fsi,
                    (f"(a) input path — PI → flagged gate  ({len(up_set)} nodes)" if control
                     else f"(a) input path — PI → trojan  ({len(up_set)} nodes)"), posn, "in")
    eo = draw_panel(ax_o, dn_set, keep_edges, role, sc, y, local, gname, norm, lab, fso,
                    (f"(b) output path — flagged → PO / DFF  ({len(dn_set)} nodes)" if control
                     else f"(b) output path — trojan → PO / DFF  ({len(dn_set)} nodes)"), posn, "out")
    has_pos = int(pos_mask.sum()) > 0
    try:
        ap_v = float(average_precision_score(y, s)) if has_pos else float("nan")
    except Exception:
        ap_v = float("nan")
    try:
        auc_v = float(roc_auc_score(y, s)) if has_pos else float("nan")
    except Exception:
        auc_v = float("nan")

    fig.suptitle(
        (("CONTROL — no ground-truth trojan (highlight = model flags)\n") if control else "")
        + f"N1 case — {view}\n"
        + (f"AP=n/a   AUC=n/a   (no ground truth)   " if not has_pos
           else f"AP={ap_v:.3f}   AUC={auc_v:.3f}   ")
        + f"pos={int(pos_mask.sum())}/{len(y)}   shown {G.number_of_nodes()}n/"
        f"pos={int(pos_mask.sum())}/{len(y)}   shown {G.number_of_nodes()}n/"
        f"{len(keep_edges)}e (edges: in {ei} / out {eo})"
        + (f"   [{tag}]" if tag else "") + "   (arrows = data-flow only)"
        + (f"\nhijacked net: {hnet}" if hnet else ""),
        fontsize=10, y=0.985)

    # 右侧面板 ✓（固定坐标 ✓ → 图例/计数/Top-8 互不压 ✓）
    axr.axis("off")
    axr.set_xlim(0, 1)
    axr.set_ylim(0, 1)

    def _row(yc, color, text, shape="o", fs=6.2):
        axr.plot([0.04], [yc], marker=shape, ms=6.0, mfc="#dddddd", mec=color,
                 mew=1.8, transform=axr.transAxes, clip_on=False)
        axr.text(0.14, yc, text, fontsize=fs, va="center", transform=axr.transAxes)

    axr.text(0.0, 0.99, "Roles (border colour)", fontsize=8.0, weight="bold",
             va="top", transform=axr.transAxes)
    yc = 0.93
    rows = ([("flagged", "model flag (no ground truth)"),
             ("PO", "primary output (touches_PO)"),
             ("other", "benign / context")] if control else
            [("trigger", "trigger tree (no pred)"),
             ("payload", "payload chain (trojan pred)"),
             ("hijack", "hijacked output gate"),
             ("PO", "primary output (touches_PO)"),
             ("other", "benign / context")])
    for k, lb in rows:
        _row(yc, ROLE_COLOR[k], lb)
        yc -= 0.040
    _row(yc, "#444444", "square = DFF", shape="s")

    from collections import Counter
    cnt = Counter(role[v] for v in nl)
    yc -= 0.065
    axr.text(0.0, yc, "role counts (shown)", fontsize=8.0, weight="bold",
             va="top", transform=axr.transAxes)
    yc -= 0.035
    for k in [r[0] for r in rows]:
        axr.text(0.04, yc, f"{k:<8s}{cnt.get(k, 0):>3d}", fontsize=6.2, va="center",
                 family="monospace", color=ROLE_COLOR[k], transform=axr.transAxes)
        yc -= 0.032
    yc -= 0.030
    axr.text(0.0, yc, "Top-8 by score", fontsize=8.0, weight="bold",
             va="top", transform=axr.transAxes)
    yc -= 0.035
    for v in sorted(nl, key=lambda u: -sc[u])[:8]:
        mark = "P" if y[local[v]] == 1 else "-"
        axr.text(0.0, yc, f"{mark} {nm(v)[:8]:<8s} {lab(v):<4s} {sc[v]:.3f} {role[v][:4]}",
                 fontsize=5.7, va="center", family="monospace", transform=axr.transAxes)
        yc -= 0.032
    axr.text(0.0, 0.02,
             f"DFF {sum(1 for v in nl if 'DFF' in gname[local[v]].upper())} | "
             f"edges {len(keep_edges)} | mean {np.mean(list(sc.values())):.3f}",
             fontsize=5.9, va="bottom", transform=axr.transAxes)
    sm = plt.cm.ScalarMappable(cmap="RdYlGn", norm=norm)
    sm.set_array([])
    cax = fig.add_axes([0.955, 0.37, 0.008, 0.24])
    cb = fig.colorbar(sm, cax=cax)
    cb.ax.tick_params(labelsize=5.8)
    cb.set_label("score", fontsize=6.2, labelpad=1)

    out_dir.mkdir(parents=True, exist_ok=True)
    name = view.split("__", 1)[1][:34] + (("_" + tag) if tag else "")
    prefix = "N1_ctl" if control else "N1_case"
    pth = out_dir / f"{prefix}_{name}.png"
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    pth = _savefig(fig, pth, dpi=170)
    plt.close(fig)
    print(f"[fig] {pth.name}")
    return dict(view=view, nodes=int(G.number_of_nodes()), pos=int(pos_mask.sum()),
                ap=ap_v, auc=auc_v,
                trigger=int(cnt.get("trigger", 0)), payload=int(cnt.get("payload", 0)),
                hijack=int(cnt.get("hijack", 0)), po=int(cnt.get("PO", 0)),
                edges=int(len(keep_edges)),
                png=str(pth.relative_to(Path(__file__).resolve().parents[2])))
