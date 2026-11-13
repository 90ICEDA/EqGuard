"""make_n1_case_figs.py —— N1.4：**木马样例电路图 + 节点风险分数**（论文 F2 ✓）。

为什么这样做 ✓：`class_map_trans.json` 只存**类别 id** ✗（不是门名 ✗），所以不解析 Verilog ✗；
改用 **图结构 + 分数 + 门类型** ✓：
  · 取某视图的**标签正节点**（木马触发/载荷 ✓，`y=1` ✓）作为"核心" ✓
  · 取它们 **2 跳 ego 子图** ✓（≤ 60 节点 ✓）
  · 颜色 = 模型分数 ✓（RdYlGn ✓），边框 = 是否正样本 ✓，形状 = DFF / 组合门 ✓
  · 文字 = 门类型简称 ✓（INV / AND / XOR / MUX / DFF ✓，来自 `gatelookup` ✓）
输出：`10.15/07_论文图表/figs/N1_case_<view>.png` ✓ + `tables/N1_case_index.csv` ✓
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
from matplotlib.colors import Normalize  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(Path(__file__).resolve().parent))
from n1_case_plot3 import draw_case  # noqa: E402  (v5 双面板 ✓ 输入/输出路径 ✓)
OUT = ROOT / "10.15" / "07_论文图表"


def gate_names(work: Path) -> list[str]:
    raw = json.loads((work / "gatelookup_recommended.json").read_text(encoding="utf-8"))
    raw = raw.get("gatelookup", raw)
    return [k for k, _ in sorted(raw.items(), key=lambda kv: int(kv[1]))]


def short(nm: str) -> str:
    u = nm.upper()
    for k in ("DFF", "MUX", "XOR", "XNOR", "NAND", "NOR", "INV", "AND", "OR", "BUF"):
        if k in u:
            return "DFF" if k == "DFF" else k
    return nm[:4]


def ego_nodes(edges: dict, seeds: list[int], hops: int = 2, cap: int = 60) -> set[int]:
    keep = set(seeds)
    frontier = set(seeds)
    for _ in range(hops):
        nxt = set()
        for v in frontier:
            nxt |= edges.get(v, set())
        frontier = nxt - keep
        keep |= nxt
        if len(keep) >= cap:
            break
    return keep


def draw_one(view: str, idx: np.ndarray, y: np.ndarray, s: np.ndarray,
             src: np.ndarray, dst: np.ndarray, gname: np.ndarray,
             out_dir: Path, tag: str = "", names_list: list | None = None) -> dict | None:
    pos_mask = y == 1
    if int(pos_mask.sum()) == 0:
        return None
    seeds = list(np.asarray(idx)[pos_mask][:20])
    edge_map: dict[int, set[int]] = {}
    for a, b in zip(src, dst):
        edge_map.setdefault(int(a), set()).add(int(b))
        edge_map.setdefault(int(b), set()).add(int(a))
    keep = ego_nodes(edge_map, seeds, hops=2, cap=60)
    sub = [(a, b) for a, b in zip(src, dst) if a in keep and b in keep]
    G = nx.DiGraph()
    G.add_nodes_from(sorted(keep))
    G.add_edges_from(sub)
    if G.number_of_nodes() < 3:
        return None

    local = {int(v): k for k, v in enumerate(idx)}
    pos = nx.spring_layout(G, seed=42, k=0.9 / max(1, G.number_of_nodes() ** 0.5))
    sc = [float(s[local[v]]) for v in G.nodes()]
    norm = Normalize(vmin=min(sc), vmax=max(sc) if max(sc) > min(sc) else min(sc) + 1e-6)
    colors = [plt.cm.RdYlGn(norm(v)) for v in sc]
    sizes = [520 if y[local[v]] == 1 else 260 for v in G.nodes()]
    lw = [2.6 if y[local[v]] == 1 else 0.6 for v in G.nodes()]
    shapes = ["s" if "DFF" in gname[local[v]].upper() else "o" for v in G.nodes()]

    fig, ax = plt.subplots(figsize=(9.2, 7.0))
    nx.draw_networkx_edges(G, pos, ax=ax, arrows=True, arrowsize=8,
                           edge_color="#b0b0b0", width=0.8)
    for shp in ("o", "s"):
        ns = [v for v in G.nodes() if ("s" if "DFF" in gname[local[v]].upper() else "o") == shp]
        if not ns:
            continue
        nx.draw_networkx_nodes(G, pos, nodelist=ns, ax=ax,
                               node_color=[colors[list(G.nodes()).index(v)] for v in ns],
                               node_size=[sizes[list(G.nodes()).index(v)] for v in ns],
                               node_shape=shp,
                               linewidths=[lw[list(G.nodes()).index(v)] for v in ns],
                               edgecolors="k")
    def _lab(v):
        if names_list is not None:
            nm = str(names_list[local[v]])
            return nm.split(".")[0][-14:]
        return short(gname[local[v]])
    labels = {v: _lab(v) for v in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=6, ax=ax)
    sm = plt.cm.ScalarMappable(cmap="RdYlGn", norm=norm)
    sm.set_array([])
    fig.colorbar(sm, ax=ax, shrink=0.75, label="model score")
    ap = average_precision_score(y, s)
    auc = roc_auc_score(y, s)
    ax.set_title(f"N1 case — {view}\nAP={ap:.3f}  AUC={auc:.3f}  "
                 f"pos={int(pos_mask.sum())}/{len(y)}  (bold border = trojan node)", fontsize=9)
    ax.axis("off")
    out_dir.mkdir(parents=True, exist_ok=True)
    nm = view.split('__', 1)[1][:34] + (('_' + tag) if tag else "")
    p = out_dir / f"N1_case_{nm}.png"
    fig.tight_layout()
    fig.savefig(p, dpi=160)
    plt.close(fig)
    print(f"[fig] {p.name}")
    return dict(view=view, nodes=int(G.number_of_nodes()), pos=int(pos_mask.sum()),
                ap=float(ap), auc=float(auc), png=str(p.relative_to(ROOT)))


def hijack_net_of(view: str, fold: Path) -> str:
    """从**注入后、综合前**的网表里读被劫持网络名 ✓（`*HJ` mux 的 `.Y(...)` ✓）。

    注意 ✓：fold 的 `trans/` 是**综合后**产物 ✗（mux 已变成 `$_MUX_`、网络名被重写 ✗），
    所以优先去 `generate_trans/hosts_bt2|hosts_e1|hosts_e2/<host>/<view>.v` 找 ✓。
    """
    import re as _re
    host = view.split('__')[0]
    src = '__'.join(view.split('__')[:2])   # hosts_bt2 里的网表**不带配方后缀** ✓
    cands = [fold.parent.parent / h / host / f"{src}.v"
             for h in ("hosts_bt2", "hosts_e1", "hosts_e2")]
    cands += [fold / "trans" / f"{view}.v", fold / "orig" / f"{view}.v"]
    for f in cands:
        if not f.exists():
            continue
        txt = f.read_text(encoding="utf-8", errors="replace")
        m = _re.search(r"\b\S+\s+(\S*HJ)\s*\([^;]*?\.(?:Y|Q|Z|O|OUT)\s*\(\s*([\w\\]+)\s*\)", txt, _re.S)
        if m:
            return m.group(2).lstrip("\\")
    return ""


def net_family(net: str) -> str:
    """网络名 → 功能族 ✓（只有前缀有语义时才有意义 ✗→✓）。"""
    s = (net or "").lower()
    if not s:
        return "unknown"
    if s.startswith("test_") or s.startswith("scan"):
        return "SCAN/TEST chain"
    if s.startswith("rec") or "receiver" in s:
        return "UART RECEIVER path"
    if s.startswith("xmit") or "xmit" in s:
        return "UART TRANSMITTER path"
    if s.startswith("g") and s[1:].isdigit():
        return "generic internal logic"
    return "internal net"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt")
    ap.add_argument("--npz", type=Path, default=ROOT / "_devcfg/gnn_v31_s42.npz")
    ap.add_argument("--views", default="", help="逗号分隔；留空=自动挑 最好/最差/对照 各 1 个 ✓")
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--tag", default="")
    ap.add_argument("--names", type=Path, default=None, help="node_names json.gz ✓")
    ap.add_argument("--in-hops", type=int, default=4, help="触发/载荷向**上游**扩几跳 ✓")
    ap.add_argument("--out-hops", type=int, default=4, help="载荷/劫持向**下游**扩几跳 ✓")
    ap.add_argument("--max-nodes", type=int, default=130, help="节点上限 ✓")
    ap.add_argument("--max-skip", type=int, default=2,
                    help="纯上下文边最多跨几列 ✓（越小越干净 ✓）")
    ap.add_argument("--control", action="store_true",
                    help="对照视图模式 ✓：无真值 → 高亮**模型误报** ✓（输出 N1_ctl_*.png ✓）")
    ap.add_argument("--flag-topk", type=int, default=10,
                    help="对照模式下高亮多少个最高分节点 ✓")
    a = ap.parse_args()
    pt = a.pt
    work = pt.parents[2]
    d = torch.load(pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    y = np.asarray(d.y, np.int8).astype(np.int64)
    ei = d.edge_index.numpy()
    fids = np.asarray(json.loads((work / "data/for_train/metadata_trans.json")
                                 .read_text(encoding="utf-8"))["file_ids"]).astype(str)
    meta = json.loads((work / "views.json").read_text(encoding="utf-8"))
    test_views = list(meta["test_views"])

    nm_map = None
    if a.names and Path(a.names).exists():
        import gzip as _gz
        with _gz.open(a.names, "rt", encoding="utf-8") as _fh:
            nm_map = json.load(_fh)
        print(f"[names] {len(nm_map)} 个视图带实例名 ✓")

    names = gate_names(work)
    ng = len(names)
    gid = np.where(X[:, :ng].sum(1) > 0, X[:, :ng].argmax(1), -1)
    gname = np.array([names[i] if 0 <= i < ng else "NA" for i in gid])
    po_mask = X[:, 28] > 0.5      # touches_PO ✓ 用于"输出端"角色标记 ✓

    g = np.load(a.npz)
    s = np.full(len(y), -1.0, np.float32)
    s[g["idx"].astype(np.int64)] = g["score"].astype(np.float32)
    seen = np.zeros(len(y), bool)
    seen[g["idx"].astype(np.int64)] = True

    per_view = {}
    for v in test_views:
        m = (fids == v) & seen
        yy = y[m]
        if 0 < yy.sum() < len(yy):
            per_view[v] = float(average_precision_score(yy, s[m]))
    if a.views:
        picks = [x.strip() for x in a.views.split(",") if x.strip()]
    elif a.control:
        picks = []                       # ✓ 对照模式必须显式 --views ✓（无 AP 可挑 ✗）
    else:
        order = sorted(per_view, key=per_view.get)
        picks = []
        if order:
            picks.append(order[-1])          # 最好 ✓
            picks.append(order[0])           # 最差 ✓
        ctl = [v for v in order if "ctlmatch" in v]
        if ctl:
            picks.append(ctl[-1])            # 匹配对照 ✓（无正样本 → 会自动跳过 ✓）
    print(f"[pick] {picks}")

    rows = []
    for v in picks:
        m = np.where(fids == v)[0]
        hnet = hijack_net_of(v, pt.parents[2])
        if hnet:
            hnet = f"{hnet}  [{net_family(hnet)}]"
        if len(m) == 0:
            print(f"[skip] {v} 不在 fold 内 ✗")
            continue
        loc = np.isin(ei[0], m) & np.isin(ei[1], m)
        r = draw_case(v, m, y[m], s[m], ei[0][loc], ei[1][loc], gname, a.out_dir / "figs", a.tag,
                              (nm_map.get(v) if nm_map else None), po=po_mask[m], hnet=hnet,
                              in_hops=a.in_hops, out_hops=a.out_hops,
                              max_nodes=a.max_nodes, max_skip=a.max_skip,
                              control=a.control, flag_topk=a.flag_topk)
        if r:
            rows.append(r)
    if rows:
        (a.out_dir / "tables").mkdir(parents=True, exist_ok=True)
        idx_name = "N1_ctrl_index.csv" if a.control else "N1_case_index.csv"
        pd.DataFrame(rows).to_csv(a.out_dir / "tables" / idx_name,
                                  index=False, encoding="utf-8-sig")
        print(f"\n[out] {a.out_dir / 'tables' / idx_name}（{len(rows)} 张 ✓）")
    else:
        print("[WARN] 没有画出任何样例 ✗（检查 views 是否含正样本 ✓）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
