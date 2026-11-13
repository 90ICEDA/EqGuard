"""analyze_feature_power.py —— 各特征在「木马 vs 非木马」上的区分力 + 分布图。

输出（`--out-dir` 下）：
  · `feat_power.csv`           每特征 AUC / Cohen's d / KS / 均值 / 非零率
  · `fig_feat_hist_grid.png`   39 个特征的分布（木马 vs 正常）
  · `fig_feat_auc_bar.png`     |AUC−0.5| 排名
  · `fig_feat_top_violin.png`  Top-12 violin
  · `feat_importance_lr.csv`   逻辑回归系数（标准化 ✓ 只用训练节点 ✓）
  · `feat_importance_group.csv` 分组汇总（门类型 one-hot vs 结构位）
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
N_GATE = 25
STRUCT = {25: "log1p_fanin", 26: "log1p_neighbors", 27: "touches_PI", 28: "touches_PO",
          29: "dist_to_PI", 30: "dist_to_PO", 31: "log1p_2hop_fanin",
          32: "log1p_2hop_fanout", 33: "dist_to_PI_reg", 34: "dist_to_PO_reg",
          35: "log1p_2hop_fanin_stage", 36: "log1p_2hop_fanout_stage",
          37: "in_cycle", 38: "scc_size"}


def feat_names(work: Path) -> list[str]:
    raw = json.loads((work / "gatelookup_recommended.json").read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "gatelookup" in raw:
        raw = raw["gatelookup"]
    cols = [k for k, _ in sorted(raw.items(), key=lambda kv: int(kv[1]))]
    return [f"gate:{c}" for c in cols[:N_GATE]] + [STRUCT[j] for j in range(N_GATE, N_GATE + 14)]


def main() -> int:
    ap = argparse.ArgumentParser(description="特征区分力分析（木马 vs 非木马）")
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/_mini31/data/processed/trans_graph.pt")
    ap.add_argument("--work", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.15" / "03_特征与模型" / "特征诊断")
    ap.add_argument("--max-neg", type=int, default=150000)
    a = ap.parse_args()

    work = a.work or a.pt.parents[2]
    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, dtype=np.float32)
    y = np.asarray(d.y, dtype=np.int8)
    tr = np.asarray(d.train_mask, dtype=bool)
    print(f"[数据] nodes={X.shape[0]} dims={X.shape[1]} pos={int(y.sum())} train_nodes={int(tr.sum())}")
    cols = feat_names(work)[: X.shape[1]]

    pos = np.where(y == 1)[0]
    neg = np.where(y == 0)[0]
    rng = np.random.default_rng(0)
    if len(neg) > a.max_neg:
        neg = rng.choice(neg, a.max_neg, replace=False)
    idx = np.concatenate([pos, neg])
    Xs, ys = X[idx], y[idx]
    Xp, Xn = Xs[ys == 1], Xs[ys == 0]

    rows = []
    for j, c in enumerate(cols):
        v = Xs[:, j]
        vp, vn = Xp[:, j], Xn[:, j]
        auc = float(roc_auc_score(ys, v)) if np.unique(v).size > 1 else 0.5
        sd = float(np.sqrt((vp.var() + vn.var()) / 2) + 1e-9)
        lo, hi = float(v.min()), float(v.max())
        hp, _ = np.histogram(vp, 64, (lo, hi))
        hn, _ = np.histogram(vn, 64, (lo, hi))
        ks = float(np.max(np.abs(np.cumsum(hp) / max(1, hp.sum()) - np.cumsum(hn) / max(1, hn.sum()))))
        rows.append({"feature": c, "idx": j, "auc": round(auc, 4),
                     "abs_auc_dev": round(abs(auc - 0.5), 4),
                     "cohens_d": round(float((vp.mean() - vn.mean()) / sd), 4),
                     "ks": round(ks, 4),
                     "pos_mean": round(float(vp.mean()), 4), "neg_mean": round(float(vn.mean()), 4),
                     "pos_nz": round(float((vp != 0).mean()), 4),
                     "neg_nz": round(float((vn != 0).mean()), 4)})
    pw = pd.DataFrame(rows).sort_values("abs_auc_dev", ascending=False)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    pw.to_csv(a.out_dir / "feat_power.csv", index=False, encoding="utf-8-sig")

    # ---- 39 图分布网格 ----
    ncol = 7
    nrow = int(np.ceil(len(cols) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.0 * ncol, 2.2 * nrow))
    for j, c in enumerate(cols):
        ax = axes[j // ncol, j % ncol]
        vp, vn = Xp[:, j], Xn[:, j]
        lo, hi = np.percentile(Xs[:, j], [0.5, 99.5])
        bins = np.linspace(lo, hi if hi > lo else lo + 1, 30)
        ax.hist(vn, bins=bins, density=True, alpha=.55, color="#7f8fa6", label="normal")
        ax.hist(vp, bins=bins, density=True, alpha=.65, color="#e84118", label="trojan")
        ax.set_title(f"{j:02d} {c}", fontsize=7)
        ax.tick_params(labelsize=6)
        if j == 0:
            ax.legend(fontsize=6)
    for k in range(len(cols), nrow * ncol):
        axes[k // ncol, k % ncol].axis("off")
    fig.suptitle("feature distribution: trojan vs normal (density)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(a.out_dir / "fig_feat_hist_grid.png", dpi=130)
    plt.close(fig)

    # ---- AUC 排名 ----
    top = pw.head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.barh(top.feature, top.abs_auc_dev, color="#e84118")
    ax.set_xlabel("|AUC - 0.5|")
    ax.set_title("univariate discriminative power")
    fig.tight_layout()
    fig.savefig(a.out_dir / "fig_feat_auc_bar.png", dpi=140)
    plt.close(fig)

    # ---- Top-12 violin ----
    topc = pw.head(12).feature.tolist()
    fig, axes = plt.subplots(3, 4, figsize=(12, 7.5))
    for i, c in enumerate(topc):
        j = cols.index(c)
        ax = axes[i // 4, i % 4]
        ax.violinplot([Xn[:, j], Xp[:, j]], showmedians=True)
        ax.set_xticks([1, 2])
        ax.set_xticklabels(["normal", "trojan"], fontsize=7)
        auc = float(pw.loc[pw.feature == c, "auc"].iloc[0])
        ax.set_title(f"{c} (AUC {auc:.3f})", fontsize=8)
    fig.tight_layout()
    fig.savefig(a.out_dir / "fig_feat_top_violin.png", dpi=130)
    plt.close(fig)

    # ---- 逻辑回归重要性（只用训练节点 ✓）----
    Xtr, ytr = X[tr], y[tr]
    cap = 400000
    if len(Xtr) > cap:
        sel = np.concatenate([np.where(ytr == 1)[0],
                              rng.choice(np.where(ytr == 0)[0], cap - int(ytr.sum()), replace=False)])
        Xtr, ytr = Xtr[sel], ytr[sel]
    Z = StandardScaler().fit_transform(Xtr)
    lr = LogisticRegression(max_iter=2000, class_weight="balanced")
    lr.fit(Z, ytr)
    coef = pd.DataFrame({"feature": cols[: Z.shape[1]],
                         "coef": np.round(lr.coef_[0], 4),
                         "abs_coef": np.round(np.abs(lr.coef_[0]), 4)}).sort_values("abs_coef", ascending=False)
    coef.to_csv(a.out_dir / "feat_importance_lr.csv", index=False, encoding="utf-8-sig")
    gm = np.array([c.startswith("gate:") for c in coef.feature])
    grp = pd.DataFrame([
        {"group": "gate_onehot(all)", "sum_abs_coef": round(float(coef.loc[gm, "abs_coef"].sum()), 3)},
        {"group": "structural(all 14)", "sum_abs_coef": round(float(coef.loc[~gm, "abs_coef"].sum()), 3)},
        {"group": "structural(top5)", "sum_abs_coef": round(float(coef.loc[~gm, "abs_coef"].head(5).sum()), 3)},
    ])
    grp.to_csv(a.out_dir / "feat_importance_group.csv", index=False, encoding="utf-8-sig")

    print("\n[Top-15 单变量]")
    print(pw.head(15)[["feature", "auc", "cohens_d", "pos_mean", "neg_mean", "pos_nz", "neg_nz"]]
          .to_string(index=False))
    print("\n[逻辑回归 Top-12]")
    print(coef.head(12).to_string(index=False))
    print("\n[分组]")
    print(grp.to_string(index=False))
    print(f"\n[导出] {a.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
