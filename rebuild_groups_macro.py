#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rebuild_groups_macro.py — 从已有结果目录重建 4 组 MACRO 对照表（不重训）

用法：
  python rebuild_groups_macro.py <fold> <seed> [<输出 csv 名>] [--fold-mode fold|loco] [--suffix _amp]
例：
  python rebuild_groups_macro.py single_to_composed_d2 42                       # fold 模式（旧命名）
  python rebuild_groups_macro.py single_to_composed_d2 42 --fold-mode loco --suffix _amp
"""

import argparse
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
MACRO_KEYS = ["AP", "Anchor_AP_Orig", "Anchor_AP_Trans", "Recall@1%", "Recall@2%", "Recall@5%",
              "Paired_MAE", "Flip_Rate", "Spearman_Corr", "AP_O", "AP_T", "PR_Drop",
              "Consistency_Gap", "ROC-AUC", "Precision", "Recall", "FPR", "Macro-F1"]
GROUPS = ["G1_OrigOnly", "G2_EqAug", "G3_RandCons", "G4_PredHard"]


def main():
    ap = argparse.ArgumentParser(description="从结果目录重建 4 组 MACRO 表")
    ap.add_argument("fold", nargs="?", default="single_to_composed_d2")
    ap.add_argument("seed", nargs="?", type=int, default=42)
    ap.add_argument("out_name", nargs="?", default="")
    ap.add_argument("--fold-mode", choices=["fold", "loco"], default="fold")
    ap.add_argument("--suffix", type=str, default="", help="tag 后缀（如 _amp）")
    args = ap.parse_args()
    fold, seed = args.fold, args.seed
    mode_tag = "" if args.fold_mode == "fold" else f"_{args.fold_mode}"
    out = CUR / "results" / (args.out_name if args.out_name else
                             f"{fold}_seed{seed}_groups_macro{args.suffix}{mode_tag}.csv")
    rows = []
    for tag in GROUPS:
        pat = f"{fold}_seed{seed}mode*_{args.fold_mode}_*{tag}{args.suffix}"
        cand = sorted((CUR / "results").glob(pat))
        if not cand:
            print(f"[WARN] 找不到 {tag} 的结果目录（{pat}），跳过")
            continue
        cl = cand[-1] / "circuit_level_summary.csv"
        if not cl.exists():
            print(f"[WARN] {cand[-1].name} 缺 circuit_level_summary.csv，跳过")
            continue
        df = pd.read_csv(cl)
        macro = df[df["Circuit"] == "MACRO_MEAN"]
        row = {"Group": tag, "Fold": fold, "Seed": seed, "Result_Dir": cand[-1].name,
               "Fold_Mode": args.fold_mode, "N_Circuits": int(df["Circuit"].nunique() - 1)}
        for k in MACRO_KEYS + ["ROC-AUC", "Precision", "Recall", "FPR", "Macro-F1",
                               "Anchor_Coverage", "Recall@2%"]:
            if k in macro.columns:
                row[k] = float(macro.iloc[0][k])
        rows.append(row)
    if not rows:
        return 1
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[OK] -> {out}")
    print(pd.DataFrame(rows)[["Group"] + MACRO_KEYS].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
