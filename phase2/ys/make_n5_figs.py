"""make_n5_figs.py —— N5：论文图 F1 / F3 / F4 / F5（数据来自已入库 CSV/npz ✓，纯 CPU ✓）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "10.15"
OUT = D / "07_论文图表" / "figs"
COL = {"base": "#7f8fa6", "region": "#e84118", "ok": "#40739e"}
sys.path.insert(0, str(Path(__file__).resolve().parent))
from summarize_npz import score_one  # noqa: E402


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    fig.tight_layout()
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"[fig] {p.name}")


def f1() -> None:
    d = pd.read_csv(D / "01_数据与标签/A1_变换统计/tables/a1_v3_by_op.csv")
    d = d[d["views_with_pos"] > 0].copy()
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.scatter(d["node_ratio_median"], d["transported_cover"], s=60, c=COL["ok"], edgecolor="k")
    for _, r in d.iterrows():
        ax.annotate(r["op"], (r["node_ratio_median"], r["transported_cover"]),
                    fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel("node ratio (synthesized / original)")
    ax.set_ylabel("transported label coverage")
    ax.set_title("F1 — Synthesis strength vs label preservation", fontsize=10)
    ax.grid(alpha=0.3)
    save(fig, "F1_strength_vs_labelcover.png")


def f3() -> None:
    d = pd.read_csv(D / "04_ABC_AIG专项/D3_特征对比/tables/recipe_feature_drift.csv")
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    x = np.arange(len(d))
    w = 0.26
    for i, (c, lb) in enumerate((("gate_drift", "gate"), ("struct_drift", "struct"),
                                 ("cone_drift", "cone"))):
        ax.bar(x + (i - 1) * w, d[c], w, label=lb)
    ax.set_xticks(x)
    ax.set_xticklabels(d["recipe"], rotation=20, fontsize=8)
    ax.set_ylabel("feature drift (σ)")
    ax.set_title("F3 — Feature drift by recipe (cone drift outlier: abc)")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    save(fig, "F3_feature_drift.png")


def f4() -> None:
    p = D / "03_特征与模型/C6_区域级监督/tables/t12_region_loss_summary.csv"
    if not p.exists():
        print("[skip] F4：缺 t12_region_loss_summary.csv")
        return
    d = pd.read_csv(p).set_index("model")
    keys = [("view_ap", "Node"), ("dff_view_ap", "DFF cone"), ("po_cone_view_ap", "PO cone")]
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    x = np.arange(len(keys))
    w = 0.36
    for i, (m, lb) in enumerate((("base", "baseline"), ("region_l10", "+ region loss λ=10"))):
        vals = [float(d.loc[m, k + "_mean"]) for k, _ in keys]
        errs = [float(d.loc[m, k + "_std"]) for k, _ in keys]
        ax.bar(x + (i - 0.5) * w, vals, w, yerr=errs, capsize=4, label=lb,
               color=COL["base"] if m == "base" else COL["region"], edgecolor="k")
        for xi, v in zip(x + (i - 0.5) * w, vals):
            ax.text(xi, v + 0.008, f"{v:.3f}", ha="center", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels([lb for _, lb in keys])
    ax.set_ylabel("per-view AP (mean ± std, n=3)")
    ax.set_title("F4 — Granularity: region loss lifts all three levels")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    save(fig, "F4_granularity_regionloss.png")


def f5() -> None:
    csv = OUT.parent / "tables" / "F5_ablation_main.csv"
    if not csv.exists():
        print("[skip] F5：缺 F5_ablation_main.csv ✗（先用完整版跑一次 ✓）")
        return
    d = pd.read_csv(csv)
    fig, ax = plt.subplots(figsize=(7.4, 4.1))
    ax.bar(np.arange(len(d)), d["ap_mean"], yerr=d["ap_std"], capsize=4,
           color=[COL["region"] if "region" in m else COL["ok"] for m in d["model"]],
           edgecolor="k")
    top = float((d["ap_mean"] + d["ap_std"]).max())
    for i, r in d.iterrows():
        ax.text(i, r["ap_mean"] + r["ap_std"] + 0.004,
                f"{r['ap_mean']:.3f}\u00b1{r['ap_std']:.3f} (n={int(r['n'])})",
                ha="center", fontsize=6.5)
    ax.set_xticks(np.arange(len(d)))
    ax.set_xticklabels(d["model"], rotation=15, fontsize=8)
    ax.set_ylabel("per-view AP (mean ± std)")
    ax.set_ylim(0, top * 1.5)
    ax.set_title("F5 — Ablation on v3.1 (3 seeds, same budget)")
    ax.grid(axis="y", alpha=0.3)
    save(fig, "F5_ablation_main.png")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    want = {s.strip().upper() for s in a.only.split(",") if s.strip()} or {"F1", "F3", "F4", "F5"}
    for k, fn in (("F1", f1), ("F3", f3), ("F4", f4), ("F5", f5)):
        if k in want:
            fn()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
