"""make_3seed_report.py —— 由 CSV 生成 3seed_report.md ✓（数字全部来自文件 ✓，不手填 ✓）。"""
from __future__ import annotations
import argparse, datetime
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def fmt(v, nd=4):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "nan"
    return "nan" if x != x else f"{x:.{nd}f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", type=Path, default=ROOT / "_devcfg/v31_3seed_summary.csv")
    ap.add_argument("--region-dir", type=Path, default=ROOT / "_devcfg/region_seeds")
    ap.add_argument("--out", type=Path, default=ROOT / "10.15/07_论文图表/3seed_report.md")
    a = ap.parse_args()
    L = ["# 3-seed 主表与图表（自动生成 ✓）", "",
         f"生成时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S} ✓", ""]
    if a.summary.exists():
        d = pd.read_csv(a.summary)
        L += ["## 1. 节点级（逐视图均值 ✓ 为主；pooled ⚠️ 仅参考）", "",
              "| npz | views | 含正视图 | view_AP | view_AUC | R@1% | R@5% | pooled_AP ⚠️ | pooled_AUC |",
              "|---|---|---|---|---|---|---|---|---|"]
        for _, r in d.iterrows():
            L.append(f"| {r['npz']} | {int(r['views'])} | {int(r['views_with_pos'])} | {fmt(r['view_ap'])} | "
                     f"{fmt(r['view_auc'])} | {fmt(r['r1'])} | {fmt(r['r5'])} | {fmt(r['pooled_ap'])} | {fmt(r['pooled_auc'])} |")
        L += ["", "### mean ± std（ddof=0 ✓，与 summarize_npz 一致 ✓）", "",
              "| metric | mean | std |", "|---|---|---|"]
        for k in ["view_ap", "view_auc", "r1", "r5", "pooled_ap", "pooled_auc"]:
            L.append(f"| {k} | {fmt(d[k].mean())} | {fmt(d[k].std(ddof=0))} |")
    rd = a.region_dir
    if (rd / "region_seeds.csv").exists():
        r = pd.read_csv(rd / "region_seeds.csv")
        L += ["", "## 2. 区域级（每 seed ✓）", "",
              "| seed | node (per-view AP) | DFF cone | PO cone | whole view (pooled) |",
              "|---|---|---|---|---|"]
        for _, x in r.iterrows():
            L.append(f"| {int(x['seed'])} | {fmt(x['view_ap'])} | {fmt(x['dff_view_ap'])} | "
                     f"{fmt(x['po_cone_view_ap'])} | {fmt(x['view_pooled_ap'])} |")
        if (rd / "region_seeds_mean.csv").exists():
            m = pd.read_csv(rd / "region_seeds_mean.csv")
            L += ["", "### mean ± std（ddof=1 ✓）", "", "| metric | mean | std | n |", "|---|---|---|---|"]
            for _, x in m.iterrows():
                L.append(f"| {x['metric']} | {fmt(x['mean'])} | {fmt(x['std'])} | {int(x['n'])} |")
            L += ["", "> 口径 ✓：前三种粒度报**逐视图均值** ✓；`view_view_ap` 在数学上不存在 ✗",
                  "> （整视图 = 1 个区域 ✗）→ 用 `view_pooled_ap` ✓。"]
    L += ["", "## 3. 图", "", "- `G10_seed_bars_v31.png`（3 seed 误差棒 ✓）",
          "- `G03_granularity_3seed.png`（四粒度 ✓）",
          "- `G05_main_3seed.png`（(a) dev4 n=1 ⚠️｜(b) v3.1 n=3 ✓）", ""]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("\n".join(L), encoding="utf-8")
    print("[report] " + str(a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())