"""make_f7_region_fig.py —— B08：`F7_region_correspondence.png` ✓（跨实现区域对应图 ✓）。

左：每个（host, inst, pair, region）的**区域内逐网证明率** ✓；
右：**区域边界证明率**（`boundary_match` full/partial/none 计数 ✓）。
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(_eqguard_path(''))
BASE = ROOT / "10.15/06_统一评测协议/N4_三向泛化"
FIG = ROOT / "10.15/07_论文图表/figs/F7_region_correspondence.png"


def main() -> int:
    df = pd.read_csv(BASE / "tables/region_pairs.csv", encoding="utf-8-sig")
    if df.empty:
        print("[warn] region_pairs 为空 ✗")
        return 1
    df["label"] = (df["host"].str[:6] + "/" + df["inst"].str[3:6] + "/"
                   + df["pair"].str.replace("ys_", "", regex=False) + "/"
                   + df["region"].str.replace("Trojan", "T", regex=False))
    fig, ax = plt.subplots(1, 2, figsize=(13.5, 4.6), dpi=150)

    d = df.sort_values(["host", "inst", "pair", "region"])
    ax[0].bar(range(len(d)), d["proved_ratio"], color="#40739e", width=0.7)
    step = max(1, len(d) // 28)
    ax[0].set_xticks(range(0, len(d), step))
    ax[0].set_xticklabels(d["label"].iloc[::step], rotation=90, fontsize=5)
    ax[0].set_ylim(0, 1.08)
    ax[0].set_ylabel("region-internal proved ratio (SAT)")
    ax[0].set_title("F7-a · per-region node equivalence (ys_id vs ys_abc / ys_opt)", fontsize=9)

    for i, (k, col) in enumerate((("full", "#2e8b57"), ("partial", "#e1b12c"),
                                  ("none", "#c23616"))):
        v = d["boundary_match"] == k
        ax[1].bar(range(len(d))[v.to_list()] if False else
                  [j for j, ok in enumerate(v) if ok],
                  d.loc[v, "boundary_proved_ratio"], width=0.7, color=col, label=k)
    ax[1].set_xticks(range(0, len(d), step))
    ax[1].set_xticklabels(d["label"].iloc[::step], rotation=90, fontsize=5)
    ax[1].set_ylim(0, 1.08)
    ax[1].set_ylabel("boundary proved ratio")
    ax[1].legend(fontsize=7, title="boundary_match", title_fontsize=7)
    ax[1].set_title("F7-b · region-boundary correspondence (full = every boundary net proved)",
                    fontsize=9)

    fig.suptitle("F7 · cross-implementation region correspondence (SAT-proved node pairs grouped "
                 "by trojan sub-circuit prefix)", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG)
    print(f"[out] {FIG}")
    print(d[["host", "inst", "pair", "region", "proved_ratio", "boundary_match"]].head(8).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
