"""profile_trojan_feats.py -- how prominent is each SAT feature on Trojan nodes,
and how far does a SINGLE-feature rule get (pooled AP) vs the trained GNN?

Only test nodes of the 24 __inj views are used (no label leakage into training).
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"
SAFE = PT / "satrel_node_feats_sat_p0clean4_safe.npy"
NAMES = ["n_rel_log", "frac_decided", "frac_influence", "frac_proved",
         "reach_po_log", "reach_dff_log", "p1_ratio",
         "n_gate_log", "n_mux_log", "n_cone_log", "n_dff_log",
         "frac_proved_sat", "frac_partial_sat", "covered"]


def pct_within_view(idx, score, group):
    from scipy.stats import rankdata

    out = np.zeros(len(idx), np.float32)
    order = np.argsort(group, kind="stable")
    g_sorted = group[order]
    starts = np.searchsorted(g_sorted, np.unique(g_sorted), side="left").tolist() + [len(order)]
    for k in range(len(starts) - 1):
        sel = order[starts[k]:starts[k + 1]]
        if sel.size == 0:
            continue
        r = rankdata(score[sel], method="average").astype(np.float32) - 1.0
        out[sel] = r / max(sel.size - 1, 1)
    return out


def main() -> int:
    d = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = d.y.numpy().astype(np.int8)
    tm = getattr(d, "test_mask", None)
    tm = tm.numpy().astype(bool) if tm is not None else np.ones(len(y), bool)
    fid = np.asarray(json.load(open(WORK / "data/for_train/metadata_trans.json",
                                    encoding="utf-8"))["file_ids"], dtype=object)
    inj = np.array([("__inj" in str(v)) for v in fid])

    keep = tm & inj
    idx = np.flatnonzero(keep)
    yy = y[idx].astype(int)
    grp = fid[idx]
    print(f"[scope] test&inj nodes={len(idx)} trojan={int(yy.sum())} views={len(np.unique(grp))}")

    x = np.load(SAFE, mmap_mode="r")
    rows = []
    for j, nm in enumerate(NAMES):
        s = np.asarray(x[idx, j]).astype(np.float32)
        pos, neg = s[yy == 1], s[yy == 0]
        sp = pct_within_view(idx, s, grp)
        ap = average_precision_score(yy, sp)
        auc = roc_auc_score(yy, sp) if np.unique(sp).size > 1 else float("nan")
        rows.append(dict(
            feature=nm,
            trojan_mean=float(pos.mean()), benign_mean=float(neg.mean()),
            enrich=float(pos.mean() / neg.mean()) if neg.mean() > 0 else float("inf"),
            trojan_nonzero=float((pos != 0).mean()), benign_nonzero=float((neg != 0).mean()),
            pooled_AP=float(ap), pooled_AUC=float(auc)))

    print("\n| feature | trojan_mean | benign_mean | enrich | trojan_nz | benign_nz | AP | AUC |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        print(f"| `{r['feature']}` | {r['trojan_mean']:.4f} | {r['benign_mean']:.4f} | "
              f"{r['enrich']:.2f}x | {r['trojan_nonzero']:.3f} | {r['benign_nonzero']:.3f} | "
              f"{r['pooled_AP']:.4f} | {r['pooled_AUC']:.4f} |")

    # simple boolean rules
    def rule_ap(mask: np.ndarray, name: str):
        s = mask.astype(np.float32)
        sp = pct_within_view(idx, s, grp)
        return dict(rule=name, trojan_rate=float(mask[yy == 1].mean()),
                    benign_rate=float(mask[yy == 0].mean()),
                    pooled_AP=float(average_precision_score(yy, sp)))

    z = np.load(SAFE, mmap_mode="r")
    cols = {nm: np.asarray(z[idx, j]) for j, nm in enumerate(NAMES)}
    rules = [
        rule_ap(cols["covered"] > 0, "covered>0"),
        rule_ap(cols["n_rel_log"] > 0, "n_rel>0"),
        rule_ap(cols["n_mux_log"] > 0, "n_mux>0"),
        rule_ap(cols["n_gate_log"] > 0, "gate case>0"),
        rule_ap(cols["n_cone_log"] > 0, "cone case>0"),
        rule_ap(cols["frac_proved_sat"] > 0, "proved_sat flag"),
        rule_ap(cols["frac_partial_sat"] > 0, "partial_sat flag"),
        rule_ap(cols["reach_po_log"] > 0, "reach_po>0"),
        rule_ap((cols["n_mux_log"] > 0) | (cols["n_rel_log"] > 0), "n_mux OR n_rel"),
        rule_ap((cols["n_mux_log"] > 0) | (cols["reach_po_log"] > 0), "n_mux OR reach_po"),
        rule_ap((cols["n_mux_log"] > 0) | (cols["n_gate_log"] > 0) | (cols["n_cone_log"] > 0),
                "any case type"),
    ]
    print("\n| rule | trojan_rate | benign_rate | pooled_AP |")
    print("|---|---:|---:|---:|")
    for r in rules:
        print(f"| {r['rule']} | {r['trojan_rate']:.4f} | {r['benign_rate']:.4f} | {r['pooled_AP']:.4f} |")
    print("\n[ref] trained models: B=0.0388 core=0.0477 verdict=0.0625 safe=0.0680")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
