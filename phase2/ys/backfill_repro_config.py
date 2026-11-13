"""backfill_repro_config.py —— P3 ✓：给 `repro/index.csv` 回填 **config 列** ✓。

做法 ✓：`kind=run` 的行，`path` 就是 `results/<run_id>` ✓ → 找 `run_config.json` ✓；
`kind=table` 的行，`path` 是 CSV ✓ → 找**同目录/上层**的 `说明.md` 所引配置 ✗（不回填 ✓，标 `n/a` ✓）。
不改任何实验结果 ✗，只补索引 ✓。
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
IDX = ROOT / "10.15" / "99_共用资产" / "repro" / "index.csv"


def find_cfg(p: Path) -> str:
    if not p.exists():
        return ""
    cands = [p / "run_config.json", p.parent / "run_config.json"]
    cands += list(p.glob("*/run_config.json"))[:1]
    for c in cands:
        if c.exists() and c.is_file():
            try:
                return str(c.relative_to(ROOT))
            except ValueError:
                return str(c)
    return ""


def main() -> int:
    d = pd.read_csv(IDX, encoding="utf-8-sig", dtype=str).fillna("")
    before = int((d["config"] != "").sum())
    n_run = 0
    for i, row in d.iterrows():
        if row["config"]:
            continue
        if row["kind"] != "run":
            continue
        cfg = find_cfg(ROOT / row["path"])
        if cfg:
            d.at[i, "config"] = cfg
            n_run += 1
    after = int((d["config"] != "").sum())
    d.to_csv(IDX, index=False, encoding="utf-8-sig")
    print(f"[repro] rows={len(d)}  config 非空: {before} → {after}（回填 {n_run} 行 ✓）")
    print(f"[repro] 仍空: {int((d['config'] == '').sum())} 行（多为 table/scores 派生件 ✓）")
    print(f"[out] {IDX}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
