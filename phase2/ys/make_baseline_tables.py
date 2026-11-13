# -*- coding: utf-8 -*-
"""make_baseline_tables.py —— 第一步：把本轮跑过的实验整理成可机读的 baseline 表。

数据来源（全是已经跑出来的产物，不重新训练）：
    * 10.13/rank_pct_<run>.csv   —— `phase2/ys/_rank_pct.py` 的逐视图输出
        （含 AP / Recall@5% / best_pos_pct / mean_pos_pct / pos_top1pct，且**只含有正样本的视图**）
    * logs_1013_<run>.txt        —— 训练日志里的 MACRO（电路级宏平均）块

产物（写到 10.13/baseline/）：
    baseline_runs_by_mode.csv    按 (run, 变换种类) 汇总
    baseline_runs_macro.csv      每个 run 的宏平均指标 + 说明

用法：py phase2/ys/make_baseline_tables.py
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "10.13" / "baseline"

RUNS = [
    ("g1", "无泄漏分组划分 + 只见过 decomp3（第一次模型结果，见执行记录）", None),
    ("g2", "无增强：训练 = 其余 4 块 × decomp3；测试 = rs232 × 4 种变换", "rank_pct_g2.csv"),
    ("g3", "（已作废）测试侧标签丢失导致假性归零，仅作记录", "rank_pct_g3.csv"),
    ("g3b", "等价增强：训练 = 其余 4 块 × (decomp3 + ys_abc)；测试 = rs232 × 4 种", "rank_pct_g3b.csv"),
    ("g5", "等价增强 + 测试侧加 ys_rt（纯往返上界）：训练同上，测试 = rs232 × 5 种", "rank_pct_g5.csv"),
]
MACRO_KEYS = ["AP", "Anchor_AP_Orig", "Anchor_AP_Trans", "Recall@1%", "Recall@5%",
              "Paired_MAE", "Flip_Rate", "Spearman_Corr"]
AGG = ["n", "n_pos", "AP", "Recall@5%", "best_pos_pct", "mean_pos_pct",
       "pos_top1pct", "neg_med_pct"]


def macro_of(tag: str) -> dict:
    p = ROOT / f"logs_1013_{tag}.txt"
    if not p.exists():
        return {}
    txt = p.read_text(encoding="utf-8", errors="replace")
    out = {}
    for k in MACRO_KEYS:
        m = re.search(rf"^\s*{re.escape(k)}\s+(-?[\d.]+)", txt, re.M)
        if m:
            out[k] = float(m.group(1))
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    views, macros = [], []
    for tag, desc, csv in RUNS:
        rec = {"run": tag, "说明": desc}
        rec.update(macro_of(tag) or {"AP": None})
        macros.append(rec)
        if not csv:
            continue
        p = ROOT / "10.13" / csv
        if not p.exists():
            print(f"[WARN] 缺 {p}")
            continue
        d = pd.read_csv(p)
        d["run"] = tag
        views.append(d)

    if views:
        allv = pd.concat(views, ignore_index=True)
        allv.to_csv(OUT / "baseline_runs_views.csv", index=False, encoding="utf-8-sig")
        g = (allv.groupby(["run", "mode", "kind"])[AGG]
                .mean().round(4).reset_index()
                .sort_values(["run", "mode", "kind"]))
        g.to_csv(OUT / "baseline_runs_by_mode.csv", index=False, encoding="utf-8-sig")
        print("=== 按 (run, 变换种类) 汇总 ===")
        print(g.to_string(index=False))

    m = pd.DataFrame(macros)
    m.to_csv(OUT / "baseline_runs_macro.csv", index=False, encoding="utf-8-sig")
    print("\n=== 各 run 的宏平均（电路级）===")
    print(m.round(4).to_string(index=False))
    print(f"\n[导出] {OUT}/baseline_runs_by_mode.csv, baseline_runs_views.csv, baseline_runs_macro.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
