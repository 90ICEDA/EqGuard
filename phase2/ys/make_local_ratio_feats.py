# -*- coding: utf-8 -*-
"""make_local_ratio_feats.py —— 局部原语比例（多尺度）：针对 abc 的剩余缺口。

为什么上一版邻域特征不够：
    `make_neigh_feats.py` 里混进了**绝对度数**类维度（自身度、邻居平均/最大度），
    而 abc 会**重映射并优化逻辑** → 节点数与原语计数本身就变了 ✗，绝对量必然漂 ✗。
这一版全部改成**比例**（区域内构成归一化）：
    * 区域构成 = (区域内各原语的计数) / (区域内原语总数) —— 与区域大小无关 ✓
    * 尺度取 1 / 2 / 3 跳，尺度越大越接近整块电路的构成（abc 保持宏观混合比例 ✓）

区域用**游走和**近似（`A^k @ P` 再按行归一化）：精确 k 跳并集需要布尔矩阵幂，
在 110 万节点 × 400 万边上不可行 ✗；游走和是标准的邻居聚合代理 ✓ 已在 json 里注明 ✓

写回布局（维度仍 39；siamese_loss 依赖 x[:,29] 下标不变）：
    0..6    自身原语构成（归一化）
    7..13   1 跳区域原语比例
    14..20  2 跳区域原语比例
    21..27  3 跳区域原语比例
    28..32  原来保留的 5 个结构量（log1p_degree / touches_PI / dist_to_PO / 两跳扇入扇出）
    33..38  自身构成熵 / 1 跳区域熵 / 2 跳区域熵 /
            1 跳 DFF 比例−全局 DFF 比例 / 1 跳 (XOR+MUX) 比例 / log1p(1 跳规模)/log1p(N)

用法：
    py phase2/ys/make_local_ratio_feats.py --src 10.13/group_fold_ys5 --out 10.13/group_fold_ys5_locratio
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


def region_ratio(A: sp.csr_matrix, P: np.ndarray) -> np.ndarray:
    S = np.asarray(A @ P, dtype=np.float64)
    tot = S.sum(axis=1, keepdims=True)
    return S / np.maximum(tot, 1e-9)


def ent(P: np.ndarray) -> np.ndarray:
    """归一化熵（0..1），对构成比例分布。"""
    p = np.clip(P, 0.0, None)
    nz = p > 0
    h = -np.where(nz, p * np.log(np.maximum(p, 1e-12)), 0.0).sum(axis=1)
    return h / np.log(len(PRIM))


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
    io = [PRIM.index("XOR"), PRIM.index("MUX")]
    idf = PRIM.index("DFF")

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
        A = sp.csr_matrix((np.ones(len(src), dtype=np.float64), (src, dst)), shape=(N, N))
        A = (A + A.T).tocsr()          # 无向（重复项会相加）
        A.data[:] = 1.0                # 只要"有没有边"，不要重数
        SP1 = np.asarray(A @ P, dtype=np.float64)
        SP2 = np.asarray(A @ SP1, dtype=np.float64)
        SP3 = np.asarray(A @ SP2, dtype=np.float64)
        R1 = region_ratio(A, P)        # = SP1 归一化
        R2 = region_ratio(A, SP1)
        R3 = region_ratio(A, SP2)
        deg1 = np.asarray(A.sum(axis=1)).ravel()

        gdff = float(P[:, idf].mean())
        newX = np.zeros_like(X)
        newX[:, 0:7] = P
        newX[:, 7:14] = R1
        newX[:, 14:21] = R2
        newX[:, 21:28] = R3
        for n in keep:
            if n in name2idx:
                newX[:, name2idx[n]] = X[:, name2idx[n]]
        newX[:, 33] = ent(P)
        newX[:, 34] = ent(R1)
        newX[:, 35] = ent(R2)
        newX[:, 36] = R1[:, idf] - gdff
        newX[:, 37] = R1[:, io[0]] + R1[:, io[1]]
        newX[:, 38] = np.log1p(deg1) / np.log1p(N)

        g.x = torch.tensor(newX, dtype=g.x.dtype)
        torch.save(g, outp / fn)
        stats[fn] = {"rows": int(N), "edges": int(ei.shape[1]),
                     "global_dff_share": round(gdff, 4),
                     "mean_deg1": round(float(deg1.mean()), 2),
                     "R1_share": {PRIM[k]: round(float(R1[:, k].mean()), 4)
                                  for k in range(len(PRIM))}}

    for fn in ("views.json", "dataset_meta.json", "gatelookup_recommended.json"):
        for d in (srcp, a.src):
            p = d / fn
            if p.exists():
                shutil.copy2(p, outp / fn)
                shutil.copy2(p, a.out / fn)
                break

    info = {"prim_dims": PRIM, "kept_structural": keep,
            "layout": {"0-6": "自身构成", "7-13": "1跳区域比例", "14-20": "2跳区域比例",
                       "21-27": "3跳区域比例", "28-32": "保留结构量",
                       "33-38": "构成熵×3 / DFF比例差 / XOR+MUX比例 / 相对规模"},
            "region_proxy": "游走和 A^k@P 后按行归一化（精确 k 跳并集不可行，已在文档注明）",
            "stats": stats}
    (a.out / "locratio_feats.json").write_text(json.dumps(info, ensure_ascii=False, indent=2),
                                               encoding="utf-8")
    for fn, st in stats.items():
        print(f"[{fn}] 行 {st['rows']}｜边 {st['edges']}｜全局 DFF 比例 {st['global_dff_share']}"
              f"｜1 跳区域比例 {st['R1_share']}")
    print(f"[导出] {outp} + locratio_feats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
