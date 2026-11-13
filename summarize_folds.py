#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
summarize_folds.py — 跨 fold 汇总：fold × 组 的 MACRO 表 + 逐 fold 配对差值

输入：results/<fold>_seed<seed>_groups_macro<suffix>.csv（run_fold_groups.py 产出）
输出：
  results/ALLFOLDS_groups_macro<suffix>.csv          每 (fold, group, seed) 一行
  results/ALLFOLDS_summary<suffix>.csv               每 (fold, group) 的均值±std + 配对差值
  results/ALLFOLDS_meanstd<suffix>.csv               按 fold 家族聚合的均值±std

用法：
  python summarize_folds.py --suffix _amp
  python summarize_folds.py --folds heldout_single_decomp,single_to_composed_d3 --suffix _amp
"""

import argparse
import glob
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
METRICS = ["AP", "Anchor_AP_Trans", "Recall@1%", "Recall@5%", "Paired_MAE",
           "Flip_Rate", "Spearman_Corr"]
BASE = "G1_OrigOnly"
GROUPS = ["G1_OrigOnly", "G2_EqAug", "G3_RandCons", "G4_PredHard"]


def family_of(fold: str) -> str:
    if fold.startswith("heldout_single"):
        return "operator_heldout_single"
    if fold.startswith("heldout_composed"):
        return "operator_heldout_composed"
    return "depth_generalization"


def main():
    ap = argparse.ArgumentParser(description="跨 fold 汇总（fold × 组 + 配对差值）")
    ap.add_argument("--suffix", type=str, default="_amp")
    ap.add_argument("--folds", type=str, default="")
    ap.add_argument("--out-prefix", type=str, default="ALLFOLDS")
    args = ap.parse_args()

    pat = str(CUR / "results" / f"*_seed*_groups_macro{args.suffix}.csv")
    files = sorted(glob.glob(pat))
    if args.folds.strip():
        keep = {f.strip() for f in args.folds.split(",") if f.strip()}
        files = [f for f in files if Path(f).name.split("_seed")[0] in keep]
    if not files:
        print(f"[ERROR] 没找到 {pat}")
        return 1

    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df = df.drop_duplicates(subset=["Fold", "Group", "Seed"], keep="last")
    df["Family"] = df["Fold"].map(family_of)
    df = df.sort_values(["Family", "Fold", "Group", "Seed"])
    out_all = CUR / "results" / f"{args.out_prefix}_groups_macro{args.suffix}.csv"
    df.to_csv(out_all, index=False, encoding="utf-8-sig")
    print(f"输入 {len(files)} 个文件 → {len(df)} 行｜fold 数 = {df.Fold.nunique()}")

    # fold × 组：均值±std + 相对 G1 的配对差值
    rows = []
    for (fam, fold, group), sub in df.groupby(["Family", "Fold", "Group"], sort=True):
        row = {"Family": fam, "Fold": fold, "Group": group, "N_Seeds": len(sub)}
        for m in METRICS:
            if m in sub.columns:
                row[f"{m}_mean"] = round(float(sub[m].mean()), 4)
                row[f"{m}_std"] = round(float(sub[m].std(ddof=1)), 4) if len(sub) > 1 else None
        if group != BASE:
            base = df[(df.Fold == fold) & (df.Group == BASE)][METRICS].reset_index(drop=True)
            cur = sub[METRICS].reset_index(drop=True)
            if len(base) == len(cur) and len(base) > 0:
                d = (cur - base)
                for m in METRICS:
                    row[f"{m}_paired_delta"] = round(float(d[m].mean()), 4)
                    row[f"{m}_paired_std"] = (round(float(d[m].std(ddof=1)), 4)
                                              if len(d) > 1 else None)
        rows.append(row)
    out_sum = CUR / "results" / f"{args.out_prefix}_summary{args.suffix}.csv"
    pd.DataFrame(rows).to_csv(out_sum, index=False, encoding="utf-8-sig")

    print("\n=== fold × 组：AP（均值 ± std）与配对 AP 差值 ===")
    tab = []
    for fold in df.Fold.unique():
        line = {"Fold": fold, "Family": family_of(fold)}
        for g in GROUPS:
            sub = df[(df.Fold == fold) & (df.Group == g)]
            if len(sub):
                line[g] = f"{sub.AP.mean():.4f}" + (f"±{sub.AP.std(ddof=1):.4f}" if len(sub) > 1 else "")
        base = df[(df.Fold == fold) & (df.Group == BASE)].AP.reset_index(drop=True)
        for g in GROUPS[1:]:
            sub = df[(df.Fold == fold) & (df.Group == g)].AP.reset_index(drop=True)
            if len(sub) == len(base) and len(sub):
                d = sub - base
                line[f"Δ{g[1:3]}"] = (f"{d.mean():+.4f}"
                                      + (f"±{d.std(ddof=1):.4f}" if len(d) > 1 else ""))
        tab.append(line)
    print(pd.DataFrame(tab).to_string(index=False))

    # 按 fold 家族聚合（先 fold 内平均，再家族平均）
    fam = df.groupby(["Family", "Group"])[METRICS].mean(numeric_only=True).round(4)
    out_fam = CUR / "results" / f"{args.out_prefix}_meanstd{args.suffix}.csv"
    fam.to_csv(out_fam, encoding="utf-8-sig")
    print("\n=== 家族级均值（先 fold 内平均，再家族平均）===")
    print(fam[["AP", "Anchor_AP_Trans", "Recall@5%", "Paired_MAE", "Flip_Rate",
               "Spearman_Corr"]].to_string())
    print(f"\n[OK] -> {out_all}\n     -> {out_sum}\n     -> {out_fam}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
