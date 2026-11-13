"""make_f6_p0v2.py -- F6-v2 from label-agnostic P0 (independent of legacy F6).

Input : _p0pilot/functional_relations_agnostic.csv
Outputs:
  tables/functional_relations_p0v2.csv
  tables/sat_summary_p0v2.csv
  figs/F6_functional_relations_p0v2.png

The legacy F6 and its per-host CSVs are not modified.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(_eqguard_path(''))
P0 = ROOT / "_p0pilot/functional_relations_agnostic.csv"
TDIR = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables"
FIGD = ROOT / "10.15/07_论文图表/figs"


def main() -> int:
    d = pd.read_csv(P0, encoding="utf-8-sig").fillna("")
    d["host"] = d["top"].astype(str).str.split("__").str[0]
    for q in ("sat_q1", "sat_q2", "sat_q3", "sat_q4"):
        d[q] = d[q].astype(str).str.lower()
    d["q_unknown"] = d[[f"sat_q{i}" for i in (1, 2, 3, 4)]].eq("unknown").sum(1)
    d["q_proved"] = d[[f"sat_q{i}" for i in (1, 2, 3, 4)]].eq("proved").sum(1)
    d["q_refuted"] = d[[f"sat_q{i}" for i in (1, 2, 3, 4)]].eq("refuted").sum(1)
    d["status_eff"] = np.where(d["q_unknown"] > 0, "unknown", d["status"])
    d["struct_reach"] = ((pd.to_numeric(d["n_po_reached"], errors="coerce").fillna(0) +
                          pd.to_numeric(d["n_dff_reached"], errors="coerce").fillna(0)) > 0).astype(int)
    d.to_csv(TDIR / "functional_relations_p0v2.csv", index=False, encoding="utf-8-sig")

    sm = (d.groupby(["host", "kind"])
          .agg(rows=("status", "size"),
               proved=("status", lambda s: int((s == "proved").sum())),
               partial=("status", lambda s: int((s == "partial").sum())),
               unknown=("status_eff", lambda s: int((s == "unknown").sum())),
               decided=("decided", "mean"),
               influence=("influence", "mean"),
               struct_reach=("struct_reach", "mean"),
               po=("n_po_reached", "mean"),
               dff=("n_dff_reached", "mean"))
          .reset_index())
    sm.to_csv(TDIR / "sat_summary_p0v2.csv", index=False, encoding="utf-8-sig")

    fig, ax = plt.subplots(2, 2, figsize=(12.5, 8.0), dpi=150)

    # A: relation graph from a proved row
    a = ax[0, 0]
    cand = d[(d["status"] == "proved") & d["kind"].isin(["gate", "mux"])]
    row = cand.iloc[0] if len(cand) else d.iloc[0]
    cuts = [x for x in str(row["cut_nets"]).split(";") if x]
    if not cuts:
        cuts = ["(cut)"]
    a.set_xlim(-0.2, 3.2)
    a.set_ylim(-0.6, max(len(cuts), 2) - 0.4)
    ys = [len(cuts) - 1 - i for i in range(len(cuts))]
    for y, nm in zip(ys, cuts):
        a.scatter([0], [y], s=700, color="#40739e", zorder=3)
        a.text(0, y, nm[:22], ha="center", va="center", fontsize=6, color="white", zorder=4)
    ym = sum(ys) / len(ys)
    col = "#2e8b57" if row["status"] == "proved" else "#8c8c8c"
    a.scatter([1.35], [ym], s=1100, color=col, zorder=3)
    a.text(1.35, ym, f"{row['kind']}\n{str(row['cell'])[:18]}", ha="center", va="center",
           fontsize=6, color="white", zorder=4)
    for y in ys:
        a.annotate("", xy=(1.15, ym), xytext=(0.15, y),
                   arrowprops=dict(arrowstyle="-|>", color="#40739e", lw=1.1))
    a.scatter([2.65], [ym], s=800, color="#e84118", zorder=3)
    a.text(2.65, ym, f"{str(row['target'])[:18]}", ha="center", va="center",
           fontsize=6, color="white", zorder=4)
    a.annotate("", xy=(2.45, ym), xytext=(1.55, ym),
               arrowprops=dict(arrowstyle="-|>", color=col, lw=1.4))
    a.text(2.05, ym + .28, "observable", ha="center", fontsize=6, color=col)
    npo, ndff = int(float(row["n_po_reached"])), int(float(row["n_dff_reached"]))
    a.text(2.05, ym - .38, f"PO×{npo} / DFF×{ndff}", ha="center", fontsize=6, color="#e84118")
    a.set_title(f"A · relation graph · {row['host']} / {row['inst']} / {row['recipe']}\n"
                f"cut → {row['kind']} → target · decided={int(row['decided'])} "
                f"influence={int(row['influence'])} · {row['status_eff']}", fontsize=7)
    a.axis("off")

    # B: effective status counts by kind
    b = ax[0, 1]
    ct = d.groupby(["kind", "status_eff"]).size().unstack(fill_value=0)
    ct.plot(kind="bar", stacked=True, ax=b, color=["#40739e", "#e1b12c", "#e84118", "#8c8c8c"])
    b.set_title("B · P0 cases by kind and effective status", fontsize=8)
    b.set_ylabel("cases")
    b.tick_params(axis="x", rotation=0)
    b.legend(fontsize=6, title="status", title_fontsize=6)

    # C: structural reach
    c = ax[1, 0]
    vals = [d.loc[d["status"] == s, "struct_reach"].mean() for s in ("proved", "partial")]
    c.bar([0, 1], vals, color=["#2e8b57", "#8c8c8c"], width=.55)
    c.set_xticks([0, 1])
    c.set_xticklabels(["proved", "partial"])
    c.set_ylim(0, 1.05)
    c.set_ylabel("fraction with PO/DFF reach")
    c.set_title("C · structural observability (not SAT proof)", fontsize=8)
    for i, v in enumerate(vals):
        c.text(i, v + .02, f"{v:.2f}", ha="center", fontsize=7)

    # D: proved rate by host/kind
    dd = ax[1, 1]
    keys = [f"{r.host}/{r.kind}" for r in sm.itertuples()]
    rate = [r.proved / max(r.rows, 1) for r in sm.itertuples()]
    dd.bar(range(len(rate)), rate, color="#40739e")
    dd.set_xticks(range(len(rate)))
    dd.set_xticklabels(keys, rotation=90, fontsize=5)
    dd.set_ylim(0, 1.0)
    dd.set_ylabel("proved / cases")
    dd.set_title("D · effective proved rate by host and kind", fontsize=8)

    fig.suptitle("F6-v2 · label-agnostic P0 (legacy 4-pattern SAT + structural reach)", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, .95))
    out = FIGD / "F6_functional_relations_p0v2.png"
    fig.savefig(out)
    print(f"[out] {TDIR / 'functional_relations_p0v2.csv'} rows={len(d)}")
    print(f"[out] {TDIR / 'sat_summary_p0v2.csv'} rows={len(sm)}")
    print(f"[out] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
