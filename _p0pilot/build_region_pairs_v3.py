"""build_region_pairs_v3.py -- 用 974k/630k node_pairs_sat_node 重建 region_pairs_v3（all-pair，未 canonicalize）。"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(r"C:\Users\91344\Desktop\GraphSAINT\GIN_train")
T = ROOT / "10.15/06_统一评测协议/N4_三向泛化/tables"
PREF = re.compile(r"^(?:\\\\)?(Trojan[A-Za-z0-9]+)")


def pref(s):
    m = PREF.match(str(s or "").strip().lstrip("\\"))
    return m.group(1) if m else ""


def main() -> int:
    p = T / "node_pairs_sat_node.csv"
    d = pd.read_csv(p, encoding="utf-8-sig",
                    usecols=["host", "inst_a", "inst_b", "recipe_a", "recipe_b",
                             "net_a", "net_b", "status"]).fillna("")
    n0 = len(d)
    d = d[(d.inst_a == d.inst_b) & (d.status == "proved")].copy()
    d["ra"] = d.net_a.map(pref)
    d["rb"] = d.net_b.map(pref)
    d = d[(d.ra != "") & (d.rb != "")]
    d["pair"] = d.recipe_a.astype(str) + ":" + d.recipe_b.astype(str)
    print(f"[in] rows={n0} -> proved/same-inst/trojan-both={len(d)}")

    # unique nets per region/pair (for jaccard)
    na = (d.groupby(["host", "inst_a", "pair", "ra"]).net_a.nunique()
          .rename("n_a").reset_index())
    nb = (d.groupby(["host", "inst_b", "pair", "rb"]).net_b.nunique()
          .rename("n_b").reset_index().rename(columns={"inst_b": "inst_a", "rb": "ra"}))
    d = d.rename(columns={"inst_a": "inst"})
    agg = (d.groupby(["host", "inst", "pair", "ra", "rb"]).size()
           .rename("n").reset_index())

    rows, roles = [], []
    for (host, inst, pair, ra), g in agg.groupby(["host", "inst", "pair", "ra"]):
        best = g.sort_values("n", ascending=False).iloc[0]
        rb = str(best["rb"])
        n_edges = int(g["n"].sum())
        n_out = int(len(g))                                  # ra -> 多少个 rb
        back = agg[(agg.host == host) & (agg.inst == inst) & (agg.pair == pair)
                   & (agg.rb == rb)]
        n_in = int(len(back))                                # rb <- 多少个 ra
        mt = ("1:1" if (n_out == 1 and n_in == 1)
              else "1:N" if n_in == 1 else "N:1")
        a_n = int(na[(na.host == host) & (na.inst_a == inst) & (na.pair == pair)
                     & (na.ra == ra)]["n_a"].sum())
        b_n = int(nb[(nb.host == host) & (nb.inst_a == inst) & (nb.pair == pair)
                     & (nb.ra == rb)]["n_b"].sum())
        jac = round(min(1.0, n_edges / max(a_n + b_n - n_edges, 1)), 4)
        rows.append(dict(host=host, inst=inst, pair=pair, region=ra,
                         partner_region=rb, jaccard=jac,
                         n_region_nets=a_n, n_boundary_sigs=0,
                         match_type=mt, n_trusted_trojan=a_n,
                         n_trusted_benign=0, n_mixed=0, n_unknown=0,
                         region_role="trusted_trojan" if n_edges else "unknown",
                         n_pair_edges=float(n_edges)))
        roles.append(dict(host=host, inst=inst, pair=pair, region=ra,
                          partner_region=rb, match_type=mt,
                          n_pair_edges=int(n_edges), region_role="trusted_trojan"))

    out = pd.DataFrame(rows).sort_values(["host", "inst", "pair", "region"])
    out.to_csv(T / "region_pairs_v3.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(roles).to_csv(T / "region_role_status_v3.csv", index=False,
                               encoding="utf-8-sig")
    print(f"[out] {T / 'region_pairs_v3.csv'} rows={len(out)}")
    print(out["match_type"].value_counts().to_string())
    print(out["region_role"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
