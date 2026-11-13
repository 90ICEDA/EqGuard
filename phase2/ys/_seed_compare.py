# -*- coding: utf-8 -*-
"""_seed_compare.py —— 汇总三 seed 与各特征变体的逐模式指标（值全部从 rank_pct CSV 读）。"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "10.13"

RUNS = {
    "prim_s42": "rank_pct_g7_prim.csv",
    "prim_s43": "rank_pct_g7_prim_s43.csv",
    "prim_s44": "rank_pct_g7_prim_s44.csv",
    "g5_s42": "rank_pct_g5.csv",
    "g5_s43": "rank_pct_g5_s43.csv",
    "g5_s44": "rank_pct_g5_s44.csv",
    "neigh_s42": "rank_pct_g8_neigh.csv",
    "g6B_s42": "rank_pct_g6_keepretained.csv",
    "base_s42": "rank_pct_g7_base.csv",
}
MODES = ["ORIG", "decomp3", "bubble", "ys_rt", "ys_abc", "ys_aig"]


def main() -> int:
    rows = []
    for k, fn in RUNS.items():
        p = OUT / fn
        if not p.exists():
            print(f"[WARN] 缺 {p}")
            continue
        g = (pd.read_csv(p).groupby("mode")[["n_pos", "AP", "best_pos_pct",
                                             "Recall@5%", "pos_top1pct"]]
             .mean().round(4).reset_index())
        g["run"] = k
        rows.append(g)
    c = pd.concat(rows, ignore_index=True)
    c.to_csv(OUT / "step4_3seed_compare.csv", index=False, encoding="utf-8-sig")

    bpp = c.pivot_table(index="mode", columns="run", values="best_pos_pct")
    bpp = bpp.reindex([m for m in MODES if m in bpp.index])
    print("=== best_pos_pct（越小越好；变平/重综合只有 ys_rt / ys_abc / ys_aig）===")
    print(bpp.round(4).to_string())
    print("\n=== AP ===")
    print(c.pivot_table(index="mode", columns="run", values="AP")
          .reindex([m for m in MODES if m in bpp.index]).round(4).to_string())

    print("\n=== 关键模式上的 seed 均值 ± 标准差 ===")
    for fam, seeds in (("prim", ["prim_s42", "prim_s43", "prim_s44"]),
                       ("g5(39维)", ["g5_s42", "g5_s43", "g5_s44"])):
        sub = c[c.run.isin(seeds)]
        for md in ("decomp3", "ys_rt", "ys_abc"):
            s = sub[sub["mode"] == md]["best_pos_pct"]
            a = sub[sub["mode"] == md]["AP"]
            print(f"{fam:<10} {md:<8} bpp {s.mean():.4f} ± {s.std():.4f}"
                  f"（逐 seed {list(s.round(4))}）｜AP {a.mean():.4f} ± {a.std():.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
