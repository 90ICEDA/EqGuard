"""make_f7_region_fig3.py -- F7 v2 from region_pairs_v3 (all-proved pairs, no canonicalization)."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(_eqguard_path(''))
BASE = ROOT / "10.15/06_统一评测协议/N4_三向泛化"
OUT = ROOT / "10.15/07_论文图表/figs/F7_region_correspondence_v2.png"
COL = {"1:1": "#40739e", "1:N": "#e1b12c", "N:1": "#8e44ad", "unmatched": "#8c8c8c"}


def main() -> int:
    d = pd.read_csv(BASE / "tables/region_pairs_v3.csv", encoding="utf-8-sig").fillna("")
    if d.empty:
        print("[warn] empty"); return 1
    d["label"] = (d.host.str[:6] + "/" + d.inst.str[3:6] + "/"
                  + d.pair.str.replace("ys_", "", regex=False) + "/"
                  + d.region.str.replace("Trojan", "T", regex=False))
    d = d.sort_values(["host", "inst", "pair", "region"]).reset_index(drop=True)
    step = max(1, len(d) // 26)
    fig, ax = plt.subplots(1, 2, figsize=(13.5, 4.8), dpi=150)
    ax[0].bar(range(len(d)), d.n_pair_edges,
              color=[COL.get(x, "#8c8c8c") for x in d.match_type], width=0.75)
    ax[0].set_xticks(range(0, len(d), step))
    ax[0].set_xticklabels(d.label.iloc[::step], rotation=90, fontsize=5)
    ax[0].set_ylabel("SAT-proved node pairs bridging the region")
    ax[0].set_title("F7-a v3 · region correspondence (1:1 / 1:N / N:1)", fontsize=9)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in COL.values()]
    ax[0].legend(handles, list(COL.keys()), fontsize=6, title="match_type", title_fontsize=6)
    mt = d.match_type.value_counts(); rr = d.region_role.value_counts()
    y = range(len(mt))
    ax[1].barh(list(y), mt.values, color=[COL.get(k, "#8c8c8c") for k in mt.index])
    ax[1].set_yticks(list(y)); ax[1].set_yticklabels(mt.index, fontsize=8)
    for i, v in enumerate(mt.values):
        ax[1].text(v + 0.2, i, str(int(v)), va="center", fontsize=7)
    ax[1].set_xlabel("regions")
    ax[1].set_title("F7-b v3 · match_type counts\nregion roles: "
                    + ", ".join(f"{k}={int(v)}" for k, v in rr.items()), fontsize=9)
    fig.suptitle("F7 · cross-implementation region correspondence v3 "
                 "(974k node pairs; proved same-inst Trojan regions; no canonicalization)", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT)
    print(f"[out] {OUT} rows={len(d)}")
    print(mt.to_string()); print(rr.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
