# -*- coding: utf-8 -*-
"""
objects.py —— 对象级分组（供 M3 的 object-aware consistency 使用）

从 `mappings/<view>.json` 的 `node_alignment`（实例名级血缘）+ `phase2/name_index.py`
（实例名→全局节点索引）构造每个视图的「对象 → 目标节点集合」：

    view -> [ (o_idx, np.array([t_idx, ...])), ... ]

只保留 **verified object**：在 mapping 里显式出现且至少有一个目标节点真实存在于该视图。
`1→1` 的对象就是一个元素；`1→N`（split）的目标集合会被 **region pooling**（mean）成一个向量，
因此不再要求逐门一一对应。

用法：
  from phase2.objects import build_object_groups
  groups = build_object_groups(work_dir)          # {view: [(o_idx, np.ndarray), ...]}
"""
from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from phase2.name_index import build_name_index


def _clean(n: str) -> str:
    return str(n).lstrip("\\")


def build_object_groups(work_dir: Path, include_identity: bool = False) -> Dict[str, List[Tuple[int, np.ndarray]]]:
    """返回 {view: [(o_idx, t_idx_array), ...]}。

    include_identity=False（默认）：只用 mapping 里的**显式血缘**（verified objects），
    与 T22.siamese_loss 里「显式 + 同名身份回落」的全量 alignment 不同——
    这正是 M3 想表达的"只有 verified object 才做约束"。
    """
    work = Path(work_dir).resolve()
    idx = build_name_index(work)
    out: Dict[str, List[Tuple[int, np.ndarray]]] = OrderedDict()
    for f in sorted((work / "mappings").glob("*.json")):
        view = f.stem
        trans_names = idx["trans"].get(view, {})
        if not trans_names:
            continue
        md = json.loads(f.read_text(encoding="utf-8"))
        src = str(md.get("src_verilog", "")).replace(".v", "")
        orig_names = idx["orig"].get(src, {})
        tset = set(trans_names)
        items: List[Tuple[int, np.ndarray]] = []
        for o_name, t_names in (md.get("node_alignment", {}) or {}).items():
            o = _clean(o_name)
            if o not in orig_names:
                continue
            tt = [trans_names[_clean(t)] for t in (t_names or []) if _clean(t) in tset]
            if tt:
                items.append((int(orig_names[o]), np.asarray(sorted(set(tt)), dtype=np.int64)))
        if include_identity:
            covered = {o for o, _ in items}
            for o, oi in orig_names.items():
                if oi not in covered and o in tset:
                    items.append((int(oi), np.asarray([trans_names[o]], dtype=np.int64)))
        if items:
            out[view] = items
    return out


def summarize_groups(groups) -> Dict[str, float]:
    sizes = np.concatenate([np.array([len(t) for _, t in v]) for v in groups.values()]) \
        if groups else np.array([1])
    return {"views": len(groups),
            "objects": int(sum(len(v) for v in groups.values())),
            "share_1to1": float((sizes == 1).mean()),
            "share_split": float((sizes > 1).mean()),
            "max_group": int(sizes.max())}
