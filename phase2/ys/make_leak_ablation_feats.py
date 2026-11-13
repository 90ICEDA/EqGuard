"""make_leak_ablation_feats.py -- 生成“去泄漏”节点特征变体（只写新文件，不改主特征）。

背景 ✗：`satrel_node_feats_sat.npy` 第 7 维（= full 的第 13 维 `region_edges`）只在
        **名字以 `Trojan` 开头**的节点上非零（`sat_region_pairs.py` 用 `PREF=Trojan...` 划区域，
        `satrel_node_feats_sat.py` 也只给 `nm.startswith("Trojan")` 的节点赋值）→ 等价于
        “该节点是不是注入木马”的标签指示器 ⚠️。

输出 ✓（同目录，形状不变，便于 `--extra-node-file` 直接加载）：
  satrel_node_feats_sat_noregion.npy   : 第 7 维置 0（去掉 region_edges）
  satrel_node_feats_sat_nocovprov.npy  : 第 5/6/8 维置 0（proved_cnt / proved_ratio / covered）
  satrel_node_feats_sat_funconly.npy   : 只留 [0..3]（control/decided/influence/observable），其余置 0

用法：
  ginvenv\\Scripts\\python.exe -X utf8 phase2/ys/make_leak_ablation_feats.py
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

from pathlib import Path

import numpy as np

ROOT = Path(_eqguard_path(''))
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"
SRC = PT / "satrel_node_feats_sat.npy"


def main() -> int:
    F = np.load(SRC)
    if F.ndim != 2 or F.shape[1] != 9:
        raise SystemExit(f"[ERROR] 期望 9 维，实际 {F.shape} ✗")
    out = {
        "satrel_node_feats_sat_noregion.npy": [7],
        "satrel_node_feats_sat_nocovprov.npy": [5, 6, 8],
        "satrel_node_feats_sat_funconly.npy": [4, 5, 6, 7, 8],
    }
    for name, cols in out.items():
        G = F.copy()
        G[:, cols] = 0.0
        np.save(PT / name, G)
        nz = (G != 0).any(1).mean()
        print(f"[out] {name}: zero cols={cols} nonzero_nodes={nz:.4%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
