"""mux_shift_test.py -- is `n_mux` an artifact (sampling x MUX inventory) or a real cue?

Split the 24 inj test views by how many MUX cells the design has:
  * low-MUX designs: --mux-cases (20) >= inventory  -> candidate sampling saturates
  * high-MUX designs: sampling covers only a small fraction
If the n_mux cue is an artifact of saturation, its advantage should shrink in high-MUX designs.
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import json
import re
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score
from scipy.stats import rankdata

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"
TRANS = WORK / "trans"
SAFE = PT / "satrel_node_feats_sat_p0clean4_safe.npy"
MUX_RE = re.compile(r"\b(MX2X1_RS|MUX2X1|MUX2)\b")


def pct(idx, score, group):
    out = np.zeros(len(idx), np.float32)
    order = np.argsort(group, kind="stable")
    gs = group[order]
    starts = np.searchsorted(gs, np.unique(gs), side="left").tolist() + [len(order)]
    for k in range(len(starts) - 1):
        sel = order[starts[k]:starts[k + 1]]
        if sel.size == 0:
            continue
        r = rankdata(score[sel], method="average").astype(np.float32) - 1.0
        out[sel] = r / max(sel.size - 1, 1)
    return out


def mux_inventory() -> dict[str, int]:
    out = {}
    for p in TRANS.glob("*.v"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        out[p.name[:-2]] = len(MUX_RE.findall(txt))
    return out


def main() -> int:
    d = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = d.y.numpy().astype(np.int8)
    tm = getattr(d, "test_mask", None)
    tm = tm.numpy().astype(bool) if tm is not None else np.ones(len(y), bool)
    fid = np.asarray(json.load(open(WORK / "data/for_train/metadata_trans.json",
                                    encoding="utf-8"))["file_ids"], dtype=object)
    inv = mux_inventory()
    keep = tm & np.array([("__inj" in str(v)) for v in fid])
    idx = np.flatnonzero(keep)
    yy = y[idx].astype(int)
    grp = fid[idx]
    views = np.unique(grp)
    n_mux = np.array([inv.get(str(v), -1) for v in views])
    print("[views] inj views=%d  mux inventory: min=%d median=%d max=%d" %
          (len(views), n_mux.min(), int(np.median(n_mux)), n_mux.max()))

    x = np.load(SAFE, mmap_mode="r")
    flag = (np.asarray(x[idx, 8]) > 0).astype(np.float32)
    z = np.load(ROOT / "_devcfg/gnn_v4safeD_s42.npz")
    sidx, sscore = z["idx"].astype(np.int64), z["score"].astype(np.float32)
    score_map = {int(i): float(s) for i, s in zip(sidx, sscore)}

    for name, sel_views in (
            ("low-MUX (<=20)", views[n_mux <= 20]),
            ("high-MUX (>20)", views[n_mux > 20])):
        m = np.isin(grp, sel_views)
        if m.sum() == 0:
            continue
        gi, gy, gg = idx[m], yy[m], grp[m]
        f = flag[m]
        sf = pct(gi, f, gg)
        p = np.array([score_map.get(int(i), np.nan) for i in gi], dtype=np.float32)
        ok = ~np.isnan(p)
        sp = pct(gi[ok], p[ok], gg[ok])
        print(f"\n[{name}] views={len(sel_views)} nodes={int(m.sum())} pos={int(gy.sum())}")
        print(f"  n_mux>0 : rate_pos={f[gy == 1].mean():.3f} rate_neg={f[gy == 0].mean():.4f}"
              f"  AP={average_precision_score(gy, sf):.4f}")
        if ok.sum() and gy[ok].sum() > 0:
            print(f"  model   : AP={average_precision_score(gy[ok], sp):.4f}"
                  f"  AUC={roc_auc_score(gy[ok], sp):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
