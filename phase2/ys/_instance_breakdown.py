# -*- coding: utf-8 -*-
"""_instance_breakdown.py —— 逐木马实例分解（第四步的"未见木马实例"这一维）。

测试电路 rs232 有 6 个木马实例（injalpha…injzeta），模型在训练时从未见过它们
（训练只用另外 4 块电路）→ 按实例分组就能看出"换个木马实例还灵不灵"。
同时给出各 run 的跨实例均值与最差实例（worst-case）。
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "10.13"
RUNS = {
    "base(39,无增强)": "rank_pct_g7_base.csv",
    "g5(39,+增强)": "rank_pct_g5.csv",
    "g6B(筛选7)": "rank_pct_g6_keepretained.csv",
    "prim(原语)": "rank_pct_g7_prim.csv",
    "neigh(邻域)": "rank_pct_g8_neigh.csv",
    "locratio(局部比例)": "rank_pct_g9_locratio.csv",
}
MODES = sys.argv[1:] or ["ys_rt", "ys_abc"]


def main() -> int:
    for md in MODES:
        print(f"\n=== {md}：逐木马实例 best_pos_pct（越小越好）===")
        rows = []
        for k, fn in RUNS.items():
            p = OUT / fn
            if not p.exists():
                continue
            d = pd.read_csv(p)
            d = d[d["View"].astype(str).str.contains("__inj")]
            if d.empty:
                continue
            d = d.copy()
            d["inst"] = d["View"].str.extract(r"__(inj[a-z]+)_d")
            d = d[d["mode"] == md]
            if d.empty:
                continue
            s = d.groupby("inst")["best_pos_pct"].mean()
            rows.append([k] + [round(float(s.get(i, float("nan"))), 4)
                               for i in ["injalpha", "injbeta", "injdelta",
                                         "injepsilon", "injgamma", "injzeta"]] +
                        [round(float(s.mean()), 4), round(float(s.max()), 4)])
        df = pd.DataFrame(rows, columns=["run", "alpha", "beta", "delta",
                                         "epsilon", "gamma", "zeta", "均值", "最差"])
        print(df.to_string(index=False))
        df.to_csv(OUT / f"instance_breakdown_{md}.csv", index=False, encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
