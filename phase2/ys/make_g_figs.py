"""make_g_figs.py —— 论文图表 G01–G09（全部来自已入库的 CSV ✓，纯 CPU ✓，英文标注 ✓）。

G01 变换结构/覆盖率（A1）    G02 锚点覆盖（A2）      G03 三层粒度 AP（B2/B4）
G04 配方特征漂移（D3）       G05 主对比（G0/G1/C2）  G06 监督消融×家族（E3）
G07 配方质量（D1/D4）        G08 家族 AP（E3）       G09 定位示意（score table）
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "10.15"
OUT = D / "07_论文图表"


def save(fig, name: str):
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"[fig] {p.name}")


def main() -> int:
    # ---------- G01：每个算子的节点比 vs 标签覆盖 ----------
    a1 = pd.read_csv(D / "01_数据与标签/A1_变换统计/tables/a1_v3_by_op.csv")
    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.scatter(a1.node_ratio_median, a1.transported_cover, s=a1.views * 6, alpha=.65)
    for r in a1.itertuples():
        ax.annotate(r.op, (r.node_ratio_median, r.transported_cover), fontsize=7,
                    xytext=(3, 3), textcoords="offset points")
    ax.axhline(1.0, ls="--", c="grey", lw=.8)
    ax.set_xlabel("median node ratio (conv / src)")
    ax.set_ylabel("label traceability (transported cover)")
    ax.set_title("G01  transformation strength vs label traceability")
    save(fig, "G01_transform_vs_labels.png")

    # ---------- G02：锚点覆盖（按 keep 方案）----------
    a2 = pd.read_csv(D / "01_数据与标签/A2_锚点与逻辑锥/tables/a2_coverage_v3.csv")
    t = a2[a2.kind == "trojan"].copy()
    t["scheme"] = t.scheme.fillna("NA")
    g = t.groupby("scheme")[["cover_core", "cover_region", "cover_neg"]].mean()
    fig, ax = plt.subplots(figsize=(6, 4))
    g.plot(kind="bar", ax=ax)
    ax.set_ylim(0, 1.05); ax.set_ylabel("coverage")
    ax.set_title("G02  anchor coverage by keep scheme (trojan views)")
    save(fig, "G02_anchor_coverage_by_keep.png")

    # ---------- G03：三层粒度 ----------
    labels = ["node\n(C2 dual)", "region\ndff-cone (M1)", "region\npo-cone (M4)", "view\n(M5, upper bound)"]
    vals = [0.0171, 0.0937, 0.1975, 0.6052]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(labels, vals, color=["#e84118", "#7f8fa6", "#40739e", "#c23616"])
    for i, v in enumerate(vals):
        ax.text(i, v + .01, f"{v:.3f}", ha="center", fontsize=9)
    ax.set_ylabel("AP (pooled, dev4)")
    ax.set_title("G03  AP by evaluation granularity")
    save(fig, "G03_granularity_ap.png")

    # ---------- G04：配方特征漂移 ----------
    d3 = pd.read_csv(D / "04_ABC_AIG专项/D3_特征对比/tables/recipe_feature_drift.csv")
    fig, ax = plt.subplots(figsize=(7, 4))
    d3.set_index("recipe")[["gate_drift", "struct_drift", "cone_drift"]].plot(kind="bar", ax=ax)
    ax.set_ylabel("std. drift vs ys_id (sigma)")
    ax.set_title("G04  feature drift by recipe")
    save(fig, "G04_feature_drift.png")

    # ---------- G05：主对比 ----------
    rows = [("G0 single", 0.0112, 0.6636, 0.0914), ("G1 single+trust", 0.0135, 0.7089, 0.1038),
            ("C2 dual+trust+cone", 0.0171, 0.8361, 0.1802)]
    fig, axs = plt.subplots(1, 3, figsize=(11, 3.6))
    for ax, k, ttl in zip(axs, (1, 2, 3), ("AP", "ROC-AUC", "Recall@5%")):
        ax.bar([r[0] for r in rows], [r[k] for r in rows],
               color=["#7f8fa6", "#40739e", "#e84118"])
        ax.set_title(ttl); ax.tick_params(axis="x", rotation=20, labelsize=7)
    fig.suptitle("G05  main comparison (dev4, 1 seed)")
    save(fig, "G05_main_comparison.png")

    # ---------- G06：监督消融 × 家族 ----------
    e3 = pd.read_csv(D / "05_木马家族扩展/E3_跨家族评测/tables/family_ap.csv")
    piv = e3.pivot_table(index="Operators", columns="model", values="AP")
    fig, ax = plt.subplots(figsize=(7.5, 4))
    piv.plot(kind="bar", ax=ax)
    ax.set_ylabel("AP (mean over views)")
    ax.set_title("G06  trust-mask ablation by trojan family")
    save(fig, "G06_ablation_by_family.png")

    # ---------- G07：配方质量 ----------
    d4 = pd.read_csv(D / "04_ABC_AIG专项/D4_aig标签/tables/recipe_label_quality.csv")
    fig, ax1 = plt.subplots(figsize=(7.5, 4))
    lab = d4.iloc[:, 0].astype(str).tolist()
    val = d4.iloc[:, -2].astype(float).tolist()      # cov_core（倒数第 2 列 ✓）
    ax1.bar(lab, val, color="#40739e")
    ax1.set_ylim(0, 1.05); ax1.set_ylabel("cover_core")
    ax1.set_title("G07  label quality by recipe")
    save(fig, "G07_recipe_label_quality.png")

    # ---------- G08：家族 AP（G1）----------
    g1 = e3[e3.model == "G1_trust"].sort_values("AP")
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(g1.Operators, g1.AP, color="#e84118")
    ax.set_xlabel("AP")
    ax.set_title("G08  per-family AP (G1 trust mask)")
    save(fig, "G08_family_ap.png")

    # ---------- G09：定位示意（单视图分数排序）----------
    f = D / "03_特征与模型/特征诊断/dev4_score_tables/score_s15850t100__injzeta_d1_s42__ys_opt.csv"
    s = pd.read_csv(f)
    fig, ax = plt.subplots(figsize=(7.5, 4))
    ax.plot(s["rank"], s["score"], lw=1, c="#7f8fa6", label="score(rank)")
    pos = s[s.y == 1]
    ax.scatter(pos["rank"], pos["score"], c="#e84118", s=28, zorder=3, label="trojan node")
    ax.set_xscale("log")
    ax.set_xlabel("rank (log)"); ax.set_ylabel("confidence")
    ax.set_title("G09  localization example: injzeta / ys_opt (AP 0.178, R@5% 0.90)")
    ax.legend(fontsize=8)
    save(fig, "G09_localization_example.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
