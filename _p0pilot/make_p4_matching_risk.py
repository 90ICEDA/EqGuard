"""make_p4_matching_risk.py -- P4 图1b: 832 SAT-aligned pairs, C v2 risk scores + matching reliability."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"
T = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables"
F = ROOT / "10.15/07_论文图表/figs"


def main() -> int:
    p = np.load(PT / "satrel_node_pairs_labelclean.npz")
    a, b, kind = p["a"], p["b"], p["kind"]
    d = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = d.y.numpy().astype(int)
    m = (kind == 0) & (y[a] == 1) & (y[b] == 1)
    a, b = a[m], b[m]
    fid = np.asarray(json.load(open(WORK / "data/for_train/metadata_trans.json",
                                    encoding="utf-8"))["file_ids"])
    s2 = np.load(PT / "FGHTL_scores_C_v2.npy").astype(np.float32)
    s1 = np.load(PT / "FGHTL_scores_C_v1_clean.npy").astype(np.float32)

    def parse(v):
        q = str(v).split("__")
        return (q[0], q[1].replace("_d1_s42", ""), q[2] if len(q) > 2 else "")

    rows = []
    for i in range(len(a)):
        va, vb = str(fid[a[i]]), str(fid[b[i]])
        ha, ia, ra = parse(va)
        hb, ib, rb = parse(vb)
        rows.append(dict(pair=i, node_a=int(a[i]), node_b=int(b[i]),
                         view_a=va, view_b=vb, host=ha, inst=ia,
                         recipe_a=ra, recipe_b=rb,
                         y_a=int(y[a[i]]), y_b=int(y[b[i]]),
                         score_a_c2=float(s2[a[i]]), score_b_c2=float(s2[b[i]]),
                         score_a_c1=float(s1[a[i]]), score_b_c1=float(s1[b[i]])))
    df = pd.DataFrame(rows)
    df["absdiff_c2"] = (df["score_a_c2"] - df["score_b_c2"]).abs()
    df["absdiff_c1"] = (df["score_a_c1"] - df["score_b_c1"]).abs()
    df["mean_c2"] = (df["score_a_c2"] + df["score_b_c2"]) / 2
    df.to_csv(T / "P4_matching_risk_pairs.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(1, 3, figsize=(12.6, 3.9), dpi=200)
    hosts = sorted(df["host"].unique())
    cols = plt.cm.tab10(np.linspace(0, 1, max(len(hosts), 1)))
    for h, c in zip(hosts, cols):
        g = df[df["host"] == h]
        ax[0].scatter(g["score_a_c2"], g["score_b_c2"], s=9, alpha=0.65, color=c, label=h)
    ax[0].plot([0, 1], [0, 1], "k--", lw=0.8)
    ax[0].set_xlim(0, 1); ax[0].set_ylim(0, 1)
    ax[0].set_xlabel("score in view A"); ax[0].set_ylabel("score in view B")
    ax[0].set_title("C v2 risk scores on matched pairs", fontsize=9)
    ax[0].legend(fontsize=5, markerscale=1.2, loc="lower right")

    bins = np.linspace(0, max(df["absdiff_c2"].max(), df["absdiff_c1"].max(), 0.05), 35)
    ax[1].hist(df["absdiff_c2"], bins=bins, alpha=0.65, label="C v2", color="#40739e")
    ax[1].hist(df["absdiff_c1"], bins=bins, alpha=0.55, label="C v1 clean", color="#e1b12c")
    ax[1].set_xlabel("|score(A) - score(B)|"); ax[1].set_ylabel("pairs")
    ax[1].set_title("within-pair score difference", fontsize=9)
    ax[1].legend(fontsize=7)

    met = pd.read_csv(T / "FGHTL_stability_832_summary.csv", encoding="utf-8-sig").set_index("method")
    keys = ["mean_pair_std", "mean_absdiff", "top5_overlap", "flip_top5"]
    x = np.arange(len(keys)); w = 0.36
    ax[2].bar(x - w / 2, [met.loc["C_v2", k] for k in keys], w, label="C v2", color="#40739e")
    ax[2].bar(x + w / 2, [met.loc["C_v1_clean", k] for k in keys], w, label="C v1 clean", color="#e1b12c")
    ax[2].set_xticks(x); ax[2].set_xticklabels(["std", "|Δ|", "top5\noverlap", "flip\ntop5"], fontsize=7)
    ax[2].set_title("reliability metrics (lower std/|Δ|; higher overlap)", fontsize=8)
    ax[2].legend(fontsize=7)
    for i, k in enumerate(keys):
        ax[2].text(i - w / 2, met.loc["C_v2", k], f"{met.loc['C_v2', k]:.3f}", ha="center", fontsize=5)
        ax[2].text(i + w / 2, met.loc["C_v1_clean", k], f"{met.loc['C_v1_clean', k]:.3f}", ha="center", fontsize=5)

    fig.suptitle("P4: reliable matched signals + risk prediction (832 SAT-aligned positive pairs)", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(F / "P4_matching_risk.png")
    plt.close(fig)
    print(f"[out] {F / 'P4_matching_risk.png'}")
    print(f"[out] {T / 'P4_matching_risk_pairs.csv'} ({len(df)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
