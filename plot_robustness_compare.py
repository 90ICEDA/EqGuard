#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_robustness_compare.py

用途：把多个 train_mode 的 robustness-boundary 曲线叠到一张图上，
      对比 Orig-only / Eq-Aug / Random-Cons / Hard-Cons。

依赖：plot_robustness.py 里的工具函数和 circuit_macro_average。

用法：
    python plot_robustness_compare.py --modes 1 2 3 4
    python plot_robustness_compare.py --modes 1 4 --x-axis edit_ratio
"""

import argparse
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 从 plot_robustness 复用
from plot_robustness import (
    load_view_metadata,
    find_runs,
    load_variant_summaries,
    merge_with_metadata,
    circuit_macro_average,
    extract_base_circuit,
)


# 四个 mode 的标签和颜色
MODE_LABELS = {
    1: ('Orig-only (Anchor)',  '#000000', '--'),   # 黑色虚线，基准
    2: ('Eq-Aug',              '#1f77b4', '-'),
    3: ('Random-Consistency',  '#2ca02c', '-'),
    4: ('Hard-Consistency',    '#d62728', '-'),
}


def compute_mode_macro(args, mode, meta_df):
    """对指定 mode 的所有 run 计算 macro average。返回 (macro_df, n_runs)。"""
    runs = find_runs(args.results, mode, args.seed, getattr(args, "runs_glob", ""))
    if not runs:
        print(f"  [WARN] mode{mode}: 未找到 run 目录")
        return None, 0

    variant_df = load_variant_summaries(runs)
    if len(variant_df) == 0:
        print(f"  [WARN] mode{mode}: 无 variant_level_summary.csv")
        return None, 0

    trans_df = variant_df[variant_df['Type'] == 'TRANS'].copy()
    merged = merge_with_metadata(trans_df, meta_df)

    y_cols = ['AP_T', 'Paired_MAE_PerOrig',
              'Recall@1%_T', 'Recall@2%_T', 'Recall@5%_T']
    y_cols = [c for c in y_cols if c in merged.columns]

    macro = circuit_macro_average(merged, args.x_axis, y_cols,
                                  n_bins=args.n_bins, seed_col='seed')
    return macro, len(runs)


def find_breaking_point(xs, ys, baseline_drop=0.05, relative=False):
    """
    找到曲线开始显著下降的 x 值。
      baseline_drop: 绝对下降阈值（AP 单位）
      relative: 若为 True，则用相对下降比例（相对于第一个点的值）
    返回：触发点 x 值，或 None。
    """
    if len(xs) == 0 or len(ys) == 0:
        return None

    baseline = ys[0]
    if baseline == 0:
        return None

    for x, y in zip(xs[1:], ys[1:]):
        if pd.isna(y):
            continue
        drop = baseline - y
        if relative:
            drop = drop / abs(baseline)
        if drop > baseline_drop:
            return x
    return None


def plot_compare(all_macros, x_col, y_specs, output_path,
                 detect_breaking=True, baseline_drop=0.05,
                 title='Robustness Boundary Comparison'):
    """
    all_macros: dict {mode: macro_df}
    y_specs: list of (y_col, subplot_title, ylabel)
    """
    n = len(y_specs)
    if n == 0:
        print("[WARN] 无可绘制指标")
        return

    n_cols = 2
    n_rows = (n + n_cols - 1) // n_cols
    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(7 * n_cols, 4.5 * n_rows))
    axes = np.array(axes).flatten()

    x_center = x_col + '_center'

    for i, (y_col, subplot_title, ylabel) in enumerate(y_specs):
        ax = axes[i]
        mean_col = f"{y_col}_mean"
        std_col = f"{y_col}_std"

        any_plotted = False
        for mode in sorted(all_macros.keys()):
            macro_df = all_macros[mode]
            if macro_df is None or len(macro_df) == 0:
                continue
            if mean_col not in macro_df.columns:
                continue

            label, color, ls = MODE_LABELS.get(
                mode, (f"mode{mode}", None, '-'))

            xs = macro_df[x_center].values
            ys = macro_df[mean_col].values
            ax.plot(xs, ys, marker='o', linewidth=2, markersize=5,
                    color=color, linestyle=ls, label=label)
            any_plotted = True

            # 误差带
            if std_col in macro_df.columns:
                stds = macro_df[std_col].fillna(0).values
                if np.any(stds > 0):
                    ax.fill_between(xs, ys - stds, ys + stds,
                                    alpha=0.15, color=color)

            # 失稳点
            if detect_breaking:
                bp = find_breaking_point(xs, ys, baseline_drop=baseline_drop)
                if bp is not None:
                    ax.axvline(x=bp, color=color, linestyle=':',
                               alpha=0.5, linewidth=1)
                    ax.text(bp, ax.get_ylim()[1] * 0.9,
                            f"{label}\nbp={bp:.3f}",
                            color=color, fontsize=7, va='top')

        if not any_plotted:
            ax.set_title(f"{subplot_title}\n(无数据)")
            ax.axis('off')
            continue

        ax.set_xlabel(x_col, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(subplot_title, fontsize=12)
        ax.grid(alpha=0.3, linestyle='--')
        ax.legend(fontsize=8, loc='best')

    for j in range(n, len(axes)):
        axes[j].axis('off')

    fig.suptitle(title, fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[OK] 对比图已保存: {output_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", type=str,
                    default="generate_trans/trans/view_metadata.csv")
    ap.add_argument("--results", type=str, default="results")
    ap.add_argument("--modes", type=int, nargs='+', default=[1, 2, 3, 4],
                    help="要对比的 train_mode 列表")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--x-axis", type=str, default="edit_ratio",
                    choices=["edit_ratio", "edit_count",
                             "expansion_ratio", "gate_expansion", "depth"])
    ap.add_argument("--n-bins", type=int, default=10)
    ap.add_argument("--no-breaking", action='store_true',
                    help="不检测失稳点")
    ap.add_argument("--baseline-drop", type=float, default=0.05,
                    help="AP 下降超过此值视为失稳（默认 0.05）")
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--runs-glob", type=str, default="",
                    help="只保留文件名匹配该通配的 run 目录（如 '*single_to_composed_d2*'）")
    args = ap.parse_args()

    print(f"[INFO] view_metadata: {args.meta}")
    meta_df = load_view_metadata(args.meta)
    print(f"       共 {len(meta_df)} 个视图")

    all_macros = {}
    for mode in args.modes:
        print(f"\n[INFO] 处理 mode{mode} ...")
        macro, n_runs = compute_mode_macro(args, mode, meta_df)
        if macro is not None:
            all_macros[mode] = macro
            print(f"       macro 行数: {len(macro)}, runs: {n_runs}")

    if not all_macros:
        print("[ERROR] 没有任何 mode 有数据")
        return

    # 输出
    if args.out:
        img_path = args.out
        os.makedirs(os.path.dirname(os.path.abspath(img_path)), exist_ok=True)
    else:
        out_dir = os.path.join(args.results, "robustness_compare")
        os.makedirs(out_dir, exist_ok=True)
        img_path = os.path.join(out_dir, f"compare_{args.x_axis}.png")

    # 导出合并 CSV
    csv_path = img_path.replace('.png', '.csv')
    merged_rows = []
    for mode, macro in all_macros.items():
        m = macro.copy()
        m['mode'] = mode
        merged_rows.append(m)
    pd.concat(merged_rows, ignore_index=True).to_csv(
        csv_path, index=False, encoding='utf-8-sig')
    print(f"\n[OK] 对比数据已保存: {csv_path}")

    # y_specs
    y_specs = [
        ('AP_T',              'AP on Transformed',       'AP_T'),
        ('Paired_MAE_PerOrig','Paired MAE (PerOrig)',    'MAE'),
        ('Recall@1%_T',       'Recall@1%',               'Recall@1%'),
        ('Recall@2%_T',       'Recall@2%',               'Recall@2%'),
        ('Recall@5%_T',       'Recall@5%',               'Recall@5%'),
    ]
    # 只要有任一 mode 有该指标就画
    any_macro = next(iter(all_macros.values()))
    y_specs = [(c, t, l) for c, t, l in y_specs
               if f"{c}_mean" in any_macro.columns]

    plot_compare(
        all_macros=all_macros,
        x_col=args.x_axis,
        y_specs=y_specs,
        output_path=img_path,
        detect_breaking=not args.no_breaking,
        baseline_drop=args.baseline_drop,
        title=f"Robustness Boundary Comparison ({', '.join(f'mode{m}' for m in all_macros)})",
    )


if __name__ == "__main__":
    main()