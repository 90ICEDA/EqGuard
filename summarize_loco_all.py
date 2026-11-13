#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
summarize_loco_all.py — 对全部 fold 跑 `summarize_loco.py` 并汇总成一张跨 fold 的两侧对照总表

输出：
  results/ALLFOLDS_<mode>_loco_bygroup<suffix>.csv   每 (fold, group) 一行（含 AP_O/AP_T/PR_Drop/CI/Wilcoxon）
  results/ALLFOLDS_<mode>_loco_foldmacro<suffix>.csv 每 (fold) 一行的组间对比（G2/G3/G4 − G1 的 AP_T / PR_Drop）
用法：
  python summarize_loco_all.py --fold-mode fold --suffix _amp
  python summarize_loco_all.py --fold-mode loco --suffix _amp --folds single_to_composed_d2
"""

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
FOLDS = ["single_to_composed_d2", "single_to_composed_d3",
         "heldout_single_decomp", "heldout_single_balance",
         "heldout_single_refactor", "heldout_single_resub",
         "heldout_composed_decomp", "heldout_composed_balance",
         "heldout_composed_refactor", "heldout_composed_resub"]
GROUPS = ["G1_OrigOnly", "G2_EqAug", "G3_RandCons", "G4_PredHard"]


def main():
    ap = argparse.ArgumentParser(description="跨 fold 两侧对照汇总")
    ap.add_argument("--fold-mode", choices=["fold", "loco"], default="fold")
    ap.add_argument("--suffix", type=str, default="_amp")
    ap.add_argument("--folds", type=str, default="")
    ap.add_argument("--python", type=str, default="")
    args = ap.parse_args()
    folds = ([f.strip() for f in args.folds.split(",") if f.strip()] if args.folds.strip()
             else FOLDS)
    py = args.python.strip() or sys.executable

    parts, missing = [], []
    for fold in folds:
        # 该 fold 是否已有 loco_summary.csv（取决于是否重跑过）
        runs = list((CUR / "results").glob(f"{fold}_seed*_*_{args.fold_mode}_*{args.suffix}"))
        if not runs:
            missing.append(fold)
            continue
        rc = subprocess.call([py, "-X", "utf8", str(CUR / "summarize_loco.py"),
                              "--fold", fold, "--fold-mode", args.fold_mode,
                              "--suffix", args.suffix],
                             cwd=str(CUR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        p = CUR / "results" / f"{fold}_{args.fold_mode}_loco_bygroup{args.suffix}.csv"
        if rc == 0 and p.exists():
            d = pd.read_csv(p)
            d.insert(0, "Fold", fold)
            parts.append(d)
        else:
            missing.append(fold)

    if not parts:
        print("[ERROR] 没有任何可汇总的 fold（先跑 run_all_folds.py 重跑以生成 loco_summary.csv）")
        return 1
    allg = pd.concat(parts, ignore_index=True)
    out = CUR / "results" / f"ALLFOLDS_{args.fold_mode}_loco_bygroup{args.suffix}.csv"
    allg.to_csv(out, index=False, encoding="utf-8-sig")

    # 每 fold 的组间对比（以 G1 为基准）
    rows = []
    for fold, sub in allg.groupby("Fold"):
        sub = sub.set_index("Group")
        if "G1_OrigOnly" not in sub.index:
            continue
        row = {"Fold": fold, "AP_O_G1": sub.loc["G1_OrigOnly", "AP_O"],
               "AP_T_G1": sub.loc["G1_OrigOnly", "AP_T"]}
        for g in GROUPS[1:]:
            if g in sub.index:
                tag = g.split("_")[0]                      # G2 / G3 / G4
                row[f"AP_T_{tag}"] = sub.loc[g, "AP_T"]
                row[f"dAP_T_{tag}_vs_G1"] = sub.loc[g, "AP_T"] - sub.loc["G1_OrigOnly", "AP_T"]
                row[f"PR_Drop_{tag}"] = sub.loc[g, "PR_Drop"]
        if "G4_PredHard" in sub.index:
            row["Wilcoxon_G4"] = sub.loc["G4_PredHard", "Wilcoxon_P_AP"]
        rows.append(row)
    fm = pd.DataFrame(rows)
    out2 = CUR / "results" / f"ALLFOLDS_{args.fold_mode}_loco_foldmacro{args.suffix}.csv"
    fm.to_csv(out2, index=False, encoding="utf-8-sig")

    show = ["Fold", "AP_O_G1", "AP_T_G1", "AP_T_G2", "AP_T_G3", "AP_T_G4",
            "dAP_T_G2_vs_G1", "dAP_T_G3_vs_G1", "dAP_T_G4_vs_G1"]
    show = [c for c in show if c in fm.columns]
    print(f"\n=== {args.fold_mode} 模式：{len(fm)} 个 fold 的两侧对照（AP_O=原网表 / AP_T=变换视图）===")
    print(fm[show].round(4).to_string(index=False))
    if len(fm) > 1:
        print("\n=== 跨 fold 平均（每 fold 先算组内均值，再对 fold 平均）===")
        mac = {c: float(fm[c].mean()) for c in ["AP_O_G1", "AP_T_G1", "AP_T_G2", "AP_T_G3", "AP_T_G4"]
               if c in fm.columns}
        print({k: round(v, 4) for k, v in mac.items()})
        for g in ["G2", "G3", "G4"]:
            c = f"dAP_T_{g}_vs_G1"
            if c in fm.columns:
                print(f"  {g} − G1 的 AP_T 增益：{fm[c].mean():+.4f} ± {fm[c].std(ddof=1):.4f}"
                      f"（{int((fm[c] > 0).sum())}/{len(fm)} 个 fold 为正）")
    if missing:
        print(f"\n[WARN] 缺 loco_summary.csv 的 fold（需重跑）：{missing}")
    print(f"\n[OK] -> {out}\n     -> {out2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
