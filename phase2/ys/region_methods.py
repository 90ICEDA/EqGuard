"""region_methods.py —— B4：区域构建方式比较（dev4）。

对比 5 种区域：
  M1 `dff`            DFF 边界锥（B2 用的 ✓）
  M2 `dff_merge1`     DFF 锥**跨 1 跳合并**（相邻锥合成一个 ✓）
  M3 `dff_merge2`     跨 2 跳合并 ✓
  M4 `po_cone`        每个 PO 的反向组合锥（遇 DFF 停 ✓）
  M5 `view`           整个视图 = 1 个区域（下界基线 ✓）
指标：区域数 / 平均大小 / 正区域纯度（正节点占正区域比例 ✓）/ 背景比 / 正样本覆盖率 /
      区域级 AP（区域分数 = 区域内节点分数最大值 ✓）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase2" / "ys"))
from region_eval import build_regions, dff_mask  # noqa: E402


def uf_merge(labels, pairs):
    """并查集：把 pairs 里相连的区域合并 ✓（labels 为每节点区域 id ✓）。"""
    ids = np.unique(labels)
    pos = {v: i for i, v in enumerate(ids)}
    base = labels.copy()
    par = np.arange(len(ids))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    for a, b in pairs:
        if a in pos and b in pos:
            ra, rb = find(pos[a]), find(pos[b])
            if ra != rb:
                par[rb] = ra
    root = np.array([find(i) for i in range(len(ids))])
    return root[np.searchsorted(ids, base)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/_dev4/data/processed/trans_graph.pt")
    ap.add_argument("--gnn", type=Path, default=ROOT / "_devcfg/gnn_dev4_g0.npz")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.15/03_特征与模型/区域评估")
    a = ap.parse_args()
    work = a.pt.parents[2]

    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    y = np.asarray(d.y, np.int8)
    tr = np.asarray(d.train_mask, bool)
    te = np.asarray(d.test_mask, bool)
    fids = json.loads((work / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))["file_ids"]
    view_ids = np.zeros(len(y), np.int64)
    vm = {}
    for i, v in enumerate(fids):
        vm.setdefault(v, []).append(i)
    for k, v in enumerate(sorted(vm)):
        view_ids[np.array(vm[v])] = k

    is_dff = dff_mask(X, work)
    p = np.zeros(len(y), np.float32)
    if a.gnn.exists():
        g = np.load(a.gnn)
        p[g["idx"].astype(np.int64)] = g["score"].astype(np.float32)
    else:
        print("[WARN] 没有 GNN 分数 → 用 LR")
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        ti = np.where(tr)[0]
        sc = StandardScaler().fit(X[ti])
        lr = LogisticRegression(max_iter=1000, class_weight="balanced").fit(sc.transform(X[ti]), y[ti])
        p = lr.predict_proba(sc.transform(X))[:, 1].astype(np.float32)

    base = build_regions(d.edge_index, is_dff, view_ids)
    src, dst = d.edge_index[0].numpy(), d.edge_index[1].numpy()
    dff_edge = is_dff[src] | is_dff[dst]

    methods = {"M1_dff": base}
    # M2/M3：把"隔着 DFF 的边"相邻的锥合并 ✓（k 跳 = 连续合并 k 次 ✓）
    cur = base
    for hops in (1, 2):
        pairs = list(zip(cur[src[dff_edge]], cur[dst[dff_edge]]))
        cur = uf_merge(cur, pairs)
        methods[f"M{hops + 1}_dff_merge{hops}"] = cur.copy()

    # M4：PO 反向锥（遇 DFF 停 ✓）
    #   PO 判定用**特征列** `touches_PO`（f28 ✓）—— 早先用"无后继"✗ 会把 DFF 当 PO ✗（M4 一度 0 区域 ✗）
    po = np.where(X[:, 28] > 0.5)[0]
    lab = np.full(len(y), -1, np.int64)
    lab[po] = po
    keep = ~is_dff[src]                       # 反向走：不穿过 DFF ✓
    s, t = src[keep], dst[keep]
    for _ in range(256):
        m = (lab[s] < 0) & (lab[t] >= 0)
        if not m.any():
            break
        ss, tt = s[m], lab[t][m]
        _, first = np.unique(ss, return_index=True)
        lab[ss[first]] = tt[first]
    left = np.where(lab < 0)[0]
    lab[left] = left
    methods["M4_po_cone"] = lab + view_ids * (len(y) + 1)

    methods["M5_view"] = view_ids.copy()

    rows = []
    for name, reg in methods.items():
        uniq, inv = np.unique(reg, return_inverse=True)
        R = len(uniq)
        size = np.bincount(inv, minlength=R)
        rmax = np.zeros(R, np.float32)
        np.maximum.at(rmax, inv, p)
        rpos = np.zeros(R, np.int32)
        np.add.at(rpos, inv, y)
        rview = np.zeros(R, np.int64)
        rview[inv] = view_ids
        is_te = np.isin(np.arange(R), np.unique(inv[te]))
        m = is_te & (size >= 2)
        posr = m & (rpos > 0)
        purity = float(rpos[posr].sum() / max(1, size[posr].sum()))
        bg = 1.0 - purity
        cov = float(rpos[m].sum() / max(1, y[te].sum()))
        ap = average_precision_score((rpos[m] > 0).astype(int), rmax[m]) if 0 < (rpos[m] > 0).sum() < m.sum() else float("nan")
        aps = []
        for k in range(len(vm)):
            mm = m & (rview == k)
            if mm.sum() < 5 or not (0 < (rpos[mm] > 0).sum() < mm.sum()):
                continue
            aps.append(average_precision_score((rpos[mm] > 0).astype(int), rmax[mm]))
        rows.append({"method": name, "regions_te": int(m.sum()), "pos_regions": int(posr.sum()),
                     "mean_size": round(float(size[m].mean()), 1),
                     "purity": round(purity, 3), "background_ratio": round(bg, 3),
                     "pos_coverage": round(cov, 3),
                     "region_AP_pooled": round(float(ap), 4),
                     "region_AP_perview_mean": round(float(np.mean(aps)), 4) if aps else float("nan")})
    r = pd.DataFrame(rows)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    r.to_csv(a.out_dir / "region_methods.csv", index=False, encoding="utf-8-sig")
    print(r.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
