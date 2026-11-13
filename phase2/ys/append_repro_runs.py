"""append_repro_runs.py —— 把 `results/` 里**尚未入索引**的运行补进 `repro/index.csv` ✓。

用途 ✓：新跑的 run（LIO@100ep、A4 seeds 1/2、LRO@100ep …）不会自动进索引 ✗ → 本脚本按目录名解析 seed ✓、
读 `run_config.json` ✓，追加 `kind=run` 行 ✓。**只追加、不改已有行** ✓。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
IDX = ROOT / "10.15" / "99_共用资产" / "repro" / "index.csv"


def main() -> int:
    d = pd.read_csv(IDX, encoding="utf-8-sig", dtype=str).fillna("")
    have = set(d["id"])
    add = []
    for p in sorted((ROOT / "results").iterdir()):
        if not p.is_dir() or p.name in have:
            continue
        cfg = p / "run_config.json"
        if not cfg.exists():
            continue                      # 只收有配置的 run ✓（可复现 ✓）
        try:
            c = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:                 # noqa: BLE001
            c = {}
        m = re.search(r"seed([0-9]+)mode", p.name)
        seed = m.group(1) if m else str(c.get("seed", "") or "")
        ep = c.get("epochs", c.get("n_epochs", ""))
        add.append(dict(kind="run", id=p.name,
                        path=str(p.relative_to(ROOT)),
                        seed=seed,
                        config=str(cfg.relative_to(ROOT)),
                        note=f"epochs={ep}" if ep != "" else ""))
    if not add:
        print("[repro] 无新增 ✓")
        return 0
    out = pd.concat([d, pd.DataFrame(add)], ignore_index=True)
    out.to_csv(IDX, index=False, encoding="utf-8-sig")
    print(f"[repro] 追加 {len(add)} 行 ✓ → 共 {len(out)} 行（{IDX}）")
    for r in add:
        print("  +", r["id"], "seed=", r["seed"], r["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
