# -*- coding: utf-8 -*-
"""_sum_lio3.py —— 把多次 lio 运行的逐实例宏平均 AP 并成一张表（跨 seed）。

用法：
    py phase2/ys/_sum_lio3.py --runs <dir1> <dir2> <dir3> --out 10.13/lio_summary_3seed.csv
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
SUF = re.compile(r"__(rw[a-z0-9]+_d\d+_s\d+|ys_[a-z0-9]+)")


def one(run: str) -> pd.Series | None:
    f = ROOT / "results" / run / "variant_level_summary.csv"
    if not f.exists():
        print(f"[WARN] 缺 {f}")
        return None
    d = pd.read_csv(f)
    d = d[[c for c in ("Split", "View", "AP") if c in d.columns]].copy()
    m = [SUF.search(str(v)) for v in d["View"]]
    d["mode"] = [x.group(1) if x else "ORIG" for x in m]
    d = d[d["mode"] != "ORIG"].dropna(subset=["AP"])
    return d.groupby("Split")["AP"].mean()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "10.13" / "lio_summary_3seed.csv")
    a = ap.parse_args()
    cols = {}
    for i, r in enumerate(a.runs):
        s = one(r)
        if s is None:
            continue
        tag = f"run{i + 1}"
        mm = re.search(r"seed(\d+)", r)
        if mm:
            tag = "s" + mm.group(1)
        cols[tag] = s
    if not cols:
        print("[ERROR] 没有可用结果")
        return 1
    t = pd.concat(cols, axis=1)
    print("逐实例宏平均 AP（跨 5 种变换）× seed")
    print(t.round(4).to_string())
    print()
    print("逐实例 mean ± std（跨 seed）")
    print(t.agg(["mean", "std"], axis=1).round(4).to_string())
    per_run = t.mean(axis=0)
    print()
    print("逐 seed 宏平均:", {k: round(float(v), 4) for k, v in per_run.items()})
    print("跨 seed 宏平均 = %.4f ± %.4f" % (per_run.mean(), per_run.std(ddof=1)
                                            if len(per_run) > 1 else float("nan")))
    t.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"[导出] {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
