"""region_clf.py —— B2 第二层：**区域级分类器（MIL）**。

区域 max 池化太弱 ✗（区域只有 ~9 个门 ✓，木马跨多个锥 ✗）→ 给每个区域构造特征，
用**区域标签**（区域内是否含正节点 ✓）训练分类器 ✓ —— 这才是 MIL 的正确用法 ✓。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "phase2" / "ys"))
from region_eval import build_regions, dff_mask  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/_dev3/data/processed/trans_graph.pt")
    ap.add_argument("--gnn", type=Path, default=ROOT / "_devcfg/gnn_dev3.npz")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.15/03_特征与模型/区域评估")
    a = ap.parse_args()
    work = a.pt.parents[2]

    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    y = np.asarray(d.y, np.int8)
    tr = np.asarray(d.train_mask, bool)
    te = np.asarray(d.test_mask, bool)
    fids = json.loads((work / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))["file_ids"]
    view_ids = np.zeros(len(y), np.int64)
    vm = {}
    for i, v in enumerate(fids):
        vm.setdefault(v, []).append(i)
    for k, v in enumerate(sorted(vm)):
        view_ids[np.array(vm[v])] = k

    is_dff = dff_mask(X, work)
    reg = build_regions(d.edge_index, is_dff, view_ids)
    uniq, inv = np.unique(reg, return_inverse=True)
    R = len(uniq)
    reg_view = np.zeros(R, np.int64)
    reg_view[inv] = view_ids

    p_gnn = np.zeros(len(y), np.float32)
    if a.gnn.exists():
        g = np.load(a.gnn)
        p_gnn[g["idx"].astype(np.int64)] = g["score"].astype(np.float32)

    raw = json.loads((work / "gatelookup_recommended.json").read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "gatelookup" in raw:
        raw = raw["gatelookup"]
    names = [k for k, _ in sorted(raw.items(), key=lambda kv: int(kv[1]))]
    ng = X.shape[1] - 14
    gid = np.where(X[:, :ng].sum(1) > 0, X[:, :ng].argmax(1), -1)
    size = np.bincount(inv, minlength=R).astype(np.float32)

    def frac(mask):
        c = np.bincount(inv[mask], minlength=R).astype(np.float32)
        return c / np.maximum(1, size)

    def idx_of(sub):
        return [i for i, n in enumerate(names[:ng]) if sub in n]

    feats = {
        "size": size, "log_size": np.log1p(size),
        "xor_frac": frac(np.isin(gid, idx_of("XOR"))),
        "and_frac": frac(np.isin(gid, idx_of("AND"))),
        "inv_frac": frac(np.isin(gid, idx_of("INV"))),
        "dff_frac": frac(is_dff),
        "fanin_mean": np.bincount(inv, weights=X[:, 25], minlength=R) / np.maximum(1, size),
        "dist_po_mean": np.bincount(inv, weights=X[:, 30], minlength=R) / np.maximum(1, size),
        "dist_pi_mean": np.bincount(inv, weights=X[:, 29], minlength=R) / np.maximum(1, size),
        "hop2in_mean": np.bincount(inv, weights=X[:, 35], minlength=R) / np.maximum(1, size),
        "gnn_mean": np.bincount(inv, weights=p_gnn, minlength=R) / np.maximum(1, size),
    }
    gmax = np.zeros(R, np.float32)
    np.maximum.at(gmax, inv, p_gnn)
    feats["gnn_max"] = gmax
    lab = np.zeros(R, np.int8)
    np.maximum.at(lab, inv, y)

    F = pd.DataFrame(feats)
    tr_r = np.where(np.isin(np.arange(R), np.unique(inv[tr])) & (size >= 2))[0]
    te_r = np.where(np.isin(np.arange(R), np.unique(inv[te])) & (size >= 2))[0]
    print(f"[区域] 训练区 {len(tr_r)}（正 {int(lab[tr_r].sum())}）｜测试区 {len(te_r)}（正 {int(lab[te_r].sum())}）")

    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import average_precision_score
    from sklearn.preprocessing import StandardScaler
    out = []
    for name, clf in (("reg-LR", LogisticRegression(max_iter=2000, class_weight="balanced")),
                      ("reg-GBDT", HistGradientBoostingClassifier(max_iter=300, random_state=0))):
        sc = StandardScaler().fit(F.iloc[tr_r].values)
        Atr = sc.transform(F.iloc[tr_r].values) if name == "reg-LR" else F.iloc[tr_r].values
        Ate = sc.transform(F.iloc[te_r].values) if name == "reg-LR" else F.iloc[te_r].values
        clf.fit(Atr, lab[tr_r])
        p = clf.predict_proba(Ate)[:, 1]
        aps = []
        for k in range(len(vm)):
            m = (reg_view[te_r] == k)
            if m.sum() < 5 or not (0 < lab[te_r][m].sum() < m.sum()):
                continue
            aps.append(average_precision_score(lab[te_r][m], p[m]))
        out.append({"model": name, "regions": len(te_r), "pos": int(lab[te_r].sum()),
                    "pooled_AP": round(float(average_precision_score(lab[te_r], p)), 4),
                    "per_view_mean": round(float(np.mean(aps)), 4),
                    "per_view_median": round(float(np.median(aps)), 4),
                    "per_view_p90": round(float(np.percentile(aps, 90)), 4),
                    "per_view_max": round(float(np.max(aps)), 4)})
    r = pd.DataFrame(out)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    r.to_csv(a.out_dir / "region_clf.csv", index=False, encoding="utf-8-sig")
    print(r.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
