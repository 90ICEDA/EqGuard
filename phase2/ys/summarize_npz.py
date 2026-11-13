"""summarize_npz.py —— 把多个 `--dump-scores` 的 npz 汇总成 **每 seed 一行** 的指标表 ✓。

用途：3-seed 主表的均值 ± std ✓（B5 口径 ✓：分层报 pooled / 逐视图均值 ✓）。

用法：
  python -X utf8 phase2/ys/summarize_npz.py \
    --pt generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt \
    --npz _devcfg/gnn_v31_s42.npz _devcfg/gnn_v31_s1.npz _devcfg/gnn_v31_s2.npz \
    --out 10.15/03_特征与模型/3seed/summary_v31.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]


def recall_at(score: np.ndarray, y: np.ndarray, frac: float) -> float:
    npos = int(y.sum())
    if npos == 0:
        return float("nan")
    k = max(1, int(len(y) * frac))
    top = np.argsort(-score)[:k]
    return float(y[top].sum() / npos)


def score_one(npz: Path, y: np.ndarray, fids: list[str], test_mask: np.ndarray) -> dict:
    g = np.load(npz)
    idx = g["idx"].astype(np.int64)
    sc = np.full(len(y), -np.inf, np.float32)
    sc[idx] = g["score"].astype(np.float32)
    seen = np.zeros(len(y), bool)
    seen[idx] = True
    rows = []
    for v in pd.unique(np.asarray(fids)[seen & test_mask]):
        sel = (np.asarray(fids) == v) & seen
        yy, ss = y[sel], sc[sel]
        npos = int(yy.sum())
        row = {"view": v, "nodes": int(sel.sum()), "pos": npos}
        if 0 < npos < sel.sum():
            row["ap"] = average_precision_score(yy, ss)
            row["auc"] = roc_auc_score(yy, ss)
            row["r1"] = recall_at(ss, yy, 0.01)
            row["r5"] = recall_at(ss, yy, 0.05)
        rows.append(row)
    df = pd.DataFrame(rows)
    # pooled：把所有测试视图的节点拼起来（pooled AP 对"视图间分数可比"敏感 ✓）
    sel_all = seen & test_mask
    yy, ss = y[sel_all], sc[sel_all]
    return {
        "npz": npz.name,
        "views": len(df),
        "pos": int(df["pos"].sum()),
        "pooled_ap": average_precision_score(yy, ss) if 0 < yy.sum() < len(yy) else np.nan,
        "pooled_auc": roc_auc_score(yy, ss) if 0 < yy.sum() < len(yy) else np.nan,
        "view_ap": df["ap"].mean(),
        "view_auc": df["auc"].mean(),
        "r1": df["r1"].mean(),
        "r5": df["r5"].mean(),
        "views_with_pos": int((df["pos"] > 0).sum()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path, required=True)
    ap.add_argument("--npz", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    work = a.pt.parents[2]
    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    y = np.asarray(d.y, np.int8).astype(np.int64)
    fids = json.loads((work / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))["file_ids"]
    # 测试视图 = views.json 的 test_views 列表（v3/v3.1 的格式：{"fold","train_views","val_views","test_views"} ✓）
    meta = json.loads((work / "views.json").read_text(encoding="utf-8"))
    if isinstance(meta, dict) and "test_views" in meta:
        test_views = set(meta["test_views"])
    elif isinstance(meta, dict):
        test_views = {k for k, v in meta.items() if str(v).lower() == "test"}
    else:
        test_views = {r["view"] for r in meta if str(r.get("split", "")).lower() == "test"}
    test_mask = np.isin(np.asarray(fids), list(test_views)) if test_views else np.ones(len(fids), bool)

    out = [score_one(p, y, fids, test_mask) for p in a.npz]
    df = pd.DataFrame(out)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, encoding="utf-8-sig")
    keys = ["pooled_ap", "pooled_auc", "view_ap", "view_auc", "r1", "r5"]
    print(df.round(4).to_string(index=False))
    print("\n[均值 ± std]（n=%d）" % len(df))
    for k in keys:
        print(f"  {k:<11s} {df[k].mean():.4f} ± {df[k].std(ddof=0):.4f}")
    print(f"\n[导出] {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
