"""region_eval.py —— B2：DFF 边界锥（区域）+ 区域级 AP。

区域定义（与 A3 的 `bnd`/keep 语义一致 ✓）：
  · 种子 = **DFF 节点** 与 **无组合输入的门**（PI 侧起点 ✓）；
  · 从种子沿数据流前进，**遇到 DFF 就停**（DFF 是边界 ✓）→ 一个锥 = 一个区域 ✓；
  · 未被覆盖的组合门（悬空/环）各自成小区域 ✓。

区域分数 = 区域内节点分数的 **max** ✓（也可 top-3 均值 ✓）；区域标签 = 区域内是否含正节点 ✓。
评估：区域级 pooled AP + per-view AP ✓（只统计两类都有的视图 ✓）。

用法：
  python -X utf8 phase2/ys/region_eval.py --pt generate_trans/folds/_dev3/data/processed/trans_graph.pt \
      --gnn _devcfg/gnn_dev3.npz --out-dir 10.15/03_特征与模型/区域评估
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]


def dff_mask(X, work: Path) -> np.ndarray:
    raw = json.loads((work / "gatelookup_recommended.json").read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "gatelookup" in raw:
        raw = raw["gatelookup"]
    names = [k for k, _ in sorted(raw.items(), key=lambda kv: int(kv[1]))]
    ng = X.shape[1] - 14
    gid = np.where(X[:, :ng].sum(1) > 0, X[:, :ng].argmax(1), -1)
    is_dff = np.zeros(len(gid), bool)
    for i, nm in enumerate(names[:ng]):
        if "DFF" in nm.upper():
            is_dff |= (gid == i)
    return is_dff


def build_regions(edge_index, is_dff, view_ids):
    """多源标签传播：种子 = DFF ∪ 无输入门 ✓；**不穿过 DFF** ✓。返回每节点的区域 id ✓。"""
    src, dst = edge_index[0].numpy(), edge_index[1].numpy()
    n = len(is_dff)
    has_in = np.zeros(n, bool)
    has_in[dst] = True
    seeds = np.where(is_dff | (~has_in))[0]
    lab = np.full(n, -1, dtype=np.int64)
    lab[seeds] = seeds

    keep = ~is_dff[dst]                       # 不穿过 DFF ✓
    s, d = src[keep], dst[keep]
    order = np.argsort(s, kind="stable")
    s, d = s[order], d[order]

    for _ in range(256):
        m = (lab[d] < 0) & (lab[s] >= 0)
        if not m.any():
            break
        dd, ss = d[m], lab[s][m]
        _, first = np.unique(dd, return_index=True)   # 先到先得 ✓
        lab[dd[first]] = ss[first]

    left = np.where(lab < 0)[0]
    if left.size:
        lab[left] = left                       # 悬空/环内残余：自成一区 ✓
    return lab + view_ids.astype(np.int64) * (n + 1)


def main() -> int:
    ap = argparse.ArgumentParser(description="B2 区域级评估（DFF 边界锥）")
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/_dev3/data/processed/trans_graph.pt")
    ap.add_argument("--gnn", type=Path, default=ROOT / "_devcfg/gnn_dev3.npz")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.15/03_特征与模型/区域评估")
    a = ap.parse_args()
    work = a.pt.parents[2]

    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    y = np.asarray(d.y, np.int8)
    tr = np.asarray(d.train_mask, bool)
    te = np.asarray(d.test_mask, bool)
    fids = json.loads((work / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))["file_ids"]

    view_of = {}
    for i, v in enumerate(fids):
        view_of.setdefault(v, []).append(i)
    view_ids = np.zeros(len(y), np.int64)
    vnames = sorted(view_of)
    for k, v in enumerate(vnames):
        view_ids[np.array(view_of[v])] = k

    is_dff = dff_mask(X, work)
    reg = build_regions(d.edge_index, is_dff, view_ids)
    uniq, inv = np.unique(reg, return_inverse=True)
    R = len(uniq)
    reg_view = np.zeros(R, np.int64)
    reg_view[inv] = view_ids
    print(f"[区域] 节点 {len(y)}｜DFF {int(is_dff.sum())}｜区域 {R}｜平均每区 {len(y)/R:.1f} 个门")

    # ---- 节点分数：GNN / LR / GBDT ----
    rng = np.random.default_rng(0)
    ti = np.where(tr)[0]
    yi = y[ti]
    neg = rng.choice(np.where(yi == 0)[0], min(250000, int((yi == 0).sum())), replace=False)
    sel = np.concatenate([np.where(yi == 1)[0], neg])
    sc = StandardScaler().fit(X[ti][sel])
    lr = LogisticRegression(max_iter=1000, class_weight="balanced").fit(sc.transform(X[ti][sel]), yi[sel])
    gb = HistGradientBoostingClassifier(max_iter=300, random_state=0).fit(X[ti][sel], yi[sel])
    p_lr = lr.predict_proba(sc.transform(X))[:, 1].astype(np.float32)
    p_gb = gb.predict_proba(X)[:, 1].astype(np.float32)
    p_gnn = np.zeros(len(y), np.float32)
    if a.gnn.exists():
        g = np.load(a.gnn)
        p_gnn[g["idx"].astype(np.int64)] = g["score"].astype(np.float32)
    scores = {"GNN": p_gnn, "LR": p_lr, "GBDT": p_gb,
              "GNN+LR+GBDT": (p_gnn + p_lr + p_gb) / 3}

    te_nodes = np.where(te)[0]
    te_reg = np.unique(inv[te_nodes])
    rows, pv_rows = [], []
    for name, p in scores.items():
        rmax = np.zeros(R, np.float32)
        np.maximum.at(rmax, inv, p)                      # 区域分数 = max ✓
        rpos = np.zeros(R, np.int8)
        np.maximum.at(rpos, inv, y)                      # 区域标签 = 是否含正 ✓
        rsz = np.bincount(inv, minlength=R)
        m = np.isin(np.arange(R), te_reg) & (rsz >= 2)
        rs, ry = rmax[m], rpos[m]
        # pooled（测试区域 ✓）
        ap_pool = average_precision_score(ry, rs) if 0 < ry.sum() < len(ry) else float("nan")
        rows.append({"model": name, "regions": int(m.sum()), "pos_regions": int(ry.sum()),
                     "pooled_region_AP": round(float(ap_pool), 4),
                     "mean_region_size": round(float(rsz[m].mean()), 1)})
        # per-view
        aps = []
        for k, v in enumerate(vnames):
            mm = m & (reg_view == k)
            if mm.sum() < 5:
                continue
            ss_, yy_ = rmax[mm], rpos[mm]
            if not (0 < yy_.sum() < len(yy_)):
                continue
            aps.append(float(average_precision_score(yy_, ss_)))
        if aps:
            pv_rows.append({"model": name, "views": len(aps),
                            "median": round(float(np.median(aps)), 4),
                            "mean": round(float(np.mean(aps)), 4),
                            "p90": round(float(np.percentile(aps, 90)), 4),
                            "max": round(float(np.max(aps)), 4)})

    a.out_dir.mkdir(parents=True, exist_ok=True)
    r1, r2 = pd.DataFrame(rows), pd.DataFrame(pv_rows)
    r1.to_csv(a.out_dir / "region_pooled.csv", index=False, encoding="utf-8-sig")
    r2.to_csv(a.out_dir / "region_per_view.csv", index=False, encoding="utf-8-sig")
    print("\n[区域级 pooled]"); print(r1.to_string(index=False))
    print("\n[区域级 per-view AP]"); print(r2.to_string(index=False))
    print(f"\n[导出] {a.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
