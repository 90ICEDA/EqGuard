"""make_8pm_outputs.py -- Q1/Q3 figures + P2 v2 table + F6 v2 copy for the 20:00 summary."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(_eqguard_path(''))
R = ROOT / "results"
T = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables"
F = ROOT / "10.15/07_论文图表/figs"

RUNS = {
    "B": "hosts_bt31_seed42mode4_allb1_fold_v31a_A2s42",
    "C_n_s42": "hosts_bt31_seed42mode4_allb1_fold_fghtl_CncleanV2R42",
    "C_n_s1": "hosts_bt31_seed1mode4_allb1_fold_fghtl_CncleanV2R1",
    "C_n_s2": "hosts_bt31_seed2mode4_allb1_fold_fghtl_CncleanV2R2",
    "D_n_s42": "hosts_bt31_seed42mode4_allb1_fold_fghtl_DncleanV2R42",
    "D_n_s1": "hosts_bt31_seed1mode4_allb1_fold_fghtl_DncleanV2R1",
}


def fold_metrics(run: str) -> dict:
    d = pd.read_csv(R / run / "loco_summary.csv", encoding="utf-8-sig")
    m = (d["Type"].astype(str) == "TRANS") & d["View"].astype(str).str.contains("__inj")
    x = d[m].groupby(["Split", "View"]).agg(AP_T=("AP_T", "mean"),
                                            AUC_T=("ROC-AUC_T", "mean"),
                                            R1_T=("Recall@1%_T", "mean"),
                                            R5_T=("Recall@5%_T", "mean"))
    return {k: float(x[k].mean()) for k in x.columns} | {
        "n_views": int(len(x)),
        "cec": float((d["CEC_Status"].astype(str) == "PASS").mean()),
    }


def main() -> int:
    b = fold_metrics(RUNS["B"])
    cs = [fold_metrics(RUNS["C_n_s42"]), fold_metrics(RUNS["C_n_s1"]), fold_metrics(RUNS["C_n_s2"])]
    ds = [fold_metrics(RUNS["D_n_s42"]), fold_metrics(RUNS["D_n_s1"])]
    c_mean = {k: float(np.mean([x[k] for x in cs])) for k in ("AP_T", "AUC_T", "R1_T", "R5_T")}
    c_std = {k: float(np.std([x[k] for x in cs], ddof=1)) for k in ("AP_T", "AUC_T", "R1_T", "R5_T")}
    d_mean = {k: float(np.mean([x[k] for x in ds])) for k in ("AP_T", "AUC_T", "R1_T", "R5_T")}

    rows = [
        dict(variant="A", label="结构 GNN（39 维）", seeds=3, ap_mean=0.072173, ap_std=0.109463,
             auc_mean=0.630349, auc_std=0.189967, r1_mean=0.192395, r5_mean=0.297823,
             cec_pass_rate=1.0, feat_level="view", notes="T16 A"),
        dict(variant="B", label="双分支（39 维）", seeds=3, ap_mean=0.142492, ap_std=0.022134,
             auc_mean=0.769485, auc_std=0.014273, r1_mean=0.377699, r5_mean=0.479700,
             cec_pass_rate=1.0, feat_level="view", notes="T16 B"),
        dict(variant="C", label="+ 视图级 SAT（未跑）", seeds=0, feat_level="view", notes="未跑"),
        dict(variant="D", label="+ L_eq（视图级，未跑）", seeds=0, feat_level="view", notes="未跑"),
        dict(variant="E", label="+ L_pair（视图级，未跑）", seeds=0, feat_level="view", notes="未跑"),
        dict(variant="C_n", label="+ 节点级 SAT（51 维）", seeds=3, ap_mean=c_mean["AP_T"], ap_std=c_std["AP_T"],
             auc_mean=c_mean["AUC_T"], auc_std=c_std["AUC_T"], r1_mean=c_mean["R1_T"], r5_mean=c_mean["R5_T"],
             cec_pass_rate=0.9846, feat_level="node", notes="seed 42/1/2; 64/65 CEC PASS"),
        dict(variant="D_n", label="C_n + L_eq（51 维）", seeds=2, ap_mean=d_mean["AP_T"],
             ap_std=float(np.std([x["AP_T"] for x in ds], ddof=1)),
             auc_mean=d_mean["AUC_T"], auc_std=float(np.std([x["AUC_T"] for x in ds], ddof=1)),
             r1_mean=d_mean["R1_T"], r5_mean=d_mean["R5_T"], cec_pass_rate=0.9846,
             feat_level="node", notes="seed 42/1; 2 seed"),
        dict(variant="E_n", label="D_n + L_pair（未跑）", seeds=0, feat_level="node", notes="E 未跑"),
        dict(variant="C_nn", label="C_n 去 covered（未跑）", seeds=0, feat_level="node", notes="未跑"),
        dict(variant="C_n_perm", label="C_n 置换（未跑）", seeds=0, feat_level="node", notes="未跑"),
        dict(variant="C_n_driver", label="C_n driver-only（未跑）", seeds=0, feat_level="node", notes="未跑"),
    ]
    t = pd.DataFrame(rows)
    t["delta_ap_vs_B"] = t["ap_mean"] - 0.142492
    t.to_csv(T / "fg_htl_ablation_v2.csv", index=False, encoding="utf-8-sig")
    print("[out] fg_htl_ablation_v2.csv")
    # ---- Q1 figure ----
    fig, ax = plt.subplots(1, 3, figsize=(12.5, 3.8), dpi=200)
    ax[0].bar(["44 (cone5)", "56 (cone5+SAT)"], [0.1401, 0.1753], color=["#7f8fa6", "#40739e"])
    ax[0].set_title("LOCO AP_T (seed42)", fontsize=9); ax[0].set_ylim(0, 0.22)
    for i, v in enumerate([0.1401, 0.1753]):
        ax[0].text(i, v + 0.005, f"{v:.3f}", ha="center", fontsize=8)
    ax[1].bar(["44", "51 (SAT)", "56 (cone5+SAT)"], [0.0116, 0.0786, 0.0196],
              color=["#7f8fa6", "#e84118", "#40739e"])
    ax[1].set_title("LRO ys_abc AP_T (5 inj views)", fontsize=9); ax[1].set_ylim(0, 0.10)
    for i, v in enumerate([0.0116, 0.0786, 0.0196]):
        ax[1].text(i, v + 0.002, f"{v:.3f}", ha="center", fontsize=8)
    ax[2].bar(["B (39)", "C_n (51)"], [0.1425, 0.1587], yerr=[0.0221, 0.0110],
              color=["#7f8fa6", "#40739e"], capsize=3)
    ax[2].set_title("fold 3-seed AP_T", fontsize=9); ax[2].set_ylim(0, 0.22)
    for i, v in enumerate([0.1425, 0.1587]):
        ax[2].text(i, v + 0.008, f"{v:.3f}", ha="center", fontsize=8)
    fig.suptitle("Q1: does SAT help localization? (AP_T; LRO only ys_abc 56-dim)", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(F / "Q1_functional_gain.png"); plt.close(fig)
    pd.DataFrame([
        dict(setting="LOCO_44", AP_T=0.1401), dict(setting="LOCO_56", AP_T=0.1753),
        dict(setting="LRO_ys_abc_44", AP_T=0.0116), dict(setting="LRO_ys_abc_51", AP_T=0.0786),
        dict(setting="LRO_ys_abc_56", AP_T=0.0196), dict(setting="fold_B_3seed", AP_T=0.1425, std=0.0221),
        dict(setting="fold_C_n_3seed", AP_T=0.1587, std=0.0110),
    ]).to_csv(T / "Q1_evidence.csv", index=False, encoding="utf-8-sig")

    # ---- Q3 figure (legacy A4) ----
    fig, ax = plt.subplots(figsize=(6.2, 3.6), dpi=200)
    labels = ["a4ctldead", "a4ctlequiv"]
    auc = [0.9976, 0.9976]; top1 = [0.9545, 0.9545]; top5 = [1.0, 1.0]
    x = np.arange(len(labels)); w = 0.25
    ax.bar(x - w, auc, w, label="AUC(rank)", color="#40739e")
    ax.bar(x, top1, w, label="top-1%", color="#e1b12c")
    ax.bar(x + w, top5, w, label="top-5%", color="#8e44ad")
    ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylim(0, 1.12)
    ax.set_ylabel("score")
    ax.set_title("Q3: A4 structure-matched control (legacy model)\nFPR = 0.000 for both", fontsize=9)
    ax.legend(fontsize=7); fig.tight_layout(); fig.savefig(F / "Q3_a4_control.png"); plt.close(fig)
    pd.DataFrame([dict(control="a4ctldead", AUC=0.9976, FPR=0.0, top1=0.9545, top5=1.0, n=8),
                  dict(control="a4ctlequiv", AUC=0.9976, FPR=0.0, top1=0.9545, top5=1.0, n=8)]
                 ).to_csv(T / "Q3_a4_evidence.csv", index=False, encoding="utf-8-sig")

    # ---- F6 v2 copy ----
    src = F / "F6_functional_relations_p0v2.png"
    if src.exists():
        shutil.copy2(src, F / "F6_functional_relations_v2.png")

    print("[out] Q1_functional_gain.png / Q1_evidence.csv")
    print("[out] Q3_a4_control.png / Q3_a4_evidence.csv")
    print("[out] F6_functional_relations_v2.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
