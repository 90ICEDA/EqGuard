# -*- coding: utf-8 -*-
"""make_baseline_history.py（第一步补全）—— 把历史结果表搬进 10.13/baseline/，让 baseline 目录自包含。

做三件事：
  1. 把 10.10/results 与 10.12/results 下的**全部** CSV 复制到 10.13/baseline/tables/（前缀 1010_/1012_）；
  2. 把几张关键宏表拼成一张"历史关键数字总表"（带"来源"列）；
  3. 打印每张关键表的前几行，便于写文档时直接引用（不凭记忆）。

用法：py phase2/ys/make_baseline_history.py
"""
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "10.13" / "baseline"
TAB = BASE / "tables"
SRC = {"1010": ROOT / "10.10" / "results", "1012": ROOT / "10.12" / "results"}
KEY = ["baselines_macro.csv", "baselines_macro_BETA.csv",
       "simple_models_macro.csv", "simple_models_macro_BETA.csv",
       "feature_groups_macro.csv", "gamma_summary.csv",
       "summary_models_beta.csv", "summary_methods_ab.csv"]


def main() -> int:
    TAB.mkdir(parents=True, exist_ok=True)
    n = 0
    for tag, d in SRC.items():
        if not d.exists():
            print(f"[WARN] 缺目录 {d}")
            continue
        for p in sorted(d.rglob("*.csv")):
            shutil.copy2(p, TAB / f"{tag}_{p.name}")
            n += 1
    print(f"[复制] {n} 张历史表 → {TAB}")

    frames = []
    for tag, d in SRC.items():
        for name in KEY:
            p = d / name
            if not p.exists():
                continue
            df = pd.read_csv(p)
            df.insert(0, "来源", f"{tag}/{name}")
            frames.append(df)
            print(f"\n--- {tag}/{name}（{len(df)} 行）---")
            print(df.head(6).to_string(index=False))
    if frames:
        out = BASE / "历史关键数字总表.csv"
        pd.concat(frames, ignore_index=True).to_csv(out, index=False, encoding="utf-8-sig")
        print(f"\n[导出] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
