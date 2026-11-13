#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_plots.py — 一键出论文图（每个 fold：各 mode 的稳健性曲线 + 四组对比图）

调用 `plot_robustness.py`（单 mode）与 `plot_robustness_compare.py`（多 mode 对比），
用 `--runs-glob` 把每个图限制在单个 fold（否则 10 个 fold 会混在一张图里）。

用法：
  python make_plots.py                                   # 全部 fold × edit_ratio/depth × 4 组 + 对比图
  python make_plots.py --folds single_to_composed_d2 --modes 1,4
  python make_plots.py --x-axes edit_ratio --no-compare
产出：
  results/figures/<fold>/mode<N>_<x>.png + .csv
  results/figures/<fold>/compare_<x>.png + .csv
"""

import argparse
import subprocess
import sys
from pathlib import Path

CUR = Path(__file__).resolve().parent
FOLDS = ["single_to_composed_d2", "single_to_composed_d3",
         "heldout_single_decomp", "heldout_single_balance",
         "heldout_single_refactor", "heldout_single_resub",
         "heldout_composed_decomp", "heldout_composed_balance",
         "heldout_composed_refactor", "heldout_composed_resub"]


def main():
    ap = argparse.ArgumentParser(description="一键出图（每 fold）")
    ap.add_argument("--folds", type=str, default="")
    ap.add_argument("--fold-mode", choices=["fold", "loco"], default="fold")
    ap.add_argument("--modes", type=str, default="1,2,3,4")
    ap.add_argument("--x-axes", type=str, default="edit_ratio,depth")
    ap.add_argument("--n-bins", type=int, default=6)
    ap.add_argument("--suffix", type=str, default="_amp")
    ap.add_argument("--meta", type=Path, default=CUR / "generate_trans" / "matrix" / "view_metadata.csv")
    ap.add_argument("--out-root", type=Path, default=CUR / "results" / "figures")
    ap.add_argument("--no-compare", action="store_true")
    ap.add_argument("--python", type=str, default="")
    args = ap.parse_args()
    py = args.python.strip() or sys.executable
    folds = ([f.strip() for f in args.folds.split(",") if f.strip()] if args.folds.strip()
             else FOLDS)
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    xaxes = [x.strip() for x in args.x_axes.split(",") if x.strip()]
    args.out_root.mkdir(parents=True, exist_ok=True)

    for fold in folds:
        runs = list((CUR / "results").glob(f"{fold}_seed*_*_{args.fold_mode}_*{args.suffix}"))
        if not runs:
            print(f"[SKIP] {fold}：没有 {args.fold_mode}{args.suffix} 的 run")
            continue
        outdir = args.out_root / fold
        outdir.mkdir(parents=True, exist_ok=True)
        glob_pat = f"{fold}*_{args.fold_mode}_*"
        print(f"\n===== {fold}（{len(runs)} 个 run）=====")
        for mode in modes:
            for x in xaxes:
                cmd = [py, "-X", "utf8", str(CUR / "plot_robustness.py"),
                       "--meta", str(args.meta), "--results", str(CUR / "results"),
                       "--mode", mode, "--runs-glob", glob_pat,
                       "--x-axis", x, "--n-bins", str(args.n_bins),
                       "--out", str(outdir / f"mode{mode}_{x}.png")]
                rc = subprocess.call(cmd, cwd=str(CUR), stdout=subprocess.DEVNULL,
                                     stderr=subprocess.STDOUT)
                print(f"  mode{mode} {x}: rc={rc} -> {outdir / f'mode{mode}_{x}.png'}")
        if not args.no_compare:
            for x in xaxes:
                cmd = [py, "-X", "utf8", str(CUR / "plot_robustness_compare.py"),
                       "--meta", str(args.meta), "--results", str(CUR / "results"),
                       "--modes", *modes, "--runs-glob", glob_pat,
                       "--x-axis", x, "--n-bins", str(args.n_bins),
                       "--out", str(outdir / f"compare_{x}.png")]
                rc = subprocess.call(cmd, cwd=str(CUR), stdout=subprocess.DEVNULL,
                                     stderr=subprocess.STDOUT)
                print(f"  compare {x}: rc={rc} -> {outdir / f'compare_{x}.png'}")
    print(f"\n[OK] 图与同名 csv 都在 {args.out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
