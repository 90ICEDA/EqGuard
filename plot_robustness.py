#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_robustness.py

用途：从 view_metadata.csv 和 results/*modeN*/variant_level_summary.csv
      生成 robustness-boundary 曲线。

X 轴：edit_ratio（默认）/ edit_count / expansion_ratio / gate_expansion
Y 轴：AP_T / Paired_MAE_PerOrig / Recall@1%_T / Recall@2%_T / Recall@5%_T

用法：
    python plot_robustness.py --mode 1
    python plot_robustness.py --mode 1 --x-axis edit_count
    python plot_robustness.py --mode 1 --seed 42 --out results/fig/rob.png
"""

import argparse
import os
import re
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


# ------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------

def normalize_view_name(name):
    """'path/rs232t1000tr45.v' → 'rs232t1000tr45'"""
    s = os.path.basename(str(name).strip())
    if s.endswith('.v'):
        s = s[:-2]
    return s


def extract_base_circuit(test_file):
    """'rs232t1000_ORIG' → 'rs232t1000'；'rs232t1000tr45' → 'rs232t1000'；
    新命名 'rs232t1000__balance_d2_s42' → 'rs232t1000'（按 `__` 切）"""
    s = str(test_file).strip()
    if s.endswith('_ORIG'):
        return s[:-5]
    if '__' in s:                       # 分任务4 的视图命名 <circuit>__<chain>_d<depth>_s<seed>
        return s.split('__')[0]
    return re.sub(r'tr\d+$', '', s)


# ------------------------------------------------------------
# 数据读取
# ------------------------------------------------------------

def load_view_metadata(meta_path):
    """读取 view_metadata.csv，返回带 edit_ratio / expansion_ratio 的 DataFrame。"""
    df = pd.read_csv(meta_path)
    df['view_key'] = df['dst_verilog'].apply(normalize_view_name)

    if 'edit_count' in df.columns and 'orig_gate_count' in df.columns:
        df['edit_ratio'] = df['edit_count'] / df['orig_gate_count'].clip(lower=1)

    if 'gate_expansion' in df.columns and 'orig_gate_count' in df.columns:
        df['expansion_ratio'] = df['gate_expansion'] / df['orig_gate_count'].clip(lower=1)

    keep = ['view_key']
    for col in ['edit_count', 'orig_gate_count', 'gate_expansion',
                'edit_ratio', 'expansion_ratio',
                'depth', 'operator_family', 'seed']:
        if col in df.columns:
            keep.append(col)

    return df[keep].drop_duplicates(subset=['view_key'])


def find_runs(results_root, mode, seed=None, extra_glob=""):
    """扫描 results/ 下所有 modeN 的 run 目录。

    extra_glob: 额外的子串过滤（如 '*single_to_composed_d2*' / '*fold*'），
                用于把图限制在单个 fold / 单个模式上（10 fold 混在一起画没有意义）。
    """
    pattern = os.path.join(results_root, f"*mode{mode}*")
    runs = sorted(glob.glob(pattern))
    if extra_glob:
        import fnmatch
        runs = [r for r in runs if fnmatch.fnmatch(os.path.basename(r), extra_glob)]
    if seed is not None:
        runs = [r for r in runs if f"seed{seed}" in r]
    return runs


def load_variant_summaries(run_dirs):
    dfs = []
    for run_dir in run_dirs:
        path = os.path.join(run_dir, 'variant_level_summary.csv')
        if not os.path.exists(path):
            print(f"  [跳过] 未找到: {path}")
            continue
        df = pd.read_csv(path)
        df['run_dir'] = os.path.basename(run_dir)

        # 从 run 目录名提取 seed，如 'trainv0.13seed42mode1'
        m = re.search(r'seed(\d+)', os.path.basename(run_dir))
        df['seed'] = int(m.group(1)) if m else 0

        dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def merge_with_metadata(variant_df, meta_df):
    """TRANS 行的 Test_File 与 view_metadata 的 view_key 关联。"""
    vdf = variant_df.copy()
    vdf['view_key'] = vdf['Test_File'].apply(
        lambda x: '' if str(x).endswith('_ORIG') else str(x)
    )
    merged = vdf.merge(meta_df, on='view_key', how='left')
    merged['Base_Circuit'] = merged['Test_File'].apply(extract_base_circuit)
    return merged


# ------------------------------------------------------------
# Circuit-level macro average
# ------------------------------------------------------------

def circuit_macro_average(df, x_col, y_cols, n_bins=10, seed_col='seed'):
    """
    两级 macro average（支持多 seed 误差带）。

    流程：
      1. 每个 (bin, circuit, seed) 内对 y 取均值
      2. 每个 (bin, seed) 内对所有 circuit 取均值   → seed-level macro average
      3. 每个 bin 内对所有 seed 求 mean / std       → 最终曲线 + 误差带

    若数据里无 seed_col，则退化为单 seed，std=0。

    返回 DataFrame:
      bin | <x_col>_center | <y>_mean | <y>_std | <y>_n_seed
    """
    if len(df) == 0 or x_col not in df.columns:
        return pd.DataFrame()

    df = df.dropna(subset=[x_col]).copy()
    if len(df) == 0:
        return pd.DataFrame()

    # 若无 seed 列，用一个伪 seed 值，退化到单 seed 行为
    if seed_col not in df.columns:
        df[seed_col] = 0

    # 1) 分箱
    x_min, x_max = df[x_col].min(), df[x_col].max()
    if x_max <= x_min or n_bins <= 1:
        df['bin'] = 0
    else:
        edges = np.linspace(x_min, x_max, n_bins + 1)
        df['bin'] = pd.cut(df[x_col], bins=edges,
                           include_lowest=True, labels=False)

    # 2) (bin, circuit, seed) 内对 y 取均值
    valid_y = [c for c in y_cols if c in df.columns]
    if not valid_y:
        return pd.DataFrame()

    per_bcs = (df.groupby(['bin', 'Base_Circuit', seed_col])[valid_y]
                 .mean(numeric_only=True)
                 .reset_index())

    # 3) (bin, seed) 内对 circuit 取均值（seed-level macro）
    per_bs = (per_bcs.groupby(['bin', seed_col])[valid_y]
                     .mean(numeric_only=True)
                     .reset_index())

    # 4) 每个 bin 内对 seed 求 mean / std
    agg_dict = {c: ['mean', 'std', 'count'] for c in valid_y}
    agg = per_bs.groupby('bin').agg(agg_dict)
    agg.columns = [f"{c}_{stat}" for c, stat in agg.columns]
    agg = agg.reset_index()

    # 5) bin 内 x 中心值
    bin_centers = df.groupby('bin')[x_col].mean().rename(x_col + '_center').reset_index()
    agg = agg.merge(bin_centers, on='bin', how='left')

    return agg.sort_values('bin').reset_index(drop=True)


# ------------------------------------------------------------
# 绘图
# ------------------------------------------------------------

def plot_robustness(macro_df, x_col, y_specs, output_path,
                    title='Robustness Boundary'):
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
        std_col  = f"{y_col}_std"

        if mean_col not in macro_df.columns or macro_df[mean_col].isna().all():
            ax.set_title(f"{subplot_title}\n(无数据)")
            ax.axis('off')
            continue

        xs = macro_df[x_center].values
        ys = macro_df[mean_col].values

        # 主曲线
        ax.plot(xs, ys, marker='o', linewidth=2, markersize=5,
                color='#1f77b4', label=ylabel)

        # 误差带（如果 std 存在且非全零）
        if std_col in macro_df.columns:
            stds = macro_df[std_col].fillna(0).values
            if np.any(stds > 0):
                ax.fill_between(xs, ys - stds, ys + stds,
                                alpha=0.2, color='#1f77b4',
                                label=f'{ylabel} ± std')

        ax.set_xlabel(x_col, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(subplot_title, fontsize=12)
        ax.grid(alpha=0.3, linestyle='--')
        if std_col in macro_df.columns and np.any(macro_df[std_col].fillna(0).values > 0):
            ax.legend(fontsize=9, loc='best')

    for j in range(n, len(axes)):
        axes[j].axis('off')

    fig.suptitle(title, fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"[OK] 图已保存: {output_path}")


# ------------------------------------------------------------
# main
# ------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", type=str,
                    default="generate_trans/trans/view_metadata.csv",
                    help="view_metadata.csv 路径")
    ap.add_argument("--results", type=str, default="results",
                    help="results/ 根目录")
    ap.add_argument("--mode", type=int, default=1,
                    help="train_mode（默认 1）")
    ap.add_argument("--seed", type=int, default=None,
                    help="只读哪个 seed（默认全部）")
    ap.add_argument("--runs-glob", type=str, default="",
                    help="只保留文件名匹配该通配的 run 目录（如 '*single_to_composed_d2*mode4*'）")
    ap.add_argument("--x-axis", type=str, default="edit_ratio",
                    choices=["edit_ratio", "edit_count",
                             "expansion_ratio", "gate_expansion", "depth"],
                    help="X 轴指标")
    ap.add_argument("--n-bins", type=int, default=10,
                    help="X 轴分箱数量（<=1 表示不分箱）")
    ap.add_argument("--out", type=str, default=None,
                    help="输出图路径（默认 results/robustness_mode{N}/...）")
    args = ap.parse_args()

    # 1) 读 view_metadata
    print(f"[INFO] view_metadata: {args.meta}")
    meta_df = load_view_metadata(args.meta)
    print(f"       共 {len(meta_df)} 个视图")

    # 2) 找 modeN 的 run 目录
    runs = find_runs(args.results, args.mode, args.seed, args.runs_glob)
    if not runs:
        print(f"[ERROR] 未找到 mode{args.mode} 的 run 目录")
        return
    print(f"[INFO] 找到 {len(runs)} 个 mode{args.mode} run：")
    for r in runs:
        print(f"       - {r}")

    # 3) 合并 variant_level_summary.csv
    variant_df = load_variant_summaries(runs)
    if len(variant_df) == 0:
        print("[ERROR] 无 variant_level_summary.csv")
        return
    print(f"[INFO] variant 总行数: {len(variant_df)}")

    # 4) 只保留 TRANS 行
    trans_df = variant_df[variant_df['Type'] == 'TRANS'].copy()
    print(f"[INFO] TRANS 行: {len(trans_df)}")

    # 5) 关联 view metadata
    merged = merge_with_metadata(trans_df, meta_df)
    miss = merged[args.x_axis].isna().sum() if args.x_axis in merged.columns else -1
    if miss > 0:
        print(f"[WARN] {miss} 行未匹配到 {args.x_axis}，将被忽略")

    # 6) 确认 Y 轴指标存在
    candidate_y = ['AP_T', 'Paired_MAE_PerOrig',
                   'Recall@1%_T', 'Recall@2%_T', 'Recall@5%_T']
    y_cols = [c for c in candidate_y if c in merged.columns]
    if not y_cols:
        print("[ERROR] 找不到任何 Y 轴指标")
        return

    # 7) circuit-level macro average
    macro = circuit_macro_average(merged, args.x_axis, y_cols,
                                  n_bins=args.n_bins, seed_col='seed')
    if len(macro) == 0:
        print("[ERROR] macro average 后为空")
        return

    # 8) 输出
    if args.out:
        img_path = args.out
        os.makedirs(os.path.dirname(os.path.abspath(img_path)), exist_ok=True)
    else:
        out_dir = os.path.join(args.results, f"robustness_mode{args.mode}")
        os.makedirs(out_dir, exist_ok=True)
        img_path = os.path.join(out_dir, f"robustness_{args.x_axis}.png")

    csv_path = img_path.replace('.png', '.csv')
    macro.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"[OK] 曲线数据已保存: {csv_path}")

    y_specs = [
        ('AP_T',              'AP on Transformed',       'AP_T'),
        ('Paired_MAE_PerOrig','Paired MAE (PerOrig)',    'MAE'),
        ('Recall@1%_T',       'Recall@1%',               'Recall@1%'),
        ('Recall@2%_T',       'Recall@2%',               'Recall@2%'),
        ('Recall@5%_T',       'Recall@5%',               'Recall@5%'),
    ]
    # 从 _mean 列判断是否存在
    y_specs = [(c, t, l) for c, t, l in y_specs if f"{c}_mean" in macro.columns]

    plot_robustness(
        macro_df=macro,
        x_col=args.x_axis,
        y_specs=y_specs,
        output_path=img_path,
        title=f"Robustness Boundary (mode{args.mode}, N_runs={len(runs)})",
    )

    # 控制台打印
    print("\n" + "=" * 60)
    print(f"[Macro Average vs {args.x_axis}]")
    print(macro.to_string(index=False))
    print("=" * 60)


if __name__ == "__main__":
    main()