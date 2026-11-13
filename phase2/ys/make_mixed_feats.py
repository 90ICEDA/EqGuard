# -*- coding: utf-8 -*-
"""make_mixed_feats.py —— 合并「自身原语构成」（对 flatten 有效）与「邻域区域比例」（对 abc 有效）。

依据（第四步与后续两组实验）：
    * prim（自身原语构成 + 5 个结构量）：ys_rt 0.0068（三 seed），但 ys_abc 0.0436 ✗
    * locratio（自身 + 1/2/3 跳区域比例 + 诊断）：ys_abc 0.0316 ✓ 但 ys_rt 0.0744 ✗、
      且见过的变换上 AP 掉得多（decomp3 0.93 → 0.65 ✗）
    → 两者互补；本脚本取"渐进局部性"的中间方案：**保留自身构成，加入 1 跳与 2 跳区域比例，
      但去掉 3 跳**（3 跳游走和把局部信号摊平，是 locratio 在 ys_rt 上退化的最可能原因）。

布局（39 维，siamese_loss 依赖 x[:,29] 下标不变）：
    0..6    自身原语构成（归一化）
    7..13   1 跳区域构成比例
    14..20  自身+1 跳合并池化比例  (P + A@P) 逐行归一化
    21..27  2 跳区域构成比例
    28..32  保留的 5 个结构量
    33..38  构成熵×3 / 1 跳 DFF 比例−全局 / 1 跳 XOR+MUX 比例 / 相对规模

用法：
    py phase2/ys/make_mixed_feats.py --src 10.13/group_fold_ys5 --out 10.13/group_fold_ys5_mixed
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import torch

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

from phase2.ys.feature_retention import feature_names  # noqa: E402
from phase2.ys.make_neigh_feats import prim_of  # noqa: E402
from phase2.ys.make_prim_feats import PRIM, STRUCT_KEEP  # noqa: E402


def row_ratio(M: np.ndarray) -> np.ndarray:
    tot = M.sum(axis=1, keepdims=True)
    return M / np.maximum(tot, 1e-9)


def ent(P: np.ndarray) -> np.ndarray:
    p = np.clip(P, 0.0, None)
    nz = p > 0
    h = -np.where(nz, p * np.log(np.maximum(p, 1e-12)), 0.0).sum(axis=1)
    return h / np.log(len(PRIM))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    order, _ = feature_names(a.src)
    gate_names = [n[5:] for n in order[:25]]
    name2idx = {n: i for i, n in enumerate(order)}
    ix, im, idf = PRIM.index("XOR"), PRIM.index("MUX"), PRIM.index("DFF")

    srcp, outp = a.src / "processed", a.out / "processed"
    if not (srcp / "trans_graph.pt").exists():
        print(f"[ERROR] 找不到 {srcp}/trans_graph.pt")
        return 1
    outp.mkdir(parents=True, exist_ok=True)

    stats = {}
    for fn in ("orig_graph.pt", "trans_graph.pt"):
        g = torch.load(srcp / fn, weights_only=False)
        X = g.x.numpy().astype(np.float64)
        ei = g.edge_index.numpy()
        N = len(X)
        P = prim_of(X, gate_names)
        A = sp.csr_matrix((np.ones(ei.shape[1]), (ei[0], ei[1])), shape=(N, N))
        A = (A + A.T).tocsr()
        A.data[:] = 1.0
        S1 = np.asarray(A @ P, dtype=np.float64)
        S2 = np.asarray(A @ S1, dtype=np.float64)
        deg1 = np.asarray(A.sum(axis=1)).ravel()
        gdff = float(P[:, idf].mean())

        newX = np.zeros_like(X)
        newX[:, 0:7] = P
        newX[:, 7:14] = row_ratio(S1)
        newX[:, 14:21] = row_ratio(P + S1)
        newX[:, 21:28] = row_ratio(S2)
        for n in STRUCT_KEEP:
            if n in name2idx:
                newX[:, name2idx[n]] = X[:, name2idx[n]]
        newX[:, 33] = ent(P)
        newX[:, 34] = ent(row_ratio(S1))
        newX[:, 35] = ent(row_ratio(S2))
        newX[:, 36] = row_ratio(S1)[:, idf] - gdff
        newX[:, 37] = row_ratio(S1)[:, ix] + row_ratio(S1)[:, im]
        newX[:, 38] = np.log1p(deg1) / np.log1p(N)
        g.x = torch.tensor(newX, dtype=g.x.dtype)
        torch.save(g, outp / fn)
        stats[fn] = {"rows": int(N), "edges": int(ei.shape[1]),
                     "global_dff_share": round(gdff, 4),
                     "R1": {PRIM[k]: round(float(row_ratio(S1)[:, k].mean()), 4)
                            for k in range(len(PRIM))}}

    for fn in ("views.json", "dataset_meta.json", "gatelookup_recommended.json"):
        for d in (srcp, a.src):
            p = d / fn
            if p.exists():
                shutil.copy2(p, outp / fn)
                shutil.copy2(p, a.out / fn)
                break

    info = {"prim_dims": PRIM, "kept_structural": STRUCT_KEEP,
            "layout": {"0-6": "自身构成", "7-13": "1跳区域比例", "14-20": "自身+1跳池化",
                       "21-27": "2跳区域比例", "28-32": "保留结构量", "33-38": "熵/DFF差/XOR+MUX/相对规模"},
            "rationale": "prim 保自身（对 flatten 有效）+ locratio 的区域比例（对 abc 有效）；去掉 3 跳（摊平局部信号）",
            "stats": stats}
    (a.out / "mixed_feats.json").write_text(json.dumps(info, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    for fn, st in stats.items():
        print(f"[{fn}] 行 {st['rows']}｜边 {st['edges']}｜全局 DFF {st['global_dff_share']}"
              f"｜1跳区域 {st['R1']}")
    print(f"[导出] {outp} + mixed_feats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
