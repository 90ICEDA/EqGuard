# -*- coding: utf-8 -*-
"""_sum_lio.py —— 汇总 10.13 的 lio（未见木马实例）运行，产出逐实例对照表。

读 `results/<tag>/variant_level_summary.csv`（每测试视图一行，`Split` = 被留出的实例），
按 (实例, 变换模式) 聚合 AP / ROC-AUC / Recall@1% / Recall@5%，并给出逐实例宏平均。

用法：
    py phase2/ys/_sum_lio.py --runs fold_ys5_seed42mode4_pred_hardb16_lio_g10_mixed_lio42 ^
        fold_ys5_seed42mode4_pred_hardb16_lio_g5_lio42 --out 10.13/lio_summary.csv
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS = ROOT / "results"
SUF = re.compile(r"__(rw[a-z0-9]+_d\d+_s\d+|ys_[a-z0-9]+)$")


def mode_of(v: str) -> str:
    m = SUF.search(str(v))
    if not m:
        return "ORIG"
    f = m.group(1)
    return f if f.startswith("ys_") else f.split("_d")[0][2:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True, help="results 下的目录名")
    ap.add_argument("--out", type=Path, default=ROOT / "10.13" / "lio_summary.csv")
    a = ap.parse_args()

    keep = ["Split", "View", "AP", "ROC-AUC", "Recall@1%", "Recall@5%", "N_Trojan"]
    frames = []
    for tag in a.runs:
        f = RESULTS / tag / "variant_level_summary.csv"
        if not f.exists():
            print(f"[WARN] 缺 {f}（该 run 可能还没跑完）")
            continue
        d = pd.read_csv(f)
        d = d[[c for c in keep if c in d.columns]].copy()
        d["mode"] = [mode_of(v) for v in d["View"]]
        d["run"] = tag.split("_")[-2] + "_" + tag.split("_")[-1] if "_" in tag else tag
        d = d[d["mode"] != "ORIG"]
        d = d.dropna(subset=[c for c in ("AP", "Recall@5%") if c in d.columns], how="all")
        # 逐实例（Split）× 模式
        g = (d.groupby(["Split", "mode"])[["AP", "ROC-AUC", "Recall@1%", "Recall@5%"]]
               .mean().round(4).reset_index())
        g["run"] = tag
        frames.append(g)

    if not frames:
        print("[ERROR] 没有任何可用结果")
        return 1
    allg = pd.concat(frames, ignore_index=True)

    for tag, sub in allg.groupby("run"):
        print(f"\n=== {tag}：逐实例 × 模式（AP）===")
        print(sub.pivot_table(index="Split", columns="mode", values="AP")
                 .round(4).to_string())
        print(f"--- {tag}：逐实例宏平均（跨 5 种变换）---")
        print(sub.groupby("Split")[["AP", "ROC-AUC", "Recall@1%", "Recall@5%"]]
                 .mean().round(4).to_string())
        m = sub.groupby("Split")["AP"].mean()
        print(f"[宏平均 AP] {m.mean():.4f} ± {m.std(ddof=1):.4f}（{len(m)} 个实例）")
        print(f"[参照] 10.10 历史 LIO（M0，39 维，30ep/b4，hosts_beta）= 0.0819 ± 0.1080")

    allg.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"\n[导出] {a.out}（{len(allg)} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
