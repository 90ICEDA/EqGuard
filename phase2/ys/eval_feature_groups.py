"""eval_feature_groups.py —— C1/C5：特征分组的**增量贡献**（LR / GBDT，dev4）。

组：
  base39      现有 39 维 ✓
  +cone5      base39 + 锥级特征（cone_feats.npy ✓）
  +scoap2     base39 + SCOAP cc0/cc1（scoap_feats.npy 前两列 ✓）
  +all        base39 + cone5 + scoap2 ✓
指标：pooled AP / AUC / R@5% + per-view macro AP（测试视图 ✓）。
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=Path(__file__).resolve().parents[2] / "generate_trans/folds/_dev4/data/processed/trans_graph.pt")
    ap.add_argument("--out-dir", type=Path,
                    default=Path(__file__).resolve().parents[2] / "10.15/03_特征与模型/C1_简单融合/tables")
    a = ap.parse_args()

    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    y = np.asarray(d.y, np.int8)
    tr = np.asarray(d.train_mask, bool)
    te = np.asarray(d.test_mask, bool)
    fids = json.loads((a.pt.parents[2] / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))["file_ids"]

    cone = np.load(a.pt.parent / "cone_feats.npy") if (a.pt.parent / "cone_feats.npy").exists() else None
    sco = np.load(a.pt.parent / "scoap_feats.npy") if (a.pt.parent / "scoap_feats.npy").exists() else None
    groups = {"base39": X}
    if cone is not None:
        groups["+cone5"] = np.concatenate([X, cone], 1)
        if sco is not None:
            groups["+scoap2"] = np.concatenate([X, sco[:, :2]], 1)
            groups["+all"] = np.concatenate([X, cone, sco[:, :2]], 1)

    rng = np.random.default_rng(0)
    ti = np.where(tr)[0]
    yi = y[ti]
    neg = rng.choice(np.where(yi == 0)[0], min(200000, int((yi == 0).sum())), replace=False)
    sel = np.concatenate([np.where(yi == 1)[0], neg])
    te_idx = np.where(te)[0]
    yt = y[te_idx]
    views = collections.defaultdict(list)
    for i, v in enumerate(fids):
        views[v].append(i)
    te_set = set(te_idx.tolist())

    rows = []
    for gname, F in groups.items():
        for mname in ("LR", "GBDT"):
            if mname == "LR":
                sc = StandardScaler().fit(F[ti][sel])
                clf = LogisticRegression(max_iter=1000, class_weight="balanced")
                clf.fit(sc.transform(F[ti][sel]), yi[sel])
                p = clf.predict_proba(sc.transform(F[te_idx]))[:, 1]
            else:
                clf = HistGradientBoostingClassifier(max_iter=300, random_state=0)
                clf.fit(F[ti][sel], yi[sel])
                p = clf.predict_proba(F[te_idx])[:, 1]
            ap = average_precision_score(yt, p)
            auc = roc_auc_score(yt, p)
            k5 = int(len(te_idx) * 0.05)
            r5 = float(yt[np.argsort(-p)[:k5]].sum() / max(1, yt.sum()))
            aps = []
            for v, ii in views.items():
                ii = [i for i in ii if i in te_set]
                if len(ii) < 10:
                    continue
                ii = np.array(ii)
                yy = y[ii]
                if not (0 < yy.sum() < len(yy)):
                    continue
                pos = np.searchsorted(te_idx, ii)
                aps.append(average_precision_score(yy, p[pos]))
            rows.append({"group": gname, "model": mname, "dims": F.shape[1],
                         "pooled_AP": round(float(ap), 4), "AUC": round(float(auc), 4),
                         "R@5%": round(r5, 4),
                         "per_view_mean": round(float(np.mean(aps)), 4) if aps else float("nan"),
                         "per_view_median": round(float(np.median(aps)), 4) if aps else float("nan")})
    r = pd.DataFrame(rows)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    r.to_csv(a.out_dir / "feature_groups.csv", index=False, encoding="utf-8-sig")
    print(r.to_string(index=False))
    return 0
