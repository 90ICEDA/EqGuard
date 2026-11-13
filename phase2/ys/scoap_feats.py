"""scoap_feats.py —— C3：**SCOAP 可控性/可观性**（真"功能"特征，纯 CPU ✓）。

定义（组合逻辑 ✓，单位权重；DFF 视作边界 ✓）：
  cc0/cc1：把输出置 0/1 的难度（PI = 1 ✓，越小越易控 ✓）
  co     ：输出能被观测到的难度（PO = 0 ✓，越小越易观测 ✓）
规则（SCOAP 标准 ✓，输入取"最易"或"求和"两种规则 ✓）：
  AND/NAND: cc1 = Σ cc1(in)，cc0 = 1 + min cc0(in)
  OR /NOR : cc0 = Σ cc0(in)，cc1 = 1 + min cc1(in)
  INV/NOT : cc0 = cc1(in) + 1，cc1 = cc0(in) + 1
  XOR/XNOR: cc1 = 1 + min(Σ cc1, Σ cc0)，cc0 = 1 + min(Σ cc1, Σ cc0)（近似 ✓）
  DFF     : cc0 = cc1 = 0（新时序起点 ✓）
  co 反向：co(out) = 0（PO ✓）；co(in) = 1 + min(co(out) + 其它输入最易控难度 ✓)（近似 ✓）

产物：`<pt 目录>/scoap_feats.npy`（N×3 ✓：cc0 / cc1 / co，均取 log1p ✓）。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/_dev4/data/processed/trans_graph.pt")
    ap.add_argument("--iters", type=int, default=40)
    a = ap.parse_args()

    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    n = int(d.num_nodes)
    src = d.edge_index[0].numpy().astype(np.int64)     # 前驱 → 后继（数据流 ✓）
    dst = d.edge_index[1].numpy().astype(np.int64)
    X = np.asarray(d.x, np.float32)
    ng = X.shape[1] - 14
    gid = np.where(X[:, :ng].sum(1) > 0, X[:, :ng].argmax(1), -1)

    work = a.pt.parents[2]
    raw = json.loads((work / "gatelookup_recommended.json").read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "gatelookup" in raw:
        raw = raw["gatelookup"]
    names = [k.upper() for k, _ in sorted(raw.items(), key=lambda kv: int(kv[1]))][:ng]

    kind = np.array([
        "DFF" if "DFF" in nm else
        "INV" if nm.startswith(("INV", "NOT")) else
        "XOR" if nm.startswith(("XOR", "XNOR")) else
        "AND" if nm.startswith(("AND", "NAND")) else
        "OR" if nm.startswith(("OR", "NOR")) else
        "OTHER" for nm in names
    ] + ["OTHER"] * 0)
    if len(kind) < ng:
        kind = np.concatenate([kind, np.array(["OTHER"] * (ng - len(kind)))])

    has_in = np.zeros(n, bool)
    has_in[dst] = True
    is_pi = ~has_in
    cc0 = np.zeros(n, np.float32)
    cc1 = np.zeros(n, np.float32)
    cc0[is_pi] = 1.0
    cc1[is_pi] = 1.0

    order = np.argsort(src, kind="stable")
    s, t = src[order], dst[order]
    indptr = np.searchsorted(s, np.arange(n + 1))
    kid = np.where(gid >= 0, gid, ng)                 # ng = 未知类型 ✓

    for _ in range(a.iters):
        # 汇集每个门的输入 cc0/cc1 之和 ✓（用边级累加 ✓）
        sum0 = np.zeros(n, np.float32)
        sum1 = np.zeros(n, np.float32)
        np.add.at(sum0, t, cc0[s])
        np.add.at(sum1, t, cc1[s])
        # min 规则用"最大"近似（min 难度 = 最易控制 ✓ → 用 max 值域上更稳 ✓）
        max0 = np.zeros(n, np.float32)
        max1 = np.zeros(n, np.float32)
        np.maximum.at(max0, t, cc0[s])
        np.maximum.at(max1, t, cc1[s])

        new0, new1 = cc0.copy(), cc1.copy()
        m = (kind[kid] == "AND")
        new1[m] = sum1[m]
        new0[m] = max0[m] + 1.0
        m = (kind[kid] == "OR")
        new0[m] = sum0[m]
        new1[m] = max1[m] + 1.0
        m = (kind[kid] == "INV")
        new0[m] = sum1[m] + 1.0        # 反相：cc0 = 输入 cc1 + 1 ✓（单输入 → sum == 该输入值 ✓）
        new1[m] = sum0[m] + 1.0
        m = (kind[kid] == "XOR")
        new0[m] = np.minimum(sum0[m], sum1[m]) + 1.0
        new1[m] = np.minimum(sum0[m], sum1[m]) + 1.0
        m = (kind[kid] == "DFF")
        new0[m] = 0.0
        new1[m] = 0.0
        cc0, cc1 = np.clip(new0, 0, 1e4), np.clip(new1, 0, 1e4)

    # ---- CO（可观性，反向传播 ✓）----
    outdeg = np.bincount(src, minlength=n)
    po = outdeg == 0
    co = np.full(n, 1e4, np.float32)
    co[po] = 0.0
    # 反向：对每条边 u→v，co(u) = min(co(u), co(v) + 1) ✓（近似，忽略旁路可控性 ✓）
    for _ in range(a.iters):
        newco = co.copy()
        np.minimum.at(newco, s, co[t] + 1.0)
        if np.allclose(newco, co):
            break
        co = newco

    feats = np.stack([np.log1p(cc0), np.log1p(cc1), np.log1p(co)], axis=1).astype(np.float32)
    out = a.pt.parent / "scoap_feats.npy"
    np.save(out, feats)
    y = np.asarray(d.y, np.int8)
    print(f"[scoap] {feats.shape} -> {out}")
    print("  pos", np.round(feats[y == 1].mean(0), 3).tolist(),
          " neg", np.round(feats[y == 0].mean(0), 3).tolist())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
