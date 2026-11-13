#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
summarize_seeds.py — 把多 seed 的 4 组结果汇总成「均值 ± 标准差」表

输入：results/<fold>_seed<seed>_groups_macro.csv（run_fold_groups.py 产出）
输出：results/<fold>_groups_macro_meanstd.csv + 终端表格

用法：
  python summarize_seeds.py single_to_composed_d2
  python summarize_seeds.py single_to_composed_d2 --seeds 42,43,44
"""

import argparse
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
KEYS = ["AP", "ROC-AUC", "Anchor_AP_Orig", "Anchor_AP_Trans", "Recall@1%", "Recall@2%",
        "Recall@5%", "Paired_MAE", "Paired_MAE_PerOrig", "Flip_Rate", "Flip_Rate_PerOrig",
        "Spearman_Corr", "Spearman_Corr_PerOrig"]


def main():
    ap = argparse.ArgumentParser(description="多 seed 4 组汇总（均值±std）")
    ap.add_argument("fold")
    ap.add_argument("--seeds", type=str, default="", help="逗号分隔；默认自动发现")
    ap.add_argument("--suffix", type=str, default="",
                    help="表名后缀（如 _gpu，对应 run_fold_groups.py --tag-suffix）")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    files = []
    if args.seeds.strip():
        for s in args.seeds.split(","):
            p = CUR / "results" / f"{args.fold}_seed{int(s)}_groups_macro{args.suffix}.csv"
            if p.exists():
                files.append(p)
            else:
                print(f"[WARN] 缺 {p.name}")
    else:
        files = sorted((CUR / "results").glob(f"{args.fold}_seed*_groups_macro{args.suffix}.csv"))
    if not files:
        print("[ERROR] 没找到任何 groups_macro.csv")
        return 1

    df = pd.concat([pd.read_csv(p) for p in files], ignore_index=True)
    df = df.sort_values(["Group", "Seed"])
    keys = [k for k in KEYS if k in df.columns]
    print(f"输入 {len(files)} 个 seed 文件：{[p.name for p in files]}")
    print(f"\n=== 各 seed 明细（{len(df)} 行）===")
    print(df[["Group", "Seed", "Result_Dir"] + keys[:8]].to_string(index=False))

    g = df.groupby("Group")[keys]
    mean = g.mean().round(4)
    std = g.std(ddof=1).round(4)
    n = g.size().rename("N_Seeds")
    out = mean.copy()
    for k in keys:
        out[k] = [f"{mean.loc[i, k]:.4f} ± {std.loc[i, k]:.4f}"
                  if pd.notna(std.loc[i, k]) else f"{mean.loc[i, k]:.4f}" for i in mean.index]
    out = pd.concat([n, out], axis=1)
    dest = args.out or (CUR / "results" / f"{args.fold}_groups_macro_meanstd{args.suffix}.csv")
    out.to_csv(dest, encoding="utf-8-sig")
    print(f"\n=== 均值 ± 标准差（{len(files)} seeds）===")
    print(out[["N_Seeds"] + [k for k in ["AP", "Anchor_AP_Trans", "Recall@1%", "Recall@5%",
                                         "Paired_MAE", "Flip_Rate", "Spearman_Corr"]
                             if k in out.columns]].to_string())
    print(f"\n[OK] -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
