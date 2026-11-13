#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_view_metadata.py — 从 matrix manifest 投影出旧绘图脚本要的 `view_metadata.csv`

旧脚本（`plot_robustness.py` / `plot_robustness_compare.py`）需要：
  `dst_verilog`（会被 normalize 成 view_key）、`edit_count`、`orig_gate_count`、`gate_expansion`、
  `depth`、`operator_family`、`seed` —— 这些在 `matrix/view_manifest_cec.csv` 里全都有。

用法：
  python make_view_metadata.py --matrix-root matrix --out matrix/view_metadata.csv
"""

import argparse
from pathlib import Path

import pandas as pd

KEEP = ["view_name", "dst_verilog", "circuit", "operator_family", "operator_chain",
        "composition_depth", "depth", "seed", "edit_count", "orig_gate_count",
        "final_gate_count", "gate_expansion", "edit_ratio", "gate_expansion_ratio",
        "depth_change", "seq_gate_count", "cec_status", "freeze_tag"]


def main():
    ap = argparse.ArgumentParser(description="生成 view_metadata.csv（供 plot_robustness*.py 使用）")
    ap.add_argument("--matrix-root", type=Path, default=Path(__file__).resolve().parent / "matrix")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    src = args.matrix_root / "view_manifest_cec.csv"
    if not src.exists():
        src = args.matrix_root / "view_manifest.csv"
    df = pd.read_csv(src, encoding="utf-8-sig")
    cols = [c for c in KEEP if c in df.columns]
    out_df = df[cols].copy()
    # 注意：`seed` 必须改名——训练结果的 variant_level_summary.csv 也有一列 `seed`（训练 seed），
    # 同名会在 `plot_robustness.merge_with_metadata` 里变成 seed_x/seed_y，导致电路宏平均退化为单 seed。
    if "seed" in out_df.columns:
        out_df = out_df.rename(columns={"seed": "view_seed"})
    if "view_name" in out_df.columns:
        # 便于按视图名直接 join（新表用 `Test_File`= view_name）
        out_df.insert(0, "view_key", out_df["view_name"])
    dest = args.out or (args.matrix_root / "view_metadata.csv")
    out_df.to_csv(dest, index=False, encoding="utf-8-sig")
    print(f"[OK] {dest}｜{len(out_df)} 行｜列: {list(out_df.columns)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
