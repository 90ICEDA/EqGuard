#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_dataset_coverage.py — 数据集血缘/标签覆盖率体检（多视图工作目录必备）

检查每个 fold 工作目录的三件事：
  1) class_map / feats 的节点数是否一致，每个视图的节点数与 global 索引区间
  2) alignment.json 是否覆盖了 **每一个** 视图（避免多视图下只在部分视图建立血缘）
  3) label transport 是否覆盖每个视图的节点（transported 标签缺失会导致标签静默为 0）

用法：
  python check_dataset_coverage.py <work_dir> [<work_dir2> ...]
"""

import collections
import json
import sys
from pathlib import Path

import numpy as np


def check(work_dir: str) -> bool:
    d = Path(work_dir).resolve()
    ft = d / "data" / "for_train"
    if not ft.exists():
        print(f"[ERROR] {ft} 不存在")
        return False
    print(f"\n=== {d} ===")
    ok = True

    for suf in ("orig", "trans"):
        meta = json.loads((ft / f"metadata_{suf}.json").read_text(encoding="utf-8"))
        fid = meta["file_ids"]
        cnt = collections.Counter(fid)
        off, o, prev = {}, 0, None
        for v in fid:
            if v != prev:
                off[v] = o
                prev = v
            o += 1
        feats = np.load(ft / f"feats_{suf}.npy", mmap_mode="r")
        cm = json.loads((ft / f"class_map_{suf}.json").read_text(encoding="utf-8"))
        same = feats.shape[0] == len(cm) == len(fid)
        ok &= same
        print(f"[{'OK ' if same else 'BAD'}] {suf}: nodes(feats)={feats.shape[0]} "
              f"dims={feats.shape[1]} class_map={len(cm)} file_ids={len(fid)}｜视图数={len(cnt)}")
        if len(cnt) <= 8:
            print(f"        per-view={dict(cnt)}")

    ali = json.loads((ft / "alignment.json").read_text(encoding="utf-8"))
    mt = json.loads((ft / "metadata_trans.json").read_text(encoding="utf-8"))
    fid = mt["file_ids"]
    n_views = len(set(fid))
    hits = collections.Counter(fid[p[1]] for p in ali)
    cov_ok = len(hits) == n_views
    ok &= cov_ok
    print(f"[{'OK ' if cov_ok else 'BAD'}] alignment: {len(ali)} 对，覆盖 {len(hits)}/{n_views} 个视图，"
          f"t_idx ∈ [{min(p[1] for p in ali)}, {max(p[1] for p in ali)}]")
    if not cov_ok:
        print(f"        未被覆盖的视图：{sorted(set(fid) - set(hits))[:5]}")

    per = collections.Counter(fid[p[1]] for p in ali)
    cov = collections.Counter(fid[int(k)] for k in
                              json.loads((ft / "class_map_trans_transported.json").read_text(encoding="utf-8")))
    # 判定标准：每个视图的 **transported 标签覆盖** 必须等于该视图节点数；
    # 血缘对数量可以 > 节点数（1:N 展开），因此只要求 >=。
    bad = [(v, n, per.get(v, 0), cov.get(v, 0))
           for v, n in collections.Counter(fid).items() if cov.get(v, 0) != n]
    ok &= not bad
    print(f"[{'OK ' if not bad else 'BAD'}] transported 标签覆盖每个视图全部节点：{not bad}"
          f"（视图数={n_views}，血缘对/节点 = {len(ali)}/{len(fid)}）")
    if bad:
        print(f"        覆盖不足的视图（view, nodes, pairs, transported）：{bad[:5]}")
    return ok


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    all_ok = all(check(p) for p in sys.argv[1:])
    print("\n[VERDICT]", "ALL PASS" if all_ok else "HAS ISSUES")
