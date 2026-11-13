#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_groups.py — 4 组实验的配对差值分析 + CPU/GPU 设备敏感性对比

用法：
  python analyze_groups.py single_to_composed_d2                 # GPU 3-seed 配对分析
  python analyze_groups.py single_to_composed_d2 --suffix _gpu
  python analyze_groups.py single_to_composed_d2 --suffix _gpu --compare-cpu
"""

import argparse
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
METRICS = ["AP", "Anchor_AP_Trans", "Recall@1%", "Recall@5%", "Paired_MAE",
           "Flip_Rate", "Spearman_Corr"]
BASE = "G1_OrigOnly"


def load(fold, suffix):
    import glob
    pattern = str(CUR / "results" / f"{fold}_seed*_groups_macro{suffix}.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        return None
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def main():
    ap = argparse.ArgumentParser(description="4 组配对差值 + 设备敏感性")
    ap.add_argument("fold")
    ap.add_argument("--suffix", type=str, default="")
    ap.add_argument("--compare-cpu", action="store_true")
    args = ap.parse_args()

    df = load(args.fold, args.suffix)
    if df is None:
        print(f"[ERROR] 找不到 {args.fold}_seed*_groups_macro{args.suffix}.csv")
        return 1
    seeds = sorted(df.Seed.unique())
    print(f"输入 {len(df)} 行｜seeds={seeds}｜suffix='{args.suffix}'")

    print(f"\n=== 配对差值（相对 {BASE}，逐 seed 相减后取均值±std）===")
    rows = []
    for metric in METRICS:
        line = {"Metric": metric}
        piv = df.pivot(index="Seed", columns="Group", values=metric)
        for g in [c for c in piv.columns if c != BASE]:
            d = (piv[g] - piv[BASE]).dropna()
            line[f"{g}_vs_G1"] = (f"{d.mean():+.4f} ± {d.std(ddof=1):.4f}"
                                  if len(d) > 1 else f"{d.mean():+.4f}")
        line[f"{BASE}_mean"] = f"{piv[BASE].mean():.4f}"
        rows.append(line)
    print(pd.DataFrame(rows).to_string(index=False))

    if args.compare_cpu:
        cpu = load(args.fold, "")
        if cpu is None:
            print("[WARN] 没有 CPU 结果可比")
            return 0
        both = sorted(set(cpu.Seed) & set(df.Seed))
        print(f"\n=== CPU vs GPU（同 seed，seed={both}）MACRO AP ===")
        a = cpu[cpu.Seed.isin(both)].pivot(index="Seed", columns="Group", values="AP")
        b = df[df.Seed.isin(both)].pivot(index="Seed", columns="Group", values="AP")
        cmp = pd.concat({"cpu": a, "gpu": b, "gpu_minus_cpu": (b - a)}, axis=1).round(4)
        print(cmp.to_string())
        print(f"\n设备差（gpu-cpu）在 {len(both)} 个 seed × {a.shape[1]} 组上的 "
              f"|ΔAP| 均值 = {float((b - a).abs().mean().mean()):.4f}｜"
              f"最大 = {float((b - a).abs().max().max()):.4f}")
        print(f"CPU 上的组间排序（seed 逐个）：{[list(a.loc[s].sort_values().index) for s in a.index]}")
        print(f"GPU 上的组间排序（seed 逐个）：{[list(b.loc[s].sort_values().index) for s in b.index]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
