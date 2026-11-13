"""make_trust_mask.py —— B1：节点级"可信标签"掩码。

定义（与你定的口径一致 ✓）：
  · **trusted** = 该 trans 节点在 `class_map_trans_transported.json` 里有标签 ✓
    （即能追到源门 ✓）；**unknown** = 其余 ✗（当前训练把它们当 0 ✗）。
  · orig 侧：源网表的门都有名字/血缘 ✓ → 全 trusted ✓。

产物：`<work>/data/for_train/trust_trans.npy` / `trust_orig.npy`（bool ✓）。
训练时用 `--label-mask trust` ✓：`train_mask &= trust` ✓（验证/测试仍用全节点 ✓，指标可比 ✓）。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-dir", type=Path, required=True)
    a = ap.parse_args()
    ft = a.work_dir / "data" / "for_train"

    mt = json.loads((ft / "metadata_trans.json").read_text(encoding="utf-8"))
    n_t = int(len(mt["file_ids"]))
    cm = json.loads((ft / "class_map_trans_transported.json").read_text(encoding="utf-8"))
    trust_t = np.zeros(n_t, dtype=bool)
    idx = np.fromiter((int(k) for k in cm.keys()), dtype=np.int64, count=len(cm))
    idx = idx[(idx >= 0) & (idx < n_t)]
    trust_t[idx] = True

    mo = json.loads((ft / "metadata_orig.json").read_text(encoding="utf-8"))
    n_o = int(len(mo["file_ids"]))
    trust_o = np.ones(n_o, dtype=bool)

    np.save(ft / "trust_trans.npy", trust_t)
    np.save(ft / "trust_orig.npy", trust_o)
    print(f"[trust] trans {int(trust_t.sum())}/{n_t} = {trust_t.mean():.4f} ✓｜orig {int(trust_o.sum())}/{n_o} = 1.0000 ✓")
    print(f"[导出] {ft}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
