# -*- coding: utf-8 -*-
"""_test_feats.py —— netlist_feats 冒烟：原网表 vs yosys 变体。"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from phase2.netlist_lib import load_library, parse_netlist  # noqa: E402
from phase2.ys import netlist_feats as NF  # noqa: E402

V = Path("C:/Users/91344/Desktop/GraphSAINT/GraphSAINT-train/vali/verilog_lib.v")
R = Path("generate_trans")
lib = load_library(V)
sem = NF.load_cell_semantics(V)
print(f"lib cells={len(sem)}  AOI221X1={sem.get('AOI221X1', {}).get('exprs')}")

files = [("orig", R / "hosts/rs232t1000/base/rs232t1000_clean.v")]
for r in ("id", "opt", "abc", "aig", "nand"):
    p = R / f"yosys_netlists/rs232t1000/rs232t1000_clean__ys_{r}.v"
    if p.exists():
        files.append((f"ys_{r}", p))

res = {}
for tag, f in files:
    nl = parse_netlist(f, lib)
    gates, rows, info = NF.circuit_features(nl, sem)
    d = pd.DataFrame(rows)
    res[tag] = d
    print(f"[{tag}] gates={info['n_gates']} ff={info.get('n_ff')} "
          f"unknown_sem={info['n_unknown_sem']} n_insts={len(nl.insts)} n_assigns={len(nl.assigns)}")
    print("   mean:", d[["sp", "toggle_rate", "cc0", "cc1", "co", "influence_in",
                         "fanin_support", "depth", "fout"]].mean().round(4).to_dict()
          if "fout" in d.columns else
          d[["sp", "toggle_rate", "cc0", "cc1", "co", "influence_in",
             "fanin_support", "depth"]].mean().round(4).to_dict())

base = res.get("orig")
if base is not None:
    print("\n=== 各特征在 orig 与各变体之间的分位数漂移（0=完全不变）===")
    for tag, d in res.items():
        if tag == "orig":
            continue
        drift = {}
        for f in NF.FEATS:
            if f not in base.columns or f not in d.columns:
                continue
            q = [0.05, 0.25, 0.5, 0.75, 0.95]
            a = base[f].quantile(q).values
            b = d[f].quantile(q).values
            span = max(base[f].quantile(0.75) - base[f].quantile(0.25), 1e-6)
            drift[f] = float(abs(a - b).mean() / span)
        s = pd.Series(drift).sort_values()
        print(f"[{tag}] 最稳: {list(s.index[:5])}")
        print(f"       最漂: {list(s.index[-4:])}")
