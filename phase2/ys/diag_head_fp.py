"""diag_head_fp.py —— N3：给任意 npz 输出**解释性指标**（head_fp / tail_pos / R@k ✓）。

用途 ✓：T12 只报了 AP/AUC，缺"为什么"；本脚本补上：
  head_fp  = 分数高于"最好正样本"的负节点数 ✓（头部假阳性 ✗）
  tail_pos = 名次低于"负样本中位数"的正节点数 ✓（尾部漏检 ✗）
另输出每视图 AP/AUC/R@1%/R@5% ✓，便于与 T12 对齐 ✓。

用法：
  py -X utf8 phase2/ys/diag_head_fp.py \
     --npz _devcfg/gnn_v31_s42.npz _devcfg/gnn_v31r_l100_s42.npz ... \
     --out 10.15/03_特征与模型/C6_区域级监督/tables/head_fp.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from summarize_npz import score_one  # noqa: E402

ROOT = HERE.parents[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt")
    ap.add_argument("--npz", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "10.15/03_特征与模型/C6_区域级监督/tables/head_fp.csv")
    a = ap.parse_args()
    work = a.pt.parents[2]
    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    y = np.asarray(d.y, np.int8).astype(np.int64)
    fids = np.asarray(json.loads((work / "data/for_train/metadata_trans.json")
                                 .read_text(encoding="utf-8"))["file_ids"])
    meta = json.loads((work / "views.json").read_text(encoding="utf-8"))
    test_views = set(meta["test_views"])

    rows = []
    for f in a.npz:
        g = np.load(f)
        idx = g["idx"].astype(np.int64)
        s = np.full(len(y), -1.0, np.float32)
        s[idx] = g["score"].astype(np.float32)
        seen = np.zeros(len(y), bool)
        seen[idx] = True
        rec = score_one(f, y, fids, np.isin(fids, list(test_views)))
        hf, tp, aps, aucs = [], [], [], []
        for v in sorted(test_views):
            m = (fids == v) & seen
            yy, ss = y[m], s[m]
            pos = int(yy.sum())
            if pos == 0 or pos == len(yy):
                continue
            order = np.argsort(-ss)
            ranks = np.empty(len(ss), np.int64)
            ranks[order] = np.arange(1, len(ss) + 1)
            rpos = ranks[yy == 1]
            hf.append(int((ss[yy == 0] > ss[yy == 1].max()).sum()))
            tp.append(int((rpos > np.median(ranks[yy == 0])).sum()))
            aps.append(average_precision_score(yy, ss))
            aucs.append(roc_auc_score(yy, ss))
        rows.append(dict(npz=f.name, views=len(hf),
                         view_ap=rec["view_ap"], view_auc=rec["view_auc"],
                         r1=rec["r1"], r5=rec["r5"],
                         head_fp=float(np.mean(hf)) if hf else np.nan,
                         tail_pos=float(np.mean(tp)) if tp else np.nan,
                         ap_recheck=float(np.mean(aps)) if aps else np.nan,
                         auc_recheck=float(np.mean(aucs)) if aucs else np.nan))
        print(f"[{f.name}] AP={rec['view_ap']:.4f} head_fp={rows[-1]['head_fp']:.1f} "
              f"tail_pos={rows[-1]['tail_pos']:.2f}", flush=True)

    df = pd.DataFrame(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out_kind = "csv"
    a.out = a.out if a.out.suffix == ".csv" else a.out.with_suffix(".csv")
    df.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"\n[out] {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
