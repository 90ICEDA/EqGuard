#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_budget_sweep.py — 视图预算扫描分析（budget ∈ {1,2,4,8} × 4 组 × 3 seed）

输入：
  results/<fold>_seed*_groups_macro_b<B>.csv    （run_budget_sweep.py / run_all_folds.py 产出，B∈{1,2,8}）
  results/<fold>_seed*_groups_macro_amp.csv     （budget=4 的主实验，即 `_amp`）
输出：
  results/<fold>_budget_sweep.csv：每个 (budget, group) 的 AP 均值±std、配对 Δ(Gk−G1)、一致性指标
  results/<fold>_budget_sweep_paired.csv：每个 seed 的 Δ(Gk−G1)，用于看预算与收益的关系
用法：python analyze_budget_sweep.py --fold single_to_composed_d2
"""

import argparse
import glob
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
GROUPS = ["G1_OrigOnly", "G2_EqAug", "G3_RandCons", "G4_PredHard"]
METRICS = ["AP", "Anchor_AP_Trans", "Recall@5%", "Paired_MAE", "Flip_Rate", "Spearman_Corr"]
BUDGETS = [1, 2, 4, 8]


def main():
    ap = argparse.ArgumentParser(description="视图预算扫描分析")
    ap.add_argument("--fold", type=str, default="single_to_composed_d2")
    ap.add_argument("--main-suffix", type=str, default="_amp",
                    help="budget=4 那批结果的 tag 后缀（默认 _amp）")
    args = ap.parse_args()

    frames = []
    for b in BUDGETS:
        suffix = args.main_suffix if b == 4 else f"_b{b}"
        files = sorted((CUR / "results").glob(f"{args.fold}_seed*_groups_macro{suffix}.csv"))
        if not files:
            print(f"[WARN] budget={b}（后缀 {suffix}）没有结果，跳过")
            continue
        d = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
        d["Budget"] = b
        frames.append(d)
    if not frames:
        raise SystemExit("[ERROR] 没有任何预算结果")
    df = pd.concat(frames, ignore_index=True)

    # 每 (budget, group)：跨 seed 的均值/配对差
    rows, paired = [], []
    for b, sub in df.groupby("Budget"):
        piv = sub.pivot_table(index="Seed", columns="Group", values="AP")
        if "G1_OrigOnly" not in piv.columns:
            continue
        for g in GROUPS:
            if g not in piv.columns:
                continue
            r = {"Budget": b, "Group": g, "N_Seeds": int(piv[g].notna().sum()),
                 "AP_mean": round(float(piv[g].mean()), 4),
                 "AP_std": round(float(piv[g].std(ddof=1)), 4) if len(piv) > 1 else None}
            if g != "G1_OrigOnly":
                d_ = piv[g] - piv["G1_OrigOnly"]
                r["dAP_vs_G1_mean"] = round(float(d_.mean()), 4)
                r["dAP_vs_G1_std"] = round(float(d_.std(ddof=1)), 4) if len(d_) > 1 else None
                for s in d_.index:
                    paired.append({"Budget": b, "Group": g, "Seed": int(s),
                                   "dAP_vs_G1": round(float(d_.loc[s]), 4)})
            for m in METRICS[1:]:
                pm = sub.pivot_table(index="Seed", columns="Group", values=m)
                if g in pm.columns:
                    r[m] = round(float(pm[g].mean()), 4)
            rows.append(r)
    out = pd.DataFrame(rows).sort_values(["Budget", "Group"])
    dest = CUR / "results" / f"{args.fold}_budget_sweep.csv"
    out.to_csv(dest, index=False, encoding="utf-8-sig")
    dest2 = CUR / "results" / f"{args.fold}_budget_sweep_paired.csv"
    pd.DataFrame(paired).to_csv(dest2, index=False, encoding="utf-8-sig")

    print(f"=== {args.fold}：视图预算扫描（每个 budget 内 4 组 × 3 seed；budget = 每电路每轮的训练视图数）===")
    show = ["Budget", "Group", "N_Seeds", "AP_mean", "AP_std", "dAP_vs_G1_mean",
            "Recall@5%", "Paired_MAE", "Flip_Rate", "Spearman_Corr"]
    print(out[[c for c in show if c in out.columns]].to_string(index=False))

    if paired:
        pv = pd.DataFrame(paired).pivot_table(index="Budget", columns="Group", values="dAP_vs_G1")
        print("\n=== 各预算下 Gk−G1 的 AP 增益（跨 3 seed 均值）===")
        print(pv.round(4).to_string())
    print(f"\n[OK] -> {dest}\n     -> {dest2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
