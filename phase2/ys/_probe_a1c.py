# -*- coding: utf-8 -*-
"""_probe_a1c.py —— 查清：(1) 哪些 src_view 在 orig 名字索引里查不到；(2) aig 视图那个正节点是谁。"""
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

OUT = Path("10.15/01_数据与标签/A1_变换统计/_probe_a1c.txt")
L = []


def sec(t):
    L.append("=" * 12 + " " + t + " " + "=" * 12)


for tag, fold in (("v2", "generate_trans/folds/hosts_beta2"), ("v1", "generate_trans/folds/hosts_beta")):
    F = Path(fold)
    ni = json.loads((F / "phase2_name_index.json").read_text(encoding="utf-8"))
    vm = pd.read_csv(F / "views_meta.csv")
    o = set(ni.get("orig", {}))
    sec(f"{tag} {fold}: orig 索引 {len(o)} 个，views_meta {len(vm)} 行")
    L.append("orig 索引里的键（前 40）: " + ", ".join(sorted(o)[:40]))
    miss = vm[~vm["src_view"].isin(o)]
    L.append(f"查不到的 src_view: {len(miss)} 行；按 op/kind 统计:")
    for k, v in Counter(miss["op"].astype(str) + "/" + miss["kind"].astype(str)).items():
        L.append(f"    {k}: {v}")
    L.append("查不到的 src_view 去重（前 25）: " + ", ".join(sorted(set(miss['src_view']))[:25]))
    hit = vm[vm["src_view"].isin(o)]
    L.append(f"能查到: {len(hit)} 行；src_view 去重 {hit['src_view'].nunique()} 个")

# aig 视图的正节点：直接从 trans 图上读（CPU torch）
sec("aig 视图的转后正节点（从 trans_graph.pt 读）")
try:
    import torch
    p = Path("10.13/group_fold_v2/processed/trans_graph.pt")
    g = torch.load(p, map_location="cpu", weights_only=False)
    L.append(f"trans_graph.pt 类型 {type(g).__name__}")
    keys = list(g.keys())[:20] if isinstance(g, dict) else [a for a in dir(g) if not a.startswith("_")][:20]
    L.append("图对象字段: " + ", ".join(map(str, keys)))
    y = g["y"] if isinstance(g, dict) else g.y
    view = g["view"] if isinstance(g, dict) else g.view
    import numpy as np
    yv = np.asarray(y).reshape(-1) if not torch.is_tensor(y) else y.reshape(-1).numpy()
    vv = list(view) if isinstance(view, (list, tuple)) else (view.tolist() if hasattr(view, "tolist") else view)
    L.append(f"节点 {len(yv)}，正节点 {int((yv > 0.5).sum())}")
    # 逐视图统计：aig 与 rt 对照
    agg = defaultdict(lambda: [0, 0])
    for i, v in enumerate(vv):
        a = agg[str(v)]
        a[0] += 1
        if yv[i] > 0.5:
            a[1] += 1
    for k in sorted(agg):
        if "__ys_aig" in k and ("inj" in k or "ctl" in k):
            L.append(f"    {k[:70]:<70} 节点 {agg[k][0]:>6} 正 {agg[k][1]}")
except Exception as e:  # noqa: BLE001
    L.append(f"<读图失败: {type(e).__name__}: {e}>")

OUT.write_text("\n".join(L), encoding="utf-8")
print("done")
