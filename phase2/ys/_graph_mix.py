# -*- coding: utf-8 -*-
"""_graph_mix.py —— 核对 GNN 实际拿到的图：节点数、正样本数、门类型分布。

用途（回答"模型看到的会不会是全是 assign 的网表"这类质疑）：
    确认每个变体视图在图里都是**合法的库单元节点**（门 one-hot 非零），
    而不是退化成空节点/接线节点。
用法：py phase2/ys/_graph_mix.py --pt 10.13/group_fold_ys5/processed --view-sub injalpha
"""
import argparse
import collections
import json
import sys
from pathlib import Path

import numpy as np
import torch

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path, required=True)
    ap.add_argument("--gl", type=Path, default=None, help="gatelookup_recommended.json")
    ap.add_argument("--view-sub", default="injalpha")
    a = ap.parse_args()

    t = torch.load(a.pt / "trans_graph.pt", weights_only=False)
    glp = a.gl or (a.pt.parent / "gatelookup_recommended.json")
    if not glp.exists():
        glp = a.pt / "gatelookup_recommended.json"
    gl = json.loads(glp.read_text(encoding="utf-8"))
    order = gl.get("simplified_gate_type_order") or list(gl["gatelookup"])

    X = t.x.numpy()
    y = t.y.numpy()
    fids = list(t.file_ids)
    views = [v for v in dict.fromkeys(fids) if a.view_sub in str(v) and "__" in str(v)]
    print(f"[口径] {a.pt}｜命中 {len(views)} 个视图｜特征 {X.shape[1]} 维")
    for v in views:
        m = np.array([x == v for x in fids])
        if m.sum() == 0:
            continue
        g, yy = X[m][:, :25], y[m]
        c = collections.Counter()
        for i in range(int(m.sum())):
            idx = np.flatnonzero(g[i] > 0)
            c["|".join(order[j] for j in idx) if len(idx) else "NONE"] += 1
        tag = str(v).split("__", 1)[1]
        print(f"{tag:<34} 节点 {int(m.sum()):>4} 正样本 {int(yy.sum()):>3} "
              f"非零门 {int((g.sum(1) > 0).sum()):>4} | {c.most_common(6)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
