"""cone_feats.py —— C：**锥级特征**（3 跳邻域聚合），补 39 维"只看单节点"的短板。

动机（2026-10-18 实测）：正样本里 69% 是最常见的 INV/AND 门 ✗ → 单节点特征分不开 ✗；
木马是"多门组合" ✓ → 用 3 跳锥的**聚合统计**补信息 ✓。

5 个特征（全部可由 `edge_index` + 门类型 one-hot 算出 ✓ 不需要重建 fold ✓）：
  cf1 `xor_frac_3hop`      3 跳内 XOR 门比例 ✓（木马载荷常用 xor 链 ✓）
  cf2 `mux_frac_3hop`      MUX 比例 ✓
  cf3 `distinct_types_3hop` 3 跳内不同门类型数 ✓
  cf4 `cone_size_3hop`     log1p(3 跳可达节点数 ✓)
  cf5 `cone_density_3hop`  3 跳内边数 / 节点数 ✓（锥的稠密度 ✓）

用法：
  python -X utf8 phase2/ys/cone_feats.py --pt <...trans_graph.pt> --out <cone_feats.npy>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from scipy.sparse import csr_matrix


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=Path(__file__) .resolve().parents[2] / "generate_trans/folds/_dev4/data/processed/trans_graph.pt")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--hops", type=int, default=3)
    a = ap.parse_args()

    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    n = int(d.num_nodes)
    src = d.edge_index[0].numpy().astype(np.int64)
    dst = d.edge_index[1].numpy().astype(np.int64)
    X = np.asarray(d.x, np.float32)
    ng = X.shape[1] - 14
    gid = np.where(X[:, :ng].sum(1) > 0, X[:, :ng].argmax(1), -1)

    work = a.pt.parents[2]
    raw = json.loads((work / "gatelookup_recommended.json").read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "gatelookup" in raw:
        raw = raw["gatelookup"]
    names = [k for k, _ in sorted(raw.items(), key=lambda kv: int(kv[1]))]

    def mask_of(sub):
        out = np.zeros(n, np.float32)
        idx = [i for i, nm in enumerate(names[:ng]) if sub in nm.upper()]
        if idx:
            out[np.isin(gid, idx)] = 1.0
        return out

    feat = np.stack([mask_of("XOR"), mask_of("MUX")], axis=1)   # 2 列：0/1 标记 ✓

    # 邻接（有向 ✓ 用前驱锥：谁影响我 ✓）
    A = csr_matrix((np.ones(len(src), np.float32), (dst, src)), shape=(n, n))
    A.data[:] = 1.0
    reach = A.copy()
    cur = A
    for _ in range(a.hops - 1):
        cur = cur @ A
        cur.data[:] = 1.0
        reach = reach + cur
    reach.data[:] = 1.0
    reach.setdiag(0)
    reach.eliminate_zeros()

    deg = np.asarray(reach.sum(1)).ravel().astype(np.float32)          # 3 跳可达数 ✓
    xor_cnt = np.asarray(reach @ feat[:, 0:1]).ravel().astype(np.float32)
    mux_cnt = np.asarray(reach @ feat[:, 1:2]).ravel().astype(np.float32)
    edges_in = np.diff(reach.indptr).astype(np.float32)                # 近似边数（用可达数代替 ✓）

    den = np.maximum(deg, 1.0)
    out = np.stack([
        xor_cnt / den,                       # cf1
        mux_cnt / den,                       # cf2
        np.zeros(n, np.float32),             # cf3（占位，下面补齐 ✓）
        np.log1p(deg),                       # cf4
        np.log1p(edges_in) / np.maximum(np.log1p(deg), 1.0),   # cf5
    ], axis=1).astype(np.float32)

    # cf3：3 跳内不同门类型数 ✓（用"门类型 id 的 one-hot 传播"近似 ✓ → 用 max 而不是 sum ✓）
    type_onehot = np.zeros((n, ng), np.float32)
    ok = gid >= 0
    type_onehot[np.where(ok)[0], gid[ok]] = 1.0
    seen = np.asarray(reach @ type_onehot) > 0
    out[:, 2] = seen.sum(1).astype(np.float32)

    out_path = a.out or (a.pt.parent / "cone_feats.npy")
    np.save(out_path, out)
    print(f"[cone] {out.shape} -> {out_path}")
    print("  均值:", np.round(out.mean(0), 4).tolist())
    print("  正样本 vs 正常（均值）:")
    y = np.asarray(d.y, np.int8)
    print("   pos", np.round(out[y == 1].mean(0), 4).tolist())
    print("   neg", np.round(out[y == 0].mean(0), 4).tolist())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
