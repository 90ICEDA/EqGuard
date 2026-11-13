#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_identity_control.py — 任务3 控制①：Identity vs 真实变换（同一 test 集）

输入：
  results/identity_control_seed*_groups_macro_identity.csv   （train = 原网表本身，edit_count=0）
  results/single_to_composed_d2_seed*_groups_macro_amp.csv   （train = 真实 d1 变换；test 完全相同）
判定：
  identity 组的增益（Gk − G1）若 ≈ 0，而真实变换组显著为正 ⇒ 增益来自**真实变换**，不是"多喂视图"。

输出：results/identity_control_vs_real_transform.csv + 终端表
用法：python analyze_identity_control.py
"""

import glob
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
GROUPS = ["G1_OrigOnly", "G2_EqAug", "G3_RandCons", "G4_PredHard"]
METRICS = ["AP", "Anchor_AP_Trans", "Recall@5%", "Paired_MAE", "Flip_Rate", "Spearman_Corr"]


def load(pattern):
    files = sorted(glob.glob(str(CUR / "results" / pattern)))
    if not files:
        raise SystemExit(f"[ERROR] 没有匹配的文件：{pattern}")
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def main():
    ctl = load("identity_control_seed*_groups_macro_identity.csv")
    real = load("single_to_composed_d2_seed*_groups_macro_amp.csv")

    piv_c = ctl.pivot_table(index="Seed", columns="Group", values="AP")
    piv_r = real.pivot_table(index="Seed", columns="Group", values="AP")
    rows = []
    for m in METRICS:
        pc = ctl.pivot_table(index="Seed", columns="Group", values=m)
        pr = real.pivot_table(index="Seed", columns="Group", values=m)
        row = {"Metric": m, "G1_identity": round(float(pc["G1_OrigOnly"].mean()), 4),
               "G1_real": round(float(pr["G1_OrigOnly"].mean()), 4)}
        for g in GROUPS[1:]:
            d_c = (pc[g] - pc["G1_OrigOnly"])
            d_r = (pr[g] - pr["G1_OrigOnly"])
            row[f"gain_ident_{g[1:3]}"] = f"{d_c.mean():+.4f} ± {d_c.std(ddof=1):.4f}"
            row[f"gain_real_{g[1:3]}"] = f"{d_r.mean():+.4f} ± {d_r.std(ddof=1):.4f}"
        rows.append(row)
    out = pd.DataFrame(rows)
    dest = CUR / "results" / "identity_control_vs_real_transform.csv"
    out.to_csv(dest, index=False, encoding="utf-8-sig")

    print("=== 每 seed 的 MACRO AP（identity 训练 vs 真实变换训练；test 完全相同）===")
    print(pd.concat({"identity": piv_c, "real_transform": piv_r},
                    axis=1).round(4).to_string())
    print("\n=== 组内增益（Gk − G1，跨 seed 均值 ± std）===")
    print(out[["Metric", "G1_identity", "G1_real"] +
              [c for c in out.columns if c.startswith(("gain_ident", "gain_real"))]].to_string(index=False))
    print(f"\n[OK] -> {dest}")

    # 判定
    d_ident = (piv_c["G4_PredHard"] - piv_c["G1_OrigOnly"])
    d_real = (piv_r["G4_PredHard"] - piv_r["G1_OrigOnly"])
    print("\n=== 判定（AP，G4 − G1）===")
    print(f"  identity 训练：{d_ident.mean():+.4f} ± {d_ident.std(ddof=1):.4f}"
          f"（{(d_ident > 0).sum()}/{len(d_ident)} 个 seed 为正）")
    print(f"  真实变换训练：{d_real.mean():+.4f} ± {d_real.std(ddof=1):.4f}"
          f"（{(d_real > 0).sum()}/{len(d_real)} 个 seed 为正）")
    gap = d_real.mean() - d_ident.mean()
    print(f"  两者之差：{gap:+.4f} → "
          + ("增益来自真实变换（identity 近似无增益）" if gap > 0.02 and abs(d_ident.mean()) < 0.02
             else "需要进一步检查（identity 也有可观增益）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
