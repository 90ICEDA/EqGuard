# -*- coding: utf-8 -*-
"""make_neigh_feats.py —— 邻域聚合特征：给每个节点加上"1 跳邻域的原语构成"。

动机（由第四步结论 4）：原语等价类把"词汇表差异"消掉了，剩下的缺口来自**节点粒度**——
flatten/abc 会把一个复合单元（如 AOI）展开成一片原语节点，所以"木马门"在原语图上对应
**一片节点**而不是一个节点。单节点特征因此对不齐，必须看局部。

写回布局（维度仍 39；siamese_loss 依赖 x[:,29] 的下标不变）：
    dims 0..6    自身原语构成（归一化，同 make_prim_feats）
    dims 7..13   1 跳邻居的原语构成**均值**（= 局部原语直方图）★ 核心
    dims 14..20  自身 + 邻域合并池化 (P + ΣP_nei)/(1 + deg)（= 局部区域的组成）
    dims 21..24  log1p(邻居平均度) / log1p(邻居最大度) / log1p(自身度) / 相对度数
    dims 25..38  只保留保持率 ≥0.3 的那 5 维结构量，其余置零

用法：
    py phase2/ys/make_neigh_feats.py --src 10.13/group_fold_ys5 --out 10.13/group_fold_ys5_neigh
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import torch

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

from phase2.ys.feature_retention import feature_names  # noqa: E402
from phase2.ys.make_prim_feats import CELL2PRIM, PRIM, STRUCT_KEEP  # noqa: E402


def prim_of(X: np.ndarray, gate_names: list) -> np.ndarray:
    """(N,39) → (N,7) 自身原语构成（逐节点归一化）。"""
    G = X[:, :len(gate_names)]
    P = np.zeros((len(X), len(PRIM)), dtype=np.float64)
    for j, gn in enumerate(gate_names):
        idx = np.flatnonzero(G[:, j] > 0)
        if len(idx) == 0:
            continue
        for k, v in CELL2PRIM[gn].items():
            P[idx, PRIM.index(k)] += v
    s = P.sum(axis=1, keepdims=True)
    s[s == 0] = 1.0
    return P / s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--structural", default=",".join(STRUCT_KEEP))
    a = ap.parse_args()

    keep = [x.strip() for x in a.structural.split(",") if x.strip()]
    order, _ = feature_names(a.src)
    gate_names = [n[5:] for n in order[:25]]
    name2idx = {n: i for i, n in enumerate(order)}

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

        src, dst = ei[0], ei[1]
        ai = np.concatenate([src, dst])          # 无向化：邻居对
        aj = np.concatenate([dst, src])
        S = np.zeros((N, len(PRIM)))
        C = np.zeros(N)
        np.add.at(S, aj, P[ai])
        np.add.at(C, aj, 1.0)
        Cc = np.where(C == 0.0, 1.0, C)
        nb_mean = S / Cc[:, None]                # 邻居原语构成均值
        pooled = (P + S) / (1.0 + C)[:, None]    # 自身+邻域合并池化

        deg = C
        S2 = np.zeros(N)
        np.add.at(S2, aj, deg[ai])
        nb_deg_mean = S2 / Cc
        nb_deg_max = np.zeros(N)
        np.maximum.at(nb_deg_max, aj, deg[ai])

        newX = np.zeros_like(X)
        newX[:, 0:7] = P
        newX[:, 7:14] = nb_mean
        newX[:, 14:21] = pooled
        newX[:, 21] = np.log1p(nb_deg_mean)
        newX[:, 22] = np.log1p(nb_deg_max)
        newX[:, 23] = np.log1p(deg)
        newX[:, 24] = np.log1p(nb_deg_mean + 1) - np.log1p(deg + 1)
        for n in keep:
            if n in name2idx:
                newX[:, name2idx[n]] = X[:, name2idx[n]]
        g.x = torch.tensor(newX, dtype=g.x.dtype)
        torch.save(g, outp / fn)
        stats[fn] = {"rows": int(N), "edges": int(ei.shape[1]),
                     "mean_deg": round(float(deg.mean()), 2),
                     "nb_mean_share": {PRIM[k]: round(float(nb_mean[:, k].mean()), 4)
                                       for k in range(len(PRIM))}}

    for fn in ("views.json", "dataset_meta.json", "gatelookup_recommended.json"):
        for d in (srcp, a.src):
            p = d / fn
            if p.exists():
                shutil.copy2(p, outp / fn)
                shutil.copy2(p, a.out / fn)
                break

    info = {"cell2prim": CELL2PRIM, "prim_dims": PRIM, "kept_structural": keep,
            "layout": {"0-6": "自身原语构成", "7-13": "邻居原语构成均值",
                       "14-20": "自身+邻域合并池化", "21-24": "度数类",
                       "25-38": "保留结构量"},
            "stats": stats}
    (a.out / "neigh_feats.json").write_text(json.dumps(info, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    for fn, st in stats.items():
        print(f"[{fn}] 行 {st['rows']}｜边 {st['edges']}｜平均度 {st['mean_deg']}"
              f"｜邻居原语均值 {st['nb_mean_share']}")
    print(f"[导出] {outp} + neigh_feats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
