"""make_g03_g05_3seed.py —— G03/G05 的**多种子版**（均值 ± std ✓）。

数据来源（都不含手填数字 ✓）：
  * `region_eval_seeds.py` 的 `region_seeds.csv`：v3.1 fold 每个 seed 的
      node / DFF 锥 / PO 锥 / 视图 四种粒度（逐视图均值 AP ✓ + pooled AP ✓）；
  * `make_g10_seedbars.py` 的 `G10_seed_bars.csv`：dev4 上 G0 / G1 / C2 的单 seed 结果
      （dev4 每个变体只训过 1 个 seed ✗ → 图上**必须**标注 n=1 ✓，不能画假的误差棒 ✗）。

产出：
  `G03_granularity_3seed.png`  四粒度 AP（v3.1，3 seed 误差棒 ✓）
  `G05_main_3seed.png`        (a) dev4 消融链 n=1 ⚠️  (b) v3.1 全量基线 n=3 ✓
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "10.15" / "07_论文图表"
GRAIN = [("view_ap", "Node (per-view)"), ("dff_view_ap", "DFF cone"),
         ("po_cone_view_ap", "PO cone"), ("view_pooled_ap", "Whole view (pooled)")]


def bars(ax, labels, vals, color="#4C78A8", hatch=None):
    xs = np.arange(len(labels))
    means = [float(np.nanmean(v)) for v in vals]
    stds = [float(np.nanstd(v, ddof=1)) if len(v) > 1 else 0.0 for v in vals]
    ax.bar(xs, means, yerr=stds, capsize=4, width=0.55, color=color,
           edgecolor="black", linewidth=0.6, hatch=hatch)
    for xi, m in enumerate(means):
        ax.text(xi, m + 0.008, f"{m:.3f}", ha="center", fontsize=8)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    return means, stds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region-csv", type=Path, required=True)
    ap.add_argument("--dev4-csv", type=Path, default=OUT / "tables" / "G10_seed_bars.csv")
    ap.add_argument("--out-dir", type=Path, default=OUT)
    a = ap.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    tdir = a.out_dir / "tables"
    tdir.mkdir(parents=True, exist_ok=True)

    reg = pd.read_csv(a.region_csv)
    n = len(reg)

    # ---------- G03（v3.1，3 seed ✓）----------
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    vals = [reg[k].to_numpy(float) for k, _ in GRAIN]
    means, stds = bars(ax, [lb for _, lb in GRAIN], vals, color="#40739e")
    ax.set_ylabel("Per-view AP (mean ± std)")
    ax.set_title(f"G03 — Region granularity (v3.1 fold, {n} seeds, "
                 f"{int(reg['view_ap'].notna().sum())} seeds)", fontsize=10)
    ax.set_ylim(0, max(means) * 1.35 + 0.02)
    fig.tight_layout()
    fig.savefig(a.out_dir / "G03_granularity_3seed.png", dpi=150)
    plt.close(fig)
    pd.DataFrame({"granularity": [lb for _, lb in GRAIN], "mean": means, "std": stds,
                  "n": [n] * len(GRAIN), "key": [k for k, _ in GRAIN]}).to_csv(
        tdir / "G03_granularity_3seed.csv", index=False, encoding="utf-8-sig")
    print(f"[fig] G03_granularity_3seed.png  " +
          "  ".join(f"{lb}={m:.3f}±{s:.3f}" for (_, lb), m, s in zip(GRAIN, means, stds)))

    # ---------- G05 ----------
    fig, axs = plt.subplots(1, 2, figsize=(11.5, 4.0))
    # (a) dev4 消融链（n=1 ⚠️）
    if a.dev4_csv.exists():
        d4 = pd.read_csv(a.dev4_csv)
        order = [x for x in ["G0", "G1", "C2_dual"] if x in set(d4["series"])]
        labels = []
        series = []
        for sname in order:
            sub = d4[d4["series"] == sname]
            labels.append(f"{sname}\n(n={len(sub)})")
            series.append(sub["view_ap"].to_numpy(float))
        if series:
            bars(axs[0], labels, series, color="#7f8fa6", hatch="//")
            axs[0].set_title("(a) dev4 ablation chain — n=1 ⚠️ (no seed bars)", fontsize=10)
            axs[0].set_ylabel("Per-view AP")
            axs[0].set_ylim(0, max(float(np.nanmax(v)) for v in series) * 1.35 + 0.01)
    # (b) v3.1 全量基线（n=3 ✓）
    eq = reg["view_ap"].to_numpy(float)
    bars(axs[1], [f"EquiGuard\nv3.1 fold\n(n={len(eq)})"], [eq], color="#e84118")
    axs[1].set_title("(b) full fold baseline — mean ± std ✓", fontsize=10)
    axs[1].set_ylim(0, float(np.nanmax(eq)) * 1.35 + 0.01)
    fig.suptitle("G05 — Main comparison: ablation chain (single seed) vs 3-seed baseline",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(a.out_dir / "G05_main_3seed.png", dpi=150)
    plt.close(fig)

    rows = []
    if a.dev4_csv.exists():
        d4 = pd.read_csv(a.dev4_csv)
        for _, r in d4.iterrows():
            rows.append({"panel": "a", "series": r["series"], "n": 1,
                         "view_ap": r["view_ap"], "view_auc": r["view_auc"], "r5": r["r5"]})
    rows.append({"panel": "b", "series": "EquiGuard_v31", "n": len(eq),
                 "view_ap": float(np.nanmean(eq)), "view_auc": float(np.nanmean(reg["view_auc"])),
                 "r5": float(np.nanmean(reg["r5"]))})
    pd.DataFrame(rows).to_csv(tdir / "G05_main_3seed.csv", index=False, encoding="utf-8-sig")
    print(f"[fig] G05_main_3seed.png  v3.1 view_AP={float(np.nanmean(eq)):.4f}±"
          f"{float(np.nanstd(eq, ddof=1)):.4f} (n={len(eq)})")
    print(f"[csv] {tdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
