"""f8_pair_hit.py -- 只读：同一 spec 的 proved node pairs 在旧/新解析器下的命中数。"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[1]))
from eqguard_paths import project_path as _eqguard_path

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(_eqguard_path(''))
sys.path.insert(0, str(ROOT / "phase2/ys"))
import f8_rewrite_case as F8  # noqa: E402
import f8_dot as D  # noqa: E402


def load(recipe):
    p = F8.VDIR / f"s38417t100__injalpha_d1_s42__{recipe}.v"
    cells = F8.parse_v(p)
    drv_old, _ = F8.build_graph(cells)
    dsu, tops = D.parse_assign_alias(p)
    cc = D.canonical_cells(cells, dsu)
    drv_new, _ = F8.build_graph(cc)
    return cells, drv_old, dsu, drv_new


if __name__ == "__main__":
    t = F8.T / "node_pairs_sat_node.csv"
    d = pd.read_csv(t, encoding="utf-8-sig", usecols=["host", "inst_a", "inst_b", "recipe_a",
                                                      "recipe_b", "net_a", "net_b", "status"]).fillna("")
    m = ((d["host"] == "s38417t100") & (d["inst_a"] == "injalpha") & (d["inst_b"] == "injalpha")
         & (d["recipe_a"] == "id") & (d["recipe_b"] == "abc") & (d["status"] == "proved"))
    pairs = d[m][["net_a", "net_b"]].drop_duplicates()
    print(f"proved unique pairs: {len(pairs)}")

    ca, old_a, dsu_a, new_a = load("ys_id")
    cb, old_b, dsu_b, new_b = load("ys_abc")
    hit_old = hit_new = both_old = both_new = 0
    for _, r in pairs.iterrows():
        a, b = str(r["net_a"]), str(r["net_b"])
        ha_o, hb_o = bool(old_a.get(a)), bool(old_b.get(b))
        ha_n, hb_n = bool(new_a.get(dsu_a.find(a))), bool(new_b.get(dsu_b.find(b)))
        hit_old += ha_o
        hit_new += ha_n
        both_old += ha_o and hb_o
        both_new += ha_n and hb_n
    print(f"A-side driven (old/new): {hit_old}/{len(pairs)} -> {hit_new}/{len(pairs)}")
    print(f"B-side driven (old/new): see both-in-region below")
    print(f"both-side driven (old/new): {both_old} -> {both_new}")
