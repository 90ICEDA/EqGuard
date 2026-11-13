# -*- coding: utf-8 -*-
"""make_prim_feats.py —— 原语等价类特征：把"库单元 one-hot"换成"原语构成"。

动机（由特征保持率审计 + 词汇表对照确定）：
    自写重写保留复合单元（AOIX / OAIX / OAX / NANDX / NORX / BUFX / ISOLANDX / SDFFX …），
    而**所有** yosys 变体（abc / aig / 纯往返 flatten）都把逻辑塌成原语
    （AND / OR / INV + 少量 MUX / XOR），**只有触发器原样保留**。
    所以"门类型 one-hot"这 25 维在变体上整体失效 ✗（保持率表里它们要么归零要么反向）。
    对策：把每个库单元按**原语构成**编码 —— AOI = AND+OR+INV、NAND = AND+INV、
    XNOR = XOR+INV …… 于是"同一个逻辑"在两种词汇表下落到同一组特征上 ✓

写回布局（维度仍 39，因为 siamese_loss 会按下标读 x[:,29]）：
    dims 0..6   原语构成（AND / OR / INV / XOR / MUX / DFF / OTHER，逐节点归一化为和为 1）
    dims 7..24  置零（原库单元 one-hot，词汇表一变就失效 ✗）
    dims 25..38 只保留 --structural 列表里的那几维（默认用保持率 ≥ 0.30 的那 5 维），其余置零

用法：
    py phase2/ys/make_prim_feats.py --src 10.13/group_fold_ys5 --out 10.13/group_fold_ys5_prim
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

PRIM = ["AND", "OR", "INV", "XOR", "MUX", "DFF", "OTHER"]

# 库单元 → 原语构成。依据：复合单元的名字即其构成（AOI=AND-OR-INVERT、OAI=OR-AND-INVERT、
# AOX=AND-OR、OAX=OR-AND、HADD=半加、NAND/NOR/XNOR 为基本门加反相器）；
# 触发器变体（扫描/异步复位/负沿）都归 DFF；无法确定构成的（硬宏/工艺标记）归 OTHER。
CELL2PRIM = {
    "ANDX": {"AND": 1}, "ORX": {"OR": 1}, "INVX": {"INV": 1},
    "NANDX": {"AND": 1, "INV": 1}, "NORX": {"OR": 1, "INV": 1},
    "XORX": {"XOR": 1}, "XNORX": {"XOR": 1, "INV": 1},
    "AOIX": {"AND": 1, "OR": 1, "INV": 1}, "OAIX": {"OR": 1, "AND": 1, "INV": 1},
    "AOX": {"AND": 1, "OR": 1}, "OAX": {"OR": 1, "AND": 1},
    "HADDX": {"XOR": 1, "AND": 1}, "MUXX": {"MUX": 1},
    "ISOLANDX": {"AND": 1}, "BUFX": {"OTHER": 1},
    "LSDNX": {"OTHER": 1}, "LSDNENX": {"OTHER": 1},
    "DFFX": {"DFF": 1}, "DFFARX": {"DFF": 1}, "DFFNX": {"DFF": 1},
    "SDFFX": {"DFF": 1}, "SDFFSRX": {"DFF": 1},
    "HARD_INC": {"OTHER": 1}, "TOP_HARD": {"OTHER": 1}, "TOP_RVT": {"OTHER": 1},
}
# 结构/拓扑维里"保持率 ≥ 0.30"的那 5 维（来自 10.13/feature_retention_g5.csv）
STRUCT_KEEP = ["log1p_degree", "touches_PI", "dist_to_PO",
               "log1p_fan_in_2hop", "log1p_fan_out_2hop"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--structural", default=",".join(STRUCT_KEEP))
    ap.add_argument("--zero-dim29", action="store_true",
                    help="额外把 dim29(=dist_to_PI, 伪信号) 置零（默认已置零，此开关仅作显式标明）")
    a = ap.parse_args()

    keep = [x.strip() for x in a.structural.split(",") if x.strip()]
    order, _groups = feature_names(a.src)
    gate_names = [n[5:] for n in order[:25]]
    missing = [g for g in gate_names if g not in CELL2PRIM]
    if missing:
        print(f"[ERROR] 有库单元没写进原语表：{missing}")
        return 1
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
        G = X[:, :25]
        P = np.zeros((len(X), len(PRIM)), dtype=np.float64)
        for j, gn in enumerate(gate_names):
            comp = CELL2PRIM[gn]
            idx = np.flatnonzero(G[:, j] > 0)
            if len(idx) == 0:
                continue
            for k, v in comp.items():
                P[idx, PRIM.index(k)] += v
        s = P.sum(axis=1, keepdims=True)
        s[s == 0] = 1.0
        P = P / s                                     # 逐节点归一化：看的是"构成比例"
        newX = np.zeros_like(X)
        newX[:, :len(PRIM)] = P
        for n in keep:
            if n in name2idx:
                newX[:, name2idx[n]] = X[:, name2idx[n]]
        g.x = torch.tensor(newX, dtype=g.x.dtype)
        torch.save(g, outp / fn)
        stats[fn] = {"rows": int(len(X)),
                     "prim_share": {PRIM[k]: round(float(P[:, k].mean()), 4)
                                    for k in range(len(PRIM))},
                     "nonzero_in_row": round(float((newX != 0).sum(axis=1).mean()), 2)}

    for fn in ("views.json", "dataset_meta.json", "gatelookup_recommended.json"):
        for d in (srcp, a.src):
            p = d / fn
            if p.exists():
                shutil.copy2(p, outp / fn)
                shutil.copy2(p, a.out / fn)
                break

    info = {"cell2prim": CELL2PRIM, "prim_dims": PRIM,
            "kept_structural": keep,
            "note": "dims0..6=原语构成(和为1)；dims7..24 置零；dims25..38 只留 kept_structural",
            "stats": stats}
    (a.out / "prim_feats.json").write_text(json.dumps(info, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    print(f"[原语维] {PRIM}")
    print(f"[保留结构维] {keep}")
    for fn, st in stats.items():
        print(f"[{fn}] 行 {st['rows']}｜原语占比 {st['prim_share']}｜每行非零维 {st['nonzero_in_row']}")
    print(f"[导出] {outp} + prim_feats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
