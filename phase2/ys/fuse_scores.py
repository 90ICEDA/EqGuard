"""fuse_scores.py —— A+B：GNN + LR + GBDT 分数融合（dev3）。

做法（全部在**测试节点**上 ✓，只用 train 节点训练 LR/GBDT ✓）：
  1. GNN 的 test 分数来自 `--dump-scores` 的 npz ✓；
  2. LR / GBDT 在 `train_mask` 节点上训练 ✓，预测 test 节点 ✓；
  3. 三者各自做 **rank 归一化**（per-test ✓，抗尺度差异 ✓），再加权平均 ✓；
  4. 报告 pooled AP / AUC / R@5% 与 per-view AP（median/mean/p90），并写 CSV ✓。
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from scipy.stats import rankdata
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]


def per_view(pos_map, y, te_idx, score, fids):
    """per-view AP ✓；`pos_map[global_idx] = 在测试数组里的位置` ✓（score 是测试数组 ✓）。"""
    idx = collections.defaultdict(list)
    for i, v in enumerate(fids):
        idx[v].append(i)
    out = []
    for v, ii in idx.items():
        ii = np.array(ii)
        ii = ii[pos_map[ii] >= 0]
        if len(ii) < 10:
            continue
        yy = y[ii]
        if not (0 < yy.sum() < len(yy)):
            continue
        out.append((v, float(average_precision_score(yy, score[pos_map[ii]])), int(yy.sum()), len(ii)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path, default=ROOT / "generate_trans/folds/_dev3/data/processed/trans_graph.pt")
    ap.add_argument("--gnn", type=Path, default=ROOT / "_devcfg/gnn_dev3.npz")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.15/03_特征与模型/特征诊断/dev3_fusion")
    a = ap.parse_args()

    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    y = np.asarray(d.y, np.int8)
    tr = np.asarray(d.train_mask, bool)
    te = np.asarray(d.test_mask, bool)
    fids = json.loads((a.pt.parents[2] / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))["file_ids"]

    rng = np.random.default_rng(0)
    ti = np.where(tr)[0]
    yi = y[ti]
    neg = rng.choice(np.where(yi == 0)[0], min(250000, int((yi == 0).sum())), replace=False)
    sel = np.concatenate([np.where(yi == 1)[0], neg])
    sc = StandardScaler().fit(X[ti][sel])
    lr = LogisticRegression(max_iter=1000, class_weight="balanced").fit(sc.transform(X[ti][sel]), yi[sel])
    gb = HistGradientBoostingClassifier(max_iter=300, random_state=0).fit(X[ti][sel], yi[sel])

    te_idx = np.where(te)[0]
    pos_map = np.full(len(y), -1, dtype=np.int64)
    pos_map[te_idx] = np.arange(len(te_idx))
    p_lr = lr.predict_proba(sc.transform(X[te_idx]))[:, 1]
    p_gb = gb.predict_proba(X[te_idx])[:, 1]

    g = np.load(a.gnn)
    gi = g["idx"].astype(np.int64)
    gs = g["score"].astype(np.float64)
    gmap = dict(zip(gi.tolist(), gs.tolist()))
    p_gnn = np.array([gmap.get(int(i), np.nan) for i in te_idx])
    have = ~np.isnan(p_gnn)
    print(f"[GNN] 覆盖测试节点 {have.sum()}/{len(te_idx)}")

    def rk(v):
        r = rankdata(v) / max(1, len(v))
        return r

    base = {k: rankdata(v) / max(1, len(v)) for k, v in
            (("LR", p_lr), ("GBDT", p_gb))}
    yt = y[te_idx]
    combos = {
        "LR": base["LR"], "GBDT": base["GBDT"],
        "GNN": rk(np.nan_to_num(p_gnn, nan=0.0)),
        "GNN+LR": 0.5 * rk(np.nan_to_num(p_gnn, nan=0.0)) + 0.5 * base["LR"],
        "GNN+GBDT": 0.5 * rk(np.nan_to_num(p_gnn, nan=0.0)) + 0.5 * base["GBDT"],
        "GNN+LR+GBDT": (rk(np.nan_to_num(p_gnn, nan=0.0)) + base["LR"] + base["GBDT"]) / 3,
    }
    rows, pv_rows = [], []
    for name, s in combos.items():
        k5 = int(len(te_idx) * 0.05)
        r5 = float(yt[np.argsort(-s)[:k5]].sum() / max(1, yt.sum()))
        rows.append({"model": name, "pooled_AP": round(float(average_precision_score(yt, s)), 4),
                     "AUC": round(float(roc_auc_score(yt, s)), 4), "R@5%": round(r5, 4)})
        pv = per_view(pos_map, y, te, s, fids)
        arr = np.array([x[1] for x in pv])
        pv_rows.append({"model": name, "views": len(arr), "median": round(float(np.median(arr)), 4),
                        "mean": round(float(arr.mean()), 4),
                        "p90": round(float(np.percentile(arr, 90)), 4),
                        "max": round(float(arr.max()), 4)})
    a.out_dir.mkdir(parents=True, exist_ok=True)
    r1 = pd.DataFrame(rows); r2 = pd.DataFrame(pv_rows)
    r1.to_csv(a.out_dir / "fusion_pooled.csv", index=False, encoding="utf-8-sig")
    r2.to_csv(a.out_dir / "fusion_per_view.csv", index=False, encoding="utf-8-sig")
    print("\n[pooled]"); print(r1.to_string(index=False))
    print("\n[per-view AP]"); print(r2.to_string(index=False))
    print(f"\n[导出] {a.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
