# -*- coding: utf-8 -*-
"""_sum_by_mode.py —— 按"变换种类"汇总检测指标，看换一种等价实现会掉多少。

用法：py phase2/ys/_sum_by_mode.py <结果目录关键字>
"""
import glob
import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEY = sys.argv[1] if len(sys.argv) > 1 else "g2_grouped_ys"


def mode_of(v: str) -> str:
    m = re.search(r"__(rw[a-z0-9]+)_d\d+_s\d+$", str(v))
    if m:
        return m.group(1)[2:].split("_d")[0]
    m = re.search(r"__(ys_[a-z0-9]+)$", str(v))
    if m:
        return m.group(1)
    return "src(注入源)"


def main() -> int:
    cands = [d for d in glob.glob(os.path.join(ROOT, "results", f"*{KEY}")) if os.path.isdir(d)]
    if not cands:
        print(f"没找到含 {KEY} 的结果目录")
        return 1
    d = cands[0]
    v = pd.read_csv(os.path.join(d, "variant_level_summary.csv"))
    t = v[v.Type == "TRANS"].copy()
    t["mode"] = t.View.map(mode_of)
    t["kind"] = t.View.apply(lambda x: "trojan" if "__inj" in str(x) else "control")
    print(f"[结果目录] {os.path.basename(d)}")
    print(f"[测试视图] {len(t)} 个｜变换种类 {sorted(t['mode'].unique())}\n")

    tro = t[t.kind == "trojan"]
    g = tro.groupby("mode").agg(视图数=("View", "size"), AP=("AP", "mean"),
                                Recall5=("Recall@5%", "mean"),
                                WorstView_AP=("AP", "min")).round(4)
    base = g.AP.max()
    g["相对最好"] = (g.AP / base - 1).round(4)
    print("=== 木马视图（按变换种类）===")
    print(g.to_string())
    print()
    ctl = t[t.kind == "control"]
    gc = ctl.groupby("mode").agg(视图数=("View", "size"), FPR=("FPR", "mean")).round(4)
    print("=== 合法对照视图（误报率）===")
    print(gc.to_string())
    print()
    print("=== 逐视图明细 ===")
    print(t[["View", "mode", "kind", "AP", "Recall@5%", "FPR"]].round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
