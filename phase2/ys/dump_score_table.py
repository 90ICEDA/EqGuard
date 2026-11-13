"""dump_score_table.py —— 导出**单个测试视图**的逐节点置信分数表（解释 AP 为什么低）。

列：rank / node_idx / gate_type / score / y / dist_to_PI / dist_to_PO /
    2hop_fanin_stage / xor_frac_3hop / cone_size_3hop

用法：
  python -X utf8 phase2/ys/dump_score_table.py --view s15850t100__injzeta_d1_s42__ys_opt
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/_dev4/data/processed/trans_graph.pt")
    ap.add_argument("--gnn", type=Path, default=ROOT / "_devcfg/gnn_dev4_dual.npz")
    ap.add_argument("--view", default="s15850t100__injzeta_d1_s42__ys_opt")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "10.15/03_特征与模型/特征诊断/dev4_score_tables")
    a = ap.parse_args()
    work = a.pt.parents[2]

    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    y = np.asarray(d.y, np.int8)
    fids = json.loads((work / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))["file_ids"]
    cone = np.load(a.pt.parent / "cone_feats.npy") if (a.pt.parent / "cone_feats.npy").exists() else None

    g = np.load(a.gnn)
    score = np.zeros(len(y), np.float32)
    score[g["idx"].astype(np.int64)] = g["score"].astype(np.float32)

    raw = json.loads((work / "gatelookup_recommended.json").read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "gatelookup" in raw:
        raw = raw["gatelookup"]
    names = [k for k, _ in sorted(raw.items(), key=lambda kv: int(kv[1]))]
    ng = X.shape[1] - 14
    gid = np.where(X[:, :ng].sum(1) > 0, X[:, :ng].argmax(1), -1)
    gname = [names[i] if 0 <= i < len(names) else "" for i in gid]

    idx = np.array([i for i, v in enumerate(fids) if v == a.view])
    if idx.size == 0:
        raise SystemExit(f"[ERROR] 视图不存在: {a.view}")
    order = idx[np.argsort(-score[idx])]
    df = pd.DataFrame({
        "rank": np.arange(1, len(order) + 1),
        "node_idx": order,
        "gate_type": [gname[i] for i in order],
        "score": np.round(score[order], 6),
        "y": y[order],
        "dist_to_PI": X[order, 29], "dist_to_PO": X[order, 30],
        "hop2_in_stage": X[order, 35], "hop2_out_stage": X[order, 36],
    })
    if cone is not None:
        df["xor_frac_3hop"] = np.round(cone[order, 0], 4)
        df["cone_size_3hop"] = np.round(cone[order, 3], 4)
    a.out.mkdir(parents=True, exist_ok=True)
    out = a.out / f"score_{a.view}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")

    npos = int(y[idx].sum())
    apv = average_precision_score(y[idx], score[idx]) if 0 < npos < len(idx) else float("nan")
    pos_rank = df.loc[df.y == 1, "rank"].tolist()
    print(f"[视图] {a.view}  节点 {len(idx)}  正节点 {npos}  **AP {apv:.4f}**")
    print(f"[正节点名次] {pos_rank}")
    print(f"[正节点名次统计] 最好 {min(pos_rank) if pos_rank else '-'} / 中位 "
          f"{int(np.median(pos_rank)) if pos_rank else '-'} / 最差 {max(pos_rank) if pos_rank else '-'}"
          f"（视图共 {len(idx)} 个节点）")
    k = max(1, int(len(idx) * 0.05))
    print(f"[top-5% = 前 {k} 名] 命中 {int(df.head(k).y.sum())} 个正节点")
    print("\n[前 15 名]")
    print(df.head(15).to_string(index=False))
    print("\n[正节点所在行]")
    print(df[df.y == 1].head(15).to_string(index=False))
    print(f"\n[导出] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
