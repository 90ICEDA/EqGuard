"""make_node_pairs_summary.py —— B05 汇总 ✓（`node_pairs_summary.csv` ✓）。

把 `node_pairs.csv`（逐网 ✓）压成 per (host, inst, pair) 的**证明率** ✓，
并单列 **木马网子集**（`Trojan*` ✓）—— 只有这个子集能进 `L_eq` 的候选 ✓（见 B07 `role_status` ✓）。
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
TDIR = ROOT / "10.15" / "06_统一评测协议" / "N4_三向泛化" / "tables"


def main() -> int:
    src = TDIR / "node_pairs.csv"
    if not src.exists():
        print("[warn] 缺 node_pairs.csv ✗")
        return 1
    df = pd.read_csv(src, encoding="utf-8-sig").fillna("")
    df["is_trojan"] = df["net"].astype(str).str.contains("Trojan", case=False)
    rows = []
    for (host, inst, pair), g in df.groupby(["host", "inst", "pair"]):
        t = g[g["is_trojan"]]
        rows.append(dict(
            host=host, inst=inst, pair=pair,
            n_total=len(g), n_proved=int((g["status"] == "proved").sum()),
            n_differ=int((g["status"] == "differ").sum()),
            proved_ratio=round(float((g["status"] == "proved").mean()), 4),
            n_trojan_total=len(t), n_trojan_proved=int((t["status"] == "proved").sum()),
            trojan_proved_ratio=round(float((t["status"] == "proved").mean()), 4) if len(t) else 0.0))
    sm = pd.DataFrame(rows).sort_values(["host", "inst", "pair"])
    out = TDIR / "node_pairs_summary.csv"
    sm.to_csv(out, index=False, encoding="utf-8-sig")
    print(sm.to_string(index=False))
    print(f"\n[out] {out}（{len(sm)} 行 ✓）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
