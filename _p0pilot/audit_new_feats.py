"""audit_new_feats.py -- leakage audit: single-feature AP/AUC by label + pair train coverage."""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"
T = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables"
CV = ROOT / "results/hosts_bt31_seed42mode4_allb1_lro_fghtl_P3lroCv2s42/loco_summary.csv"

NAMES = ["n_rel_log", "frac_decided", "frac_influence", "frac_proved",
         "reach_po_log", "reach_dff_log", "p1_ratio", "is_S", "is_P", "covered"]


def main() -> int:
    import sys
    npy = Path(sys.argv[1]) if len(sys.argv) > 1 else PT / "satrel_node_feats_sat_p0clean3.npy"
    out_tag = sys.argv[2] if len(sys.argv) > 2 else ""
    d = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = d.y.numpy().astype(int)
    fid = np.asarray(json.load(open(WORK / "data/for_train/metadata_trans.json",
                                    encoding="utf-8"))["file_ids"])
    x = np.load(npy)
    names = NAMES if not out_tag else json.loads(
        (PT / f"satrel_node_feats_sat_p0clean4_meta.json").read_text(encoding="utf-8")
    )["names"][out_tag]
    meta = pd.read_csv(CV, encoding="utf-8-sig")
    m = (meta.Type.astype(str) == "TRANS") & meta.View.astype(str).str.contains("__inj")
    views = sorted(meta[m].View.astype(str).unique())

    rows = []
    for j, name in enumerate(names[:x.shape[1]]):
        vals, labs = [], []
        for v in views:
            idx = np.where(fid == v)[0]
            yy = y[idx]
            if len(yy) < 10 or yy.min() == yy.max():
                continue
            s = x[idx, j]
            if np.unique(s).size < 2:
                continue
            vals.append(average_precision_score(yy, s))
            labs.append(roc_auc_score(yy, s))
        rows.append(dict(feature=name, n_views=len(vals),
                         ap=float(np.mean(vals)) if vals else np.nan,
                         auc=float(np.mean(labs)) if labs else np.nan,
                         nonzero=float((x[:, j] != 0).mean()),
                         mean_pos=float(x[y == 1, j].mean()),
                         mean_neg=float(x[y == 0, j].mean())))
    a = pd.DataFrame(rows)
    tag = f"_{out_tag}" if out_tag else ""
    a.to_csv(T / f"new_feature_leak_audit{tag}.csv", index=False, encoding="utf-8-sig")
    print(a.round(4).to_string(index=False))

    z = np.load(PT / "satrel_node_pairs_labelclean_v2.npz")
    a1, b1, k1 = z["a"], z["b"], z["kind"]
    m1 = k1 == 1
    tm = getattr(d, "train_mask", None)
    if tm is not None:
        tm = tm.numpy().astype(bool)
        both = tm[a1[m1]] & tm[b1[m1]]
        print(f"[pairs] kind1={int(m1.sum())} both_train={int(both.sum())} "
              f"test_or_val={int(m1.sum()-both.sum())}")
        print(f"[pairs] train nodes={int(tm.sum())} total={len(tm)}")
    else:
        print("[pairs] no train_mask in trans_graph")
    print(f"[out] {T / 'new_feature_leak_audit.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
