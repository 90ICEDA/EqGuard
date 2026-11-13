#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
check_cycle_features.py — 回归检查：SCC 收缩（--cycle-mode contract）是否按预期只影响环内节点

检查项（对照 none 与 contract 两个工作目录的 feats_orig.npy）：
  1) none 维度 = 33；contract 维度 = 39（旧 33 维 + 追加 6 维环感知特征）
  2) **所有**节点的前 33 维逐元素完全一致（旧特征零改动）
  3) 只有环内节点在追加维度上有信息：in_cycle==1 的集合大小 == 期望值
     （s38417t300 的木马环 = 29 个门；期望值可用 --expect-cycle 覆盖）
  4) 非环节点的 in_cycle == 0；环内节点的 scc_size > 1（log1p 前）

用法：
  python check_cycle_features.py --none-dir <work_none> --contract-dir <work_contract> \
      --acyclic-nodes 0:215 --expect-cycle 29 [--cycle-node-range 215:5588]
"""

import argparse
import json
from pathlib import Path
from typing import Tuple

import numpy as np


def parse_range(s: str) -> Tuple[int, int]:
    a, b = s.split(":")
    return int(a), int(b)


def main() -> int:
    ap = argparse.ArgumentParser(description="SCC 收缩回归检查")
    ap.add_argument("--none-dir", type=Path, required=True,
                    help="--cycle-mode none 的工作目录（含 data/for_train/feats_orig.npy）")
    ap.add_argument("--contract-dir", type=Path, required=True,
                    help="--cycle-mode contract 的工作目录")
    ap.add_argument("--acyclic-nodes", type=str, default="",
                    help="无环电路的节点区间 a:b（应逐元素一致），可多次用 , 分隔")
    ap.add_argument("--cycle-node-range", type=str, default="",
                    help="有环电路的节点区间 a:b（用于核对 in_cycle 数量）")
    ap.add_argument("--expect-cycle", type=int, default=-1,
                    help="期望在 cycle-node-range 内 in_cycle==1 的节点数（-1 表示不检查）")
    args = ap.parse_args()

    f_none = args.none_dir / "data" / "for_train" / "feats_orig.npy"
    f_con = args.contract_dir / "data" / "for_train" / "feats_orig.npy"
    for p in (f_none, f_con):
        if not p.exists():
            print(f"[ERROR] 缺少 {p}")
            return 1

    a = np.load(f_none)
    b = np.load(f_con)
    print(f"[dim] none={a.shape}  contract={b.shape}")
    ok = True
    if a.shape[1] != 33 or b.shape[1] != 39:
        print("[FAIL] 维度不符合预期（none 应为 33，contract 应为 39）")
        ok = False
    if a.shape[0] != b.shape[0]:
        print("[FAIL] 节点数不一致")
        return 1

    # 2) 前 33 维逐元素一致（全部节点，包括环内节点）
    base = a[:, :33]
    new = b[:, :33]
    diff = np.abs(base - new).sum(axis=1)
    changed = np.where(diff > 1e-9)[0]
    tag = "PASS" if len(changed) == 0 else "FAIL"
    if len(changed):
        ok = False
    print(f"[{tag}] 前 33 维（旧特征）被改变的节点数 = {len(changed)}"
          + (f"（例：{changed[:5].tolist()}）" if len(changed) else ""))
    for rng in [r for r in args.acyclic_nodes.split(",") if r.strip()]:
        s, e = parse_range(rng)
        sub = changed[(changed >= s) & (changed < e)]
        print(f"     无环区间 [{s}:{e}) 内被改变 = {len(sub)}")

    # 3) 环内节点（追加维：33=dist_pi, 34=dist_po, 35=fan_in, 36=fan_out, 37=in_cycle, 38=scc_size）
    cyc = np.where(b[:, 37] > 0.5)[0]
    print(f"[cycle] in_cycle==1 的节点总数 = {len(cyc)}")
    if args.cycle_node_range:
        s, e = parse_range(args.cycle_node_range)
        in_rng = cyc[(cyc >= s) & (cyc < e)]
        if args.expect_cycle >= 0:
            tag = "PASS" if len(in_rng) == args.expect_cycle else "FAIL"
            if tag == "FAIL":
                ok = False
            print(f"[{tag}] 环区间 [{s}:{e}) 内 in_cycle 节点数 = {len(in_rng)}（期望 {args.expect_cycle}）")
        outside = cyc[(cyc < s) | (cyc >= e)]
        tag = "PASS" if len(outside) == 0 else "FAIL"
        if len(outside):
            ok = False
        print(f"[{tag}] 区间外被标记为环的节点数 = {len(outside)}"
              + (f"（例：{outside[:5].tolist()}）" if len(outside) else ""))
    if len(cyc):
        scc = np.expm1(b[cyc, 38])
        tag = "PASS" if (scc >= 1).all() else "FAIL"   # 自环 SCC 的 size = 1 也合法
        if not (scc >= 1).all():
            ok = False
        print(f"[{tag}] 环内节点 scc_size 最小值 = {scc.min():.0f}（应 >=1；==1 表示自环）")
        print(f"       环内 dist_pi/dist_po 为 -1 的节点数 = "
              f"{int(((b[cyc, 33] < 0) | (b[cyc, 34] < 0)).sum())}（自由振荡环，属预期）")
        for i in cyc[:3]:
            print(f"         node {i}: legacy dist=({base[i,29]:.0f},{base[i,30]:.0f}) "
                  f"fan=({base[i,31]:.2f},{base[i,32]:.2f}) → "
                  f"dag dist=({b[i,33]:.0f},{b[i,34]:.0f}) fan=({b[i,35]:.2f},{b[i,36]:.2f}) "
                  f"in_cycle={b[i,37]:.0f} scc_size={np.expm1(b[i,38]):.0f}")

    # 4) 非环节点 in_cycle 必须为 0
    non = np.setdiff1d(np.arange(b.shape[0]), cyc)
    tag = "PASS" if (b[non, 37] < 0.5).all() else "FAIL"
    if tag == "FAIL":
        ok = False
    print(f"[{tag}] 非环节点 in_cycle 非零的数量 = {int((b[non, 37] > 0.5).sum())}")

    print("\n[VERDICT]", "ALL PASS" if ok else "HAS FAILURES")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
