"""sat_stratified_ap.py -- 分层 AP：all / covered / S / P / unknown, C v2 vs C v1."""
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
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"
T = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables"
F = ROOT / "10.15/07_论文图表/figs"
CV = ROOT / "results/hosts_bt31_seed42mode4_allb1_lro_fghtl_P3lroCv2s42/loco_summary.csv"


def main() -> int:
    d = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = d.y.numpy().astype(int)
    fid = np.asarray(json.load(open(WORK / "data/for_train/metadata_trans.json",
                                    encoding="utf-8"))["file_ids"])
    mask = np.load(PT / "satrel_node_mask_sat_p0clean2.npy").astype(bool)
    cov = mask.any(1)
    s2 = np.load(PT / "FGHTL_scores_C_v2.npy").astype(np.float32)
    s1 = np.load(PT / "FGHTL_scores_C_v1_clean.npy").astype(np.float32)
    meta = pd.read_csv(CV, encoding="utf-8-sig")
    m = (meta.Type.astype(str) == "TRANS") & meta.View.astype(str).str.contains("__inj")
    views = sorted(meta[m].View.astype(str).unique())
    strata = {
        "all": np.ones(len(y), bool),
        "covered": cov,
        "S": mask[:, 0],
        "P": mask[:, 1],
        "unknown": ~cov,
    }
    rows = []
    for meth, sc in (("C_v2", s2), ("C_v1_clean", s1)):
        for v in views:
            idx = np.where(fid == v)[0]
            yy = y[idx]
            for name, sm in strata.items():
                sel = sm[idx]
                yy2 = yy[sel]
                if len(yy2) < 10 or yy2.min() == yy2.max():
                    rows.append(dict(method=meth, view=v, stratum=name, n=len(yy2),
                                     n_pos=int(yy2.sum()), ap=np.nan, auc=np.nan))
                    continue
                ss = sc[idx][sel]
                rows.append(dict(method=meth, view=v, stratum=name, n=len(yy2),
                                 n_pos=int(yy2.sum()),
                                 ap=float(average_precision_score(yy2, ss)),
                                 auc=float(roc_auc_score(yy2, ss))))
    r = pd.DataFrame(rows)
    r.to_csv(T / "SAT_stratified_AP.csv", index=False, encoding="utf-8-sig")
    sm = (r.groupby(["method", "stratum"]).agg(n_views=("view", "nunique"),
                                                n_pos=("n_pos", "sum"),
                                                ap=("ap", "mean"), auc=("auc", "mean"))
          .reset_index())
    sm.to_csv(T / "SAT_stratified_AP_summary.csv", index=False, encoding="utf-8-sig")
    print(sm.to_string(index=False))

    order = ["all", "covered", "S", "P", "unknown"]
    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=200)
    x = np.arange(len(order)); w = 0.36
    for j, meth in enumerate(["C_v2", "C_v1_clean"]):
        vals = [float(sm[(sm.method == meth) & (sm.stratum == s)].ap.iloc[0]) if len(sm[(sm.method == meth) & (sm.stratum == s)]) else np.nan for s in order]
        ax.bar(x + (j - 0.5) * w, vals, w, label=meth, color=["#40739e", "#e1b12c"][j])
        for i, v in enumerate(vals):
            if not np.isnan(v):
                ax.text(i + (j - 0.5) * w, v, f"{v:.3f}", ha="center", va="bottom", fontsize=5)
    ax.set_xticks(x); ax.set_xticklabels(order)
    ax.set_ylabel("AP_T (mean over inj views)")
    ax.set_title("SAT coverage-stratified AP (24 inj views; C v2 vs C v1 clean)", fontsize=9)
    ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(F / "SAT_stratified_AP.png"); plt.close(fig)
    print(f"[out] {F / 'SAT_stratified_AP.png'}")
    print(f"[out] {T / 'SAT_stratified_AP_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
