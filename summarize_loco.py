#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
summarize_loco.py — 把各 run 的 `loco_summary.csv` 汇总成**任务2 旧形态**的两侧对照表

输入：`results/<fold>_seed*_..._<fold_mode>_<group>*<suffix>/loco_summary.csv`
      （由 `train_test2.3.py` 的 `write_loco_summary()` 产出：ORIG 行 + TRANS 行 + 统计尾部）
输出：
  results/<fold>_<fold_mode>_loco_bygroup<suffix>.csv    每组一行：AP_O/AP_T/PR_Drop/一致性 + CI + Wilcoxon
  results/<fold>_<fold_mode>_loco_bycircuit<suffix>.csv  每 (组, 电路, seed) 一行（电路级宏平均）
  results/<fold>_<fold_mode>_loco_byseed<suffix>.csv     每 (组, seed) 一行（看 seed 波动）

口径与 2.2 的 `detailed_loco_summary.csv` 一致：
  * ORIG 侧按 **网表 stem** 关联（`<stem>_ORIG`），同电路所有视图共用同一份；
  * TRANS 侧按视图 → 电路级 = 该电路所有视图先平均；
  * `PR_Drop = AP_O − AP_T`（>0 表示变换后 AP 下降）；`Consistency_Gap = |PR_Drop|`；
  * 统计：电路级 bootstrap 95% CI（1000 次重采样）+ 电路级配对 Wilcoxon。

用法：
  python summarize_loco.py --fold single_to_composed_d2 --suffix _amp
  python summarize_loco.py --fold single_to_composed_d2 --fold-mode loco --suffix _amp
"""

import argparse
import glob
import re
from pathlib import Path

import numpy as np
import pandas as pd

CUR = Path(__file__).resolve().parent
GROUPS = ["G1_OrigOnly", "G2_EqAug", "G3_RandCons", "G4_PredHard"]
METRICS = ["AP_O", "AP_T", "ROC-AUC_O", "ROC-AUC_T", "Recall_O", "Recall_T", "FPR_O", "FPR_T",
           "Recall@1%_O", "Recall@1%_T", "Recall@2%_O", "Recall@2%_T",
           "Recall@5%_O", "Recall@5%_T", "PR_Drop", "Consistency_Gap",
           "Anchor_AP_Orig", "Anchor_AP_Trans", "Paired_MAE", "Paired_MAE_PerOrig",
           "Flip_Rate", "Flip_Rate_PerOrig", "Spearman_Corr", "Spearman_Corr_PerOrig",
           "Trojan_Drift", "Benign_Drift", "TopK_Overlap"]


def bootstrap_ci(data, n_boot=1000, seed=0):
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    if len(data) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = [rng.choice(data, size=len(data), replace=True).mean() for _ in range(n_boot)]
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def load_runs(fold, fold_mode, suffix):
    """返回 {group: [(seed, DataFrame), ...]}"""
    out = {}
    pat = str(CUR / "results" / f"{fold}_seed*_*_{fold_mode}_*{suffix}" / "loco_summary.csv")
    for p in sorted(glob.glob(pat)):
        run = Path(p).parent.name
        m = re.search(r"_seed(\d+)", run)
        seed = int(m.group(1)) if m else -1
        grp = next((g for g in GROUPS if run.endswith(g + suffix)), None) or run
        df = pd.read_csv(p)
        out.setdefault(grp, []).append((seed, df[df["Type"].isin(["ORIG", "TRANS"])]))
    return out


def main():
    ap = argparse.ArgumentParser(description="LOCO/两侧对照汇总（旧形态）")
    ap.add_argument("--fold", required=True)
    ap.add_argument("--fold-mode", choices=["fold", "loco"], default="fold")
    ap.add_argument("--suffix", type=str, default="_amp")
    ap.add_argument("--seeds", type=str, default="")
    args = ap.parse_args()

    runs = load_runs(args.fold, args.fold_mode, args.suffix)
    if not runs:
        print(f"[ERROR] 没找到 {args.fold} 的 loco_summary.csv（fold_mode={args.fold_mode}）")
        return 1
    keep = {int(s) for s in args.seeds.split(",") if s.strip()} if args.seeds.strip() else None

    by_seed_rows, by_circ_rows = [], []
    for grp in GROUPS:
        if grp not in runs:
            continue
        for seed, df in runs[grp]:
            if keep and seed not in keep:
                continue
            tr = df[df.Type == "TRANS"]
            og = df[df.Type == "ORIG"].set_index("Test_File")
            for circ, sub in tr.groupby("Circuit"):
                row = {"Group": grp, "Seed": seed, "Circuit": circ, "N_Views": int(len(sub))}
                stem = f"{str(sub['Test_File'].iloc[0]).split('__')[0]}_ORIG"
                if stem in og.index:
                    for k in METRICS:
                        if k.endswith("_O") and k in og.columns:
                            row[k] = float(og.loc[stem, k])
                for k in METRICS:
                    if k in sub.columns and not k.endswith("_O"):
                        row[k] = float(sub[k].mean())
                by_circ_rows.append(row)

    circ_df = pd.DataFrame(by_circ_rows)
    if circ_df.empty:
        print("[ERROR] 汇总为空")
        return 1
    for grp, sub in circ_df.groupby("Group"):
        m = sub.groupby("Seed")[METRICS].mean(numeric_only=True)
        by_seed_rows += [{"Group": grp, "Seed": s, **m.loc[s].to_dict()} for s in m.index]

    rows = []
    for grp, sub in circ_df.groupby("Group"):
        per_circ = sub.groupby("Circuit")[METRICS].mean(numeric_only=True)
        row = {"Group": grp, "N_Seeds": int(sub.Seed.nunique()), "N_Circuits": int(len(per_circ)),
               "N_Views": int(sub.N_Views.sum() / max(1, sub.Seed.nunique()))}
        for k in METRICS:
            if k in per_circ.columns:
                row[k] = float(per_circ[k].mean())
                row[f"{k}_std"] = float(per_circ[k].std(ddof=1)) if len(per_circ) > 1 else np.nan
                lo, hi = bootstrap_ci(per_circ[k].values, seed=0)
                row[f"{k}_ci_lo"], row[f"{k}_ci_hi"] = lo, hi
        p = np.nan
        try:
            if {"AP_O", "AP_T"}.issubset(per_circ.columns):
                v_o = per_circ["AP_O"].values.astype(float)
                v_t = per_circ["AP_T"].values.astype(float)
                mk = ~(np.isnan(v_o) | np.isnan(v_t))
                if mk.sum() >= 2 and not np.array_equal(v_o[mk], v_t[mk]):
                    from scipy.stats import wilcoxon
                    _, p = wilcoxon(v_o[mk], v_t[mk])
        except Exception as e:      # noqa: BLE001
            print(f"[WARN] Wilcoxon 失败: {e}")
        row["Wilcoxon_P_AP"] = float(p)
        rows.append(row)
    grp_df = pd.DataFrame(rows)
    seed_df = pd.DataFrame(by_seed_rows)

    meta = f"{args.fold}_{args.fold_mode}"
    out_g = CUR / "results" / f"{meta}_loco_bygroup{args.suffix}.csv"
    out_c = CUR / "results" / f"{meta}_loco_bycircuit{args.suffix}.csv"
    out_s = CUR / "results" / f"{meta}_loco_byseed{args.suffix}.csv"
    grp_df.sort_values("Group").to_csv(out_g, index=False, encoding="utf-8-sig")
    circ_df.sort_values(["Group", "Circuit", "Seed"]).to_csv(out_c, index=False, encoding="utf-8-sig")
    seed_df.sort_values(["Group", "Seed"]).to_csv(out_s, index=False, encoding="utf-8-sig")

    show = ["Group", "N_Seeds", "N_Circuits", "AP_O", "AP_T", "PR_Drop", "Consistency_Gap",
            "Recall@5%_O", "Recall@5%_T", "Paired_MAE", "Flip_Rate", "Spearman_Corr"]
    show = [c for c in show if c in grp_df.columns]
    print(f"\n=== {meta}：两侧对照（AP_O=原网表，AP_T=变换视图；PR_Drop = AP_O − AP_T）===")
    print(grp_df.sort_values("Group")[show].round(4).to_string(index=False))
    if "AP_T_ci_lo" in grp_df.columns:
        ci = grp_df.sort_values("Group")[["Group", "AP_O", "AP_O_ci_lo", "AP_O_ci_hi",
                                          "AP_T", "AP_T_ci_lo", "AP_T_ci_hi", "Wilcoxon_P_AP"]]
        print("\n=== 电路级 bootstrap 95% CI + 配对 Wilcoxon ===")
        print(ci.round(4).to_string(index=False))
    print(f"\n[OK] -> {out_g}\n     -> {out_c}\n     -> {out_s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
