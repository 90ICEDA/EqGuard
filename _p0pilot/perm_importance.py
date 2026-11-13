"""perm_importance.py -- L3 model-reliance: per-column permutation importance.

Loads the trained C v4 safe model (53-dim input), runs inference **per view**, and for
each of the 14 extra columns shuffles that column within each view, then measures the
drop in pooled AP on the 24 __inj test views.

L1 (single-feature AP) and L2 (distribution shift) do not tell us what the model relies
on; this does. A column with ~0 importance is not being used, even if its standalone AP
is high.
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
import yaml
from scipy.stats import rankdata
from sklearn.metrics import average_precision_score

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
WORK = ROOT / "generate_trans/folds/hosts_bt31"
CKPT = ROOT / "results/hosts_bt31_seed42mode4_allb1_fold_fghtl_CncleanV4safeD42/best_model_ALL.pt"
EXTRA = PT / "satrel_node_feats_sat_p0clean4_safe.npy"
NAMES = ["n_rel_log", "frac_decided", "frac_influence", "frac_proved",
         "reach_po_log", "reach_dff_log", "p1_ratio",
         "n_gate_log", "n_mux_log", "n_cone_log", "n_dff_log",
         "frac_proved_sat", "frac_partial_sat", "covered"]


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


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from models.gin_net import GINDual

    g = torch.load(PT / "trans_graph.pt", map_location="cpu", weights_only=False, mmap=True)
    xb = g.x.float()
    ei = g.edge_index.long()
    y = g.y.numpy().astype(int)
    tm = g.test_mask.numpy().astype(bool)
    fid = np.asarray(json.load(open(WORK / "data/for_train/metadata_trans.json",
                                    encoding="utf-8"))["file_ids"], dtype=object)
    n = xb.shape[0]

    # view groups (fid is NOT contiguous: keep-variants interleave)
    views = [v for v in np.unique(fid) if "__inj" in str(v)]
    groups = []
    for v in views:
        idx = np.flatnonzero(fid == v)
        remap = np.full(n, -1, dtype=np.int64)
        remap[idx] = np.arange(len(idx))
        keep = (remap[ei[0]] >= 0) & (remap[ei[1]] >= 0)
        groups.append((v, idx, torch.from_numpy(remap[ei[:, keep]])))
    print(f"[views] inj views={len(groups)} nodes={sum(len(x[1]) for x in groups)}")

    # normalise exactly as training (base: fit=all; extra: covered rows, clamp +-10)
    Eraw = np.asarray(np.load(EXTRA, mmap_mode="r")[:, :], dtype=np.float32)
    cov = Eraw[:, -1] > 0
    En = Eraw.copy()
    mu = Eraw[cov, :13].mean(0, keepdims=True)
    sd = Eraw[cov, :13].std(0, keepdims=True)
    sd[sd < 1e-6] = 1e-6
    En[:, :13] = np.clip((Eraw[:, :13] - mu) / sd, -10.0, 10.0)
    En[~cov, :13] = 0.0
    bmu = xb.mean(0, keepdim=True)
    bsd = xb.std(0, keepdim=True).clamp_min(1e-6)
    X = torch.cat([((xb - bmu) / bsd).clamp(-10.0, 10.0), torch.from_numpy(En)], dim=1)
    del Eraw, En, xb, bmu, bsd
    print(f"[x] {tuple(X.shape)}")

    cfg = yaml.safe_load((ROOT / "_devcfg/dual.yaml").read_text(encoding="utf-8"))
    ck = torch.load(CKPT, map_location="cpu", weights_only=False)
    model = GINDual(in_channels=int(X.shape[1]),
                    hidden_channels=int(cfg["model"]["hidden_channels"]),
                    out_channels=int(cfg["model"]["out_channels"]),
                    num_layers=int(cfg["model"]["branch_layers"]),
                    split=int(cfg["model"]["split"]), fusion="gate")
    model.load_state_dict(ck["state_dict"])
    model.eval()

    def scores(Xt: torch.Tensor) -> np.ndarray:
        out = []
        with torch.no_grad():
            for _v, idx, e in groups:
                out.append(model(Xt[torch.from_numpy(idx)], e)[:, 1].numpy())
        return np.concatenate(out)

    def pooled_ap(sc: np.ndarray):
        idx = np.concatenate([gg[1] for gg in groups])
        m = tm[idx]
        idx, sc = idx[m], sc[m]
        yy = y[idx]
        sp = pct(idx, sc, fid[idx])
        return float(average_precision_score(yy, sp)), idx, yy

    base_ap, idx, yy = pooled_ap(scores(X))
    print(f"[base] pooled AP={base_ap:.4f}  nodes={len(idx)} pos={int(yy.sum())}")

    rng = np.random.default_rng(20261025)
    rows = []
    n_base = X.shape[1] - 14
    for j in range(n_base, X.shape[1]):
        Xp = X.clone()
        for _v, gidx, _e in groups:
            t = torch.from_numpy(gidx)
            vals = X[t, j].numpy()
            Xp[t, j] = torch.from_numpy(vals[rng.permutation(len(gidx))])
        ap, _, _ = pooled_ap(scores(Xp))
        rows.append((NAMES[j - n_base], ap, base_ap - ap))
        print(f"  {NAMES[j - n_base]:18s} AP={ap:.4f}  dAP={base_ap - ap:+.4f}")

    print("\n| column | AP after shuffle | dAP |")
    print("|---|---:|---:|")
    for nm, ap, d in sorted(rows, key=lambda r: -r[2]):
        print(f"| `{nm}` | {ap:.4f} | {d:+.4f} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
