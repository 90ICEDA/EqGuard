"""fix_node_pairs_csv.py -- 修复 `node_pairs_sat_node.csv` 里被磁盘写满截断的坏行。

背景 ✗：2026-10-23 23:51 磁盘满（OSError 28），`_write_rows` 的临时文件没写完 →
        主表首行留下一条「只有 log 文件名、其余字段全空」的残行 ⚠️。
做法 ✓：只保留 `host ∈ {5 个宿主}` 且关键字段非空、status ∈ {proved,differ} 的行；
        写 `*.tmp.csv` 后 `os.replace` 原子替换（与 `sat_node_pairs_batch.py` 同一套路 ✓）。
        **全列按字符串读** ✓，`sig_hex` 的前导 0 不会被改写 ✓。

用法：
  ginvenv\\Scripts\\python.exe -X utf8 phase2/ys/fix_node_pairs_csv.py
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import os
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
D15 = next(p for p in (ROOT / "10.15").iterdir()
           if p.is_dir() and p.name.startswith("06_"))
N4 = next(p for p in D15.iterdir()
          if p.is_dir() and p.name.startswith("N4_") and "_100ep" not in p.name)
CSV = N4 / "tables" / "node_pairs_sat_node.csv"
HOSTS = {"rs232t1000", "s15850t100", "s35932t200", "s38417t100", "s38584t100"}


def main() -> int:
    if not CSV.exists():
        raise SystemExit(f"[ERROR] 缺 {CSV} ✗")
    d = pd.read_csv(CSV, encoding="utf-8-sig", dtype=str)
    n0 = len(d)
    bad = (~d["host"].isin(HOSTS)
           | d["pair"].isna() | d["net_a"].isna() | d["net_b"].isna()
           | ~d["status"].isin(["proved", "differ"]))
    n_bad = int(bad.sum())
    if n_bad:
        print("[bad rows]")
        print(d[bad].head(10).to_string())
    d = d[~bad].reset_index(drop=True)
    tmp = CSV.with_name(CSV.stem + ".tmp.csv")
    d.to_csv(tmp, index=False, encoding="utf-8-sig")
    os.replace(tmp, CSV)
    print(f"[fix] {CSV.name}: {n0} -> {len(d)} rows (dropped {n_bad}) ✓")
    if len(d):
        print("[by host]")
        print(d.groupby("host").size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
