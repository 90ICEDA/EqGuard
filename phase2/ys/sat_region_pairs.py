"""sat_region_pairs.py —— B06：**跨实现区域对** ✓（`region_pairs.csv` ✓）。

区域定义 ✓（可机器判定 ✓）：木马子电路按**前缀**分组（`TrojanAHJ` / `TrojanAP0` … ✓），
每个前缀 = 一个"区域"（等价于插入记录里的一个逻辑块 ✓）；
跨区域边界 = 该区域**扇入/扇出**到区域外的网 ✓。

输出 ✓（每 host×inst×pair×region 一行 ✓）：
  `n_nets` / `n_proved` / `proved_ratio` ✓（区域内逐网 SAT 证明率 ✓）
  `n_boundary` / `n_boundary_proved` / `boundary_proved_ratio` ✓（区域边界网的证明率 ✓）
  `boundary_match ∈ {full, partial, none}` ✓
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
BASE = ROOT / "10.15/06_统一评测协议/N4_三向泛化"
LOGS = BASE / "logs"
PREF = re.compile(r"^(?:\\\\)?(Trojan[A-Za-z0-9]+)")


def load_graph(js: Path):
    d = json.loads(js.read_text(encoding="utf-8"))
    mod = d["modules"][list(d["modules"])[0]]
    names: dict[int, str] = {}
    for nm, info in mod.get("netnames", {}).items():
        for b in info.get("bits", []):
            if isinstance(b, int) and (b not in names or names[b].startswith("$")):
                names[b] = nm
    con, drv = {}, {}
    for cname, cell in mod.get("cells", {}).items():
        for port, bits in cell.get("connections", {}).items():
            for b in bits:
                if not isinstance(b, int):
                    continue
                if port in ("Y", "Q", "QN"):
                    drv.setdefault(b, cname)
                else:
                    con.setdefault(b, []).append(cname)
    return names, con, drv, mod["cells"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=str(BASE / "tables/node_pairs.csv"))
    ap.add_argument("--out", default=str(BASE / "tables/region_pairs.csv"))
    a = ap.parse_args()

    df = pd.read_csv(a.pairs, encoding="utf-8-sig").fillna("")
    df["region"] = df["net"].astype(str).map(
        lambda s: (PREF.match(s).group(1) if PREF.match(s) else ""))
    stat_map: dict[tuple, dict] = {}
    for (h, i, p), gg in df.groupby(["host", "inst", "pair"]):
        stat_map[(h, i, p)] = dict(zip(gg["net"].astype(str), gg["status"].astype(str)))
    rows = []
    for (host, inst), g in df.groupby(["host", "inst"]):
        cand = sorted(LOGS.glob(f"{host}__{inst}_d1_s42__*ys_id.json"))
        if not cand:
            continue
        names, con, drv, cells = load_graph(cand[0])
        bit_of: dict[str, int] = {}
        for b, n in names.items():
            bit_of.setdefault(n, b)
        for (pair, region), gg in g[g["region"] != ""].groupby(["pair", "region"]):
            nets = gg["net"].astype(str).tolist()
            proved = int((gg["status"] == "proved").sum())
            # ---- 边界：该区域网的 fanin/fanout 到区域外的网 ✓
            boundary = set()
            for n in nets:
                b = bit_of.get(n)
                if b is None:
                    continue
                for cname in con.get(b, []):
                    for port, bits in cells[cname].get("connections", {}).items():
                        if port in ("Y", "Q", "QN"):
                            for ob in bits:
                                if isinstance(ob, int):
                                    on = names.get(ob, "")
                                    if on and not on.startswith(region):
                                        boundary.add(on)
            bstat = stat_map.get((host, inst, pair), {})
            nb = len(boundary)
            nbp = sum(1 for x in boundary if bstat.get(x) == "proved")
            rows.append(dict(
                host=host, inst=inst, pair=pair, region=region,
                n_nets=len(nets), n_proved=proved,
                proved_ratio=round(proved / max(len(nets), 1), 4),
                n_boundary=nb, n_boundary_proved=nbp,
                boundary_proved_ratio=round(nbp / nb, 4) if nb else 0.0,
                boundary_match=("full" if nb and nbp == nb else
                                "partial" if nbp else "none")))
    out = pd.DataFrame(rows).sort_values(["host", "inst", "pair", "region"])
    out.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"[out] {a.out}（{len(out)} 行 ✓）")
    print(out.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
