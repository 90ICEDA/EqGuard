"""n1_case_plot2.py —— N1 电路图 v3（修孤立点 ✓ + 角色标识 ✓）。

相对 v2 的两处改动 ✓：
  ① **不再丢长边** ✗→✓：只画 `layer[b] > layer[a]` 的边 ✓（跨层保留 ✓，反向与同层丢弃 ✓ → 单向 ✓、无孤立点 ✓）
  ② **角色标识** ✓（无需实例名 ✓，用标签+拓扑推断）：
       `trigger`：正样本里**没有正样本前驱**的门 ✓（触发树起点 ✓，红框 ✓）
       `payload`：正样本里**有正样本前驱**的门 ✓（载荷链 ✓，橙框 ✓）
       `hijack` ：**非**正样本，但前驱里有正样本、且自身通到 PO/DFF ✓（被劫持的输出门 ✓，紫框 ✓）
       `PO`     ：`touches_PO`（f28 ✓）→ 蓝色双框 ✓
       其余     ：灰框 ✓；**DFF** 用方块 ✓
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
ROLE_COLOR = {"trigger": "#d62728", "payload": "#ff7f0e", "hijack": "#9467bd",
              "PO": "#1f77b4", "other": "#888888", "flagged": "#e377c2"}


def short(nm: str) -> str:
    u = nm.upper()
    for k in ("DFF", "MUX", "XNOR", "XOR", "NAND", "NOR", "INV", "AND", "OR", "BUF"):
        if k in u:
            return "DFF" if k == "DFF" else k
    return nm[:4]


def select_nodes(edges: dict, seeds: list[int], hops: int = 2, cap: int = 120) -> set[int]:
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
    ranks = {L: i for i, L in enumerate(sorted(groups))}   # ✓ 层号压实（去掉空层 ✗ → 铺满宽度 ✓）
    nL = max(1, len(ranks) - 1)
    for L, vs in groups.items():
        vs = sorted(vs)
        n = len(vs)
        cols = max(1, int(np.ceil(n / max_per_col)))
        per = int(np.ceil(n / cols))
        for i, v in enumerate(vs):
            c, r = divmod(i, per)
            x = (ranks[L] + (c / max(1, cols)) * 0.8) / nL if nL else 0.0
            y = ((per - 1) / 2 - r) / max(1, per - 1) if per > 1 else 0.0
            pos[v] = (x, y)
    # 二次：Sugiyama 重心排序 ✓（下行 + 上行 各 2 轮 ✓ → 交叉大幅减少 ✓）
    def _place(L: int, vs2: list) -> None:
        n = len(vs2)
        cols = max(1, int(np.ceil(n / max_per_col)))
        per = int(np.ceil(n / cols))
        for i, v in enumerate(vs2):
            c, r = divmod(i, per)
            x = (ranks[L] + (c / max(1, cols)) * 0.8) / nL if nL else 0.0
            y = ((per - 1) / 2 - r) / max(1, per - 1) if per > 1 else 0.0
            pos[v] = (x, y)

    def _bary(vs: list, nb_iter) -> dict:
        if not vs:
            return {}
        acc: dict = {}
        for u, w in nb_iter:
            if u in pos and w in pos:
                acc.setdefault(w, []).append(pos[u][1])
        return {v: (float(np.mean(acc[v])) if v in acc else pos[v][1]) for v in vs}

    for _rnd in range(2):
        down = _rnd == 1
        for L in (sorted(groups, reverse=True) if down else sorted(groups)):
            vs = groups.get(L, [])
            if len(vs) < 2:
                continue
            if down:
                if L + 1 not in groups:
                    continue
                nb = [(u, w) for w, u in G.edges() if w in pos and u in pos
                      and layer[u] == L + 1]
                key = _bary(vs, nb)              # 用**后继**的 y ✓
            else:
                if L - 1 not in groups:
                    continue
                nb = [(w, u) for u, w in G.edges() if u in pos and w in pos
                      and layer[w] == L - 1]
                key = _bary(vs, nb)              # 用**前驱**的 y ✓
            if key:
                _place(L, sorted(vs, key=lambda v: -key.get(v, 0.0)))
    return pos, layer


def place_labels(fig, ax, pos, labels: dict, prio: dict,
                 fontsize: float = 5.8, node_px: float = 10.0,
                 pad_px: float = 2.5) -> None:
    """给**每个**节点放"门类型 / 置信度" ✓；贪心选位 ✗重叠→✓。

    做法 ✓：把 12 个候选偏移（上/下/左/右/4 斜角/远距）逐一试 ✓，
    取**与已放标签 + 所有节点圆**交叠面积最小、且不出画布**的那个 ✓。
    """
    fig.canvas.draw()
    k = float(fig.dpi) / 72.0                      # pt → px
    bx0, by0, bw, bh = ax.get_window_extent().bounds
    bx1, by1 = bx0 + bw, by0 + bh

    px: dict = {}
    nb: list = []
    for v, (xx, yy) in pos.items():
        sx, sy = ax.transData.transform((xx, yy))
        px[v] = (sx, sy)
        nb.append((sx - node_px, sy - node_px, sx + node_px, sy + node_px))

    def inter(a, b) -> float:
        w = min(a[2], b[2]) - max(a[0], b[0])
        h = min(a[3], b[3]) - max(a[1], b[1])
        return w * h if (w > 0 and h > 0) else 0.0

    cand = [(0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1),
            (0, -1.8), (0, 1.8), (-1.7, 0), (1.7, 0),
            (0, -2.6), (0, 2.6), (-2.4, 0), (2.4, 0)]
    placed: list = []
    for v in sorted(labels, key=lambda u: -prio.get(u, 0.0)):
        txt = labels[v]
        wpx = max(len(s) for s in txt.split("\n")) * fontsize * 0.60 * k + 3.0
        hpx = (txt.count("\n") + 1) * fontsize * 1.32 * k + 2.0
        sx, sy = px[v]
        best, best_box, best_off = None, None, (0, 0)
        for cx, cy in cand:
            ox = cx * (node_px + wpx / 2 + pad_px)
            oy = cy * (node_px + hpx / 2 + pad_px)
            box = (sx + ox - wpx / 2, sy + oy - hpx / 2,
                   sx + ox + wpx / 2, sy + oy + hpx / 2)
            cost = sum(inter(box, b) for b in placed) + sum(inter(box, b) for b in nb)
            if box[0] < bx0 or box[1] < by0 or box[2] > bx1 or box[3] > by1:
                cost += 1e9
            if best is None or cost < best:
                best, best_box, best_off = cost, box, (ox, oy)
            if cost == 0:
                break
        placed.append(best_box)
        far = max(abs(best_off[0]) / max(1e-6, (node_px + wpx / 2 + pad_px)),
                  abs(best_off[1]) / max(1e-6, (node_px + hpx / 2 + pad_px))) > 1.05
        ap_kw = {}
        if far or best > 0:
            ap_kw["arrowprops"] = dict(arrowstyle="-", lw=0.45, color="#8a8f94",
                                       shrinkA=1, shrinkB=1)
        ax.annotate(txt, xy=pos[v], xytext=(best_off[0] / k, best_off[1] / k),
                    textcoords="offset points", ha="center", va="center",
                    fontsize=fontsize, zorder=7, color="#111111", **ap_kw,
                    bbox=dict(boxstyle="round,pad=0.10", fc="white",
                              ec="none", alpha=0.80))


def _savefig(fig, pth: Path, dpi: int = 170) -> Path:
    """存图 ✓；若目标被预览器/杀软临时占用（`Errno 22` ✓）→ 退避重试 ✗→✓。"""
    import os
    import time
    tmp = pth.with_name(pth.stem + ".tmp.png")
    for i in range(6):
        try:
            fig.savefig(tmp, dpi=dpi)
            os.replace(tmp, pth)
            return pth
        except OSError as e:
            print(f"[save-retry {i}] {type(e).__name__}: {e}")
            time.sleep(0.6 * (i + 1))
    alt = pth.with_name(pth.stem + "_alt.png")
    fig.savefig(alt, dpi=dpi)
    print(f"[save-fallback] {alt.name}")
    return alt


def draw_case(view: str, idx: np.ndarray, y: np.ndarray, s: np.ndarray,
              src: np.ndarray, dst: np.ndarray, gname: np.ndarray,
              out_dir: Path, tag: str = "", names_list: list | None = None,
              po: np.ndarray | None = None, hnet: str = "",
              in_hops: int = 4, out_hops: int = 4,
              max_nodes: int = 130, max_skip: int = 2):
    pos_mask = y == 1
    if int(pos_mask.sum()) == 0:
        return None
    seeds = list(np.asarray(idx)[pos_mask][:20])
    und: dict[int, set[int]] = {}
    for a, b in zip(src, dst):
        und.setdefault(int(a), set()).add(int(b))
        und.setdefault(int(b), set()).add(int(a))
    keep = select_nodes(und, seeds, hops=3, cap=320)
    G = nx.DiGraph()
    G.add_nodes_from(sorted(keep))
    G.add_edges_from([(a, b) for a, b in zip(src, dst) if a in keep and b in keep])
    if G.number_of_nodes() < 3:
        return None
    local = {int(v): k for k, v in enumerate(idx)}

    # ① 剪掉"画出来会孤立"的点 ✓（保正样本 ✓）
    lay0 = layered_pos(G)[1]
    flow0 = [(a, b) for a, b in G.edges() if lay0[b] > lay0[a]]
    deg: dict[int, int] = {}
    for a, b in flow0:
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
    nkeep = {n for n in G.nodes() if deg.get(n, 0) > 0 or y[local[n]] == 1}
    G = G.subgraph(nkeep).copy()
    pos, layer = layered_pos(G)
    # ② 单向数据流边 ✓（跨层保留 ✓ → 不再丢长边 ✓）
    flow = [(a, b) for a, b in G.edges() if layer[b] > layer[a]]
    preds = {n: set() for n in G.nodes()}
    succs = {n: set() for n in G.nodes()}
    for a, b in flow:
        preds[b].add(a)
        succs[a].add(b)

    # ③ 角色 ✓（无需名字 ✓）
    role = {}
    for n in G.nodes():
        is_pos = y[local[n]] == 1
        has_pos_pred = any(y[local[m]] == 1 for m in preds[n])
        drives_out = ((po is not None and bool(po[local[n]]))
                      or any("DFF" in gname[local[m]].upper() for m in succs[n]))
        if is_pos and drives_out:
            role[n] = "hijack"          # 木马门**直接驱动真实输出/DFF** ✓ = 被劫持的输出端 ✓
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

    # ④ **路径扩张** ✓：触发器往上游扩 `in_hops` ✓（输入路径 ✓）；载荷/劫持往下游扩
    #    `out_hops` ✓（输出路径 → PO/DFF ✓）→ 不再把输入/输出路径剪窄 ✗
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
    pos, layer = layered_pos(G)
    keep_edges = [(a, b) for a, b in flow if a in keep_n and b in keep_n]
    # ⑤ 只压"纯上下文→纯上下文且跨 >max_skip 列"的长边 ✗（1–2 列保留 ✓ → 路径不断 ✓ 交叉可控 ✓）
    keep_edges = [(a, b) for a, b in keep_edges
                  if not (role[a] == "other" and role[b] == "other"
                          and (layer[b] - layer[a]) > max_skip)]
    # ⑥ 剪掉剪边后孤立的"纯上下文"节点 ✓（角色节点一律保留 ✓）
    d2: dict[int, int] = {}
    for a, b in keep_edges:
        d2[a] = d2.get(a, 0) + 1
        d2[b] = d2.get(b, 0) + 1
    drop = {n for n in G.nodes() if role[n] == "other" and d2.get(n, 0) == 0}
    if drop:
        G = G.subgraph(set(G.nodes()) - drop).copy()
        keep_edges = [(a, b) for a, b in keep_edges if a in G and b in G]
        pos, layer = layered_pos(G)
    nl = list(G.nodes())
    sc = {v: float(s[local[v]]) for v in nl}
    vmin, vmax = min(sc.values()), max(sc.values())
    norm = Normalize(vmin=vmin, vmax=vmax if vmax > vmin else vmin + 1e-6)

    def _lab(v):
        return short(gname[local[v]])

    def _nm(v):
        if names_list is not None:
            return str(names_list[local[v]]).split(".")[0][-14:]
        return f"n{int(v)}"

    fig = plt.figure(figsize=(18.0, 11.5))
    gs = fig.add_gridspec(1, 22)
    ax = fig.add_subplot(gs[0, :15])
    axr = fig.add_subplot(gs[0, 16:20])
    nx.draw_networkx_edges(G, pos, edgelist=keep_edges, ax=ax, arrows=True, arrowsize=8,
                           edge_color="#b8bec4", width=0.8, alpha=0.9,
                           node_size=380, min_source_margin=6, min_target_margin=6)
    comb = [v for v in nl if "DFF" not in gname[local[v]].upper()]
    dff = [v for v in nl if "DFF" in gname[local[v]].upper()]
    big = len(nl) <= 70
    for grp, shape, base in ((comb, "o", 560), (dff, "s", 520)):
        if not grp:
            continue
        nx.draw_networkx_nodes(
            G, pos, nodelist=grp, ax=ax, node_shape=shape,
            node_color=[plt.cm.RdYlGn(norm(sc[v])) for v in grp],
            node_size=[(base if y[local[v]] == 1 else base * 0.5) if big
                       else (base * 0.55 if y[local[v]] == 1 else base * 0.28) for v in grp],
            linewidths=[2.6 if y[local[v]] == 1 else 1.6 for v in grp],
            edgecolors=[ROLE_COLOR[role[v]] for v in grp])
    _fs = 5.4 if len(nl) <= 45 else (4.8 if len(nl) <= 70 else (4.3 if len(nl) <= 110 else 3.9))
    place_labels(fig, ax, pos,
                 {v: f"{_lab(v)} {sc[v]:.2f}" for v in nl},
                 prio={v: sc[v] for v in nl}, fontsize=_fs,
                 node_px=8.0 if big else 6.5, pad_px=2.0)
    ax.set_title(f"N1 case — {view}\nAP={average_precision_score(y, s):.3f}   "
                 f"AUC={roc_auc_score(y, s):.3f}   pos={int(pos_mask.sum())}/{len(y)}   "
                 f"shown {G.number_of_nodes()}n/{len(keep_edges)}e"
                 + (f"   [{tag}]" if tag else "") + "   (arrows = data-flow only)"
                 + (f"\nhijacked net: {hnet}" if hnet else ""),
                 fontsize=9.5)
    ax.set_aspect("auto")
    ax.margins(0.06)
    ax.axis("off")

    axr.axis("off")
    axr.set_xlim(0, 1)
    axr.set_ylim(0, 1)

    def _row(yc, color, text, shape="o", fs=6.6):
        axr.plot([0.035], [yc], marker=shape, ms=6.5, mfc="#dddddd", mec=color,
                 mew=1.8, transform=axr.transAxes, clip_on=False)
        axr.text(0.11, yc, text, fontsize=fs, va="center", transform=axr.transAxes)

    axr.text(0.0, 0.995, "Roles (border colour)", fontsize=8.5, weight="bold",
             va="top", transform=axr.transAxes)
    yc = 0.94
    for k, lb in (("trigger", "trigger tree (no trojan pred)"),
                  ("payload", "payload chain (trojan pred)"),
                  ("hijack", "hijacked output gate"),
                  ("PO", "primary output (touches_PO)"),
                  ("other", "benign / context")):
        _row(yc, ROLE_COLOR[k], lb)
        yc -= 0.036
    _row(yc, "#444444", "square = DFF (region boundary)", shape="s")

    from collections import Counter
    cnt = Counter(role[v] for v in nl)          # ✓ 只数**画出来的**节点 ✓
    yc -= 0.055
    axr.text(0.0, yc, "role counts (shown)", fontsize=8.5, weight="bold",
             va="top", transform=axr.transAxes)
    yc -= 0.032
    for k in ("trigger", "payload", "hijack", "PO", "other"):
        axr.text(0.03, yc, f"{k:<8s}{cnt.get(k, 0):>3d}", fontsize=6.8, va="center",
                 family="monospace", color=ROLE_COLOR[k], transform=axr.transAxes)
        yc -= 0.030
    yc -= 0.030
    axr.text(0.0, yc, "Top-8 by score", fontsize=8.5, weight="bold",
             va="top", transform=axr.transAxes)
    yc -= 0.032
    for v in sorted(nl, key=lambda u: -sc[u])[:8]:
        mark = "P" if y[local[v]] == 1 else "-"
        axr.text(0.0, yc, f"{mark} {_nm(v)[:9]:<9s} {_lab(v):<4s} {sc[v]:.3f} {role[v][:4]}",
                 fontsize=6.6, va="center", family="monospace", transform=axr.transAxes)
        yc -= 0.030
    axr.text(0.0, 0.02,
             f"DFF {len(dff)} | edges {len(keep_edges)} | "
             f"mean {np.mean(list(sc.values())):.3f}",
             fontsize=6.6, va="bottom", transform=axr.transAxes)
    sm = plt.cm.ScalarMappable(cmap="RdYlGn", norm=norm)
    sm.set_array([])
    cax = fig.add_axes([0.925, 0.34, 0.009, 0.30])
    cb = fig.colorbar(sm, cax=cax)
    cb.ax.tick_params(labelsize=6.0)
    cb.set_label("score", fontsize=7, labelpad=2)
    cb.ax.tick_params(labelsize=6.5)
    cb.set_label("score", fontsize=7)

    out_dir.mkdir(parents=True, exist_ok=True)
    nm = view.split("__", 1)[1][:34] + (("_" + tag) if tag else "")
    pth = out_dir / f"N1_case_{nm}.png"
    fig.tight_layout()
    pth = _savefig(fig, pth, dpi=170)
    plt.close(fig)
    print(f"[fig] {pth.name}")
    return dict(view=view, nodes=int(G.number_of_nodes()), pos=int(pos_mask.sum()),
                ap=float(average_precision_score(y, s)), auc=float(roc_auc_score(y, s)),
                trigger=int(cnt.get("trigger", 0)), payload=int(cnt.get("payload", 0)),
                hijack=int(cnt.get("hijack", 0)), po=int(cnt.get("PO", 0)),
                edges=int(len(keep_edges)), png=str(pth.relative_to(ROOT)))
