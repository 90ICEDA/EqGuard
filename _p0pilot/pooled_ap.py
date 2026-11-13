"""pooled_ap.py -- pooled AP/AUC over the 24 inj views (tiny positives, 6-17 each).

Why: per-view AP with ~10 positives among 10k-24k nodes is extremely volatile;
the mean over 24 views can swing 0.05 from a single node's rank. Pooling with
within-view percentile normalisation gives one number over 243 positives.

Usage:
  python _p0pilot/pooled_ap.py <scores.npz> [<scores.npz> ...]

Needs: trans_graph.pt (y, test mask), metadata_trans.json (file_ids).
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import json
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"


def load_meta():
    d = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    y = d.y.numpy().astype(np.int8)
    fid = np.asarray(json.load(open(WORK / "data/for_train/metadata_trans.json",
                                    encoding="utf-8"))["file_ids"], dtype=object)
    inj = np.array([("__inj" in str(v)) for v in fid])
    return y, fid, inj


def pct_within_view(idx: np.ndarray, score: np.ndarray, group: np.ndarray) -> np.ndarray:
    """Tie-aware within-group percentile rank (average rank for ties, scaled to [0,1]).

    Using double argsort is WRONG when a group has many identical scores (e.g. all zero):
    argsort then returns the identity permutation and assigns a ramp by node index,
    fabricating an ordering that does not exist.
    """
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
    y, fid, inj = load_meta()
    for path in sys.argv[1:]:
        z = np.load(path)
        idx, score, test = z["idx"], z["score"].astype(np.float32), z["test"].astype(bool)
        keep = test & inj[idx]
        ii, ss = idx[keep], score[keep]
        yy = y[ii]
        grp = fid[ii]
        s_pct = pct_within_view(ii, ss, grp)
        ap = average_precision_score(yy, s_pct)
        auc = roc_auc_score(yy, s_pct)
        # mean per-view AP for reference
        aps = []
        for g in np.unique(grp):
            m = grp == g
            if yy[m].sum() > 0 and yy[m].min() != yy[m].max():
                aps.append(average_precision_score(yy[m], s_pct[m]))
        print(f"{Path(path).name}: n={len(ii)} pos={int(yy.sum())} "
              f"pooled_AP={ap:.4f} pooled_AUC={auc:.4f} "
              f"viewmean_AP={np.mean(aps):.4f} views={len(aps)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
