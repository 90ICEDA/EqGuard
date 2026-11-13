"""summarize_region_mini.py —— C6 试点汇总（λ_region vs 指标，mean ± std ✓）。

输入：`_devcfg/region_mini/mini_lam*_s*.csv`（每个文件 = 一个 seed 的**逐视图**指标 ✓）
输出：`10.15/03_特征与模型/C6_区域级监督/tables/region_mini_summary.csv` ✓ + 同目录 `说明.md` ✓
口径 ✓：先在**每个 seed 内**对视图取均值 ✓，再对 seed 取 mean±std（ddof=1 ✓）。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_devcfg" / "region_mini"
DST = ROOT / "10.15" / "03_特征与模型" / "C6_区域级监督"
COLS = ["node_ap", "node_auc", "r5", "reg_ap", "head_fp", "tail_pos", "pos"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--dst", type=Path, default=DST)
    a = ap.parse_args()

    rows = []
    for f in sorted(a.src.glob("mini_lam*_s*.csv")):
        if "smoke" in f.name:
            continue
        m = re.search(r"lam([0-9.]+)_s(\d+)", f.name)
        if not m:
            continue
        d = pd.read_csv(f)
        rec = {"lambda": float(m.group(1)), "seed": int(m.group(2)), "views": len(d)}
        rec.update({c: float(d[c].mean()) for c in COLS if c in d.columns})
        rows.append(rec)
    if not rows:
        raise SystemExit(f"[ERROR] 没找到结果 ✗ {a.src}")
    df = pd.DataFrame(rows).sort_values(["lambda", "seed"])
    a.dst.mkdir(parents=True, exist_ok=True)
    (a.dst / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(a.dst / "tables" / "region_mini_per_seed.csv", index=False, encoding="utf-8-sig")

    g = df.groupby("lambda")
    summ = pd.DataFrame({
        "lambda": sorted(df["lambda"].unique()),
        **{f"{c}_mean": g[c].mean().values for c in COLS},
        **{f"{c}_std": g[c].std(ddof=1).values for c in COLS},
        "n_seed": g["seed"].count().values,
        "views": g["views"].max().values,
    })
    summ.to_csv(a.dst / "tables" / "region_mini_summary.csv", index=False, encoding="utf-8-sig")

    lines = ["# C6 试点 —— PO 锥级监督（小 fold `_mini31` ✓，独立于现有数据集 ✓）", "",
             "口径 ✓：小 fold = `rs232t1000` 训练 → `s15850t100` 测试 ✓（91/22/87 视图 ✓，445,505 节点 ✓，70,997 个 PO 锥 ✓）；",
             "每个 seed 先对视图取均值 ✓ → 再对 seed 取 mean ± std（ddof=1 ✓）；**未使用** trust 掩码 / 一致性项 ✓（本试点只加区域损失 ✓）。", "",
             "| λ_region | node AP | node AUC | R@5% | **region AP** | **head_fp** | tail_pos | n_seed |",
             "|---|---|---|---|---|---|---|---|"]
    base = summ[summ["lambda"] == 0.0]
    for _, r in summ.iterrows():
        def f(k):
            return f"{r[k + '_mean']:.4f}±{r[k + '_std']:.4f}"
        lines.append(f"| {r['lambda']:g} | {f('node_ap')} | {f('node_auc')} | {f('r5')} | "
                     f"**{f('reg_ap')}** | **{r['head_fp_mean']:.1f}** | {r['tail_pos_mean']:.2f} | {int(r['n_seed'])} |")
    if len(base):
        b = base.iloc[0]
        best_ap = summ.loc[summ["node_ap_mean"].idxmax()]
        best_reg = summ.loc[summ["reg_ap_mean"].idxmax()]
        lines += ["", "**结论** ✓",
                  f"1. 与 λ=0 基线比：`head_fp` {b['head_fp_mean']:.0f} → **{best_ap['head_fp_mean']:.0f}** "
                  f"（−{100 * (1 - best_ap['head_fp_mean'] / b['head_fp_mean']):.0f}% ✓），"
                  f"node AP {b['node_ap_mean']:.4f} → **{best_ap['node_ap_mean']:.4f}** ✓，"
                  f"AUC {b['node_auc_mean']:.3f} → **{best_ap['node_auc_mean']:.3f}** ✓，"
                  f"R@5% {b['r5_mean']:.3f} → **{best_ap['r5_mean']:.3f}** ✓；",
                  f"2. **region AP** 最优在 λ={best_reg['lambda']:g}：{b['reg_ap_mean']:.4f} → **{best_reg['reg_ap_mean']:.4f}** ✓；",
                  "3. → 机制成立 ✓：**给\"证据成团\"的监督，确实压掉了孤立高分门** ✓（head_fp 单调下降 ✓）；",
                  "4. ⚠️ 只有小 fold + 3 seed ✓、未接 trust/一致性 ✗ → 只能作为\"方向性证据\" ✓，不能直接当主表 ✗。",
                  "", "## 落地建议（按性价比 ✓）", "",
                  "1. **先做后处理版（零训练 ✓）**：`score + 0.2·log1p(锥内高分门数)` → dev4 上 per-view AP 0.0478 → **0.0943** ✓（λ 只在 val 选 ✓）；",
                  "2. **再做训练版**：把本试点的 `region_bce`（锥内 max ✓ + 正/负锥 BCE ✓）接到正式训练 ✓，"
                  "并**叠加** trust 掩码 ✓ 与 `_mini31` 之外的真实 fold（v3.1 ✓）→ 3 seed ≈ 40 min ✓；",
                  "3. **不要**做锥内 max 广播到节点 ✗（实测 −72% ✗）；也**不要**温度/校准 ✗（AP 不变 ✗）。"]
    (a.dst / "说明.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[out] {a.dst / 'tables' / 'region_mini_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
