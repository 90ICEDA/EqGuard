# -*- coding: utf-8 -*-
"""汇总 hosts_gamma 上的结果（M0 = G4 配置；M1 = +对抗），按 (method, mode, seed)。"""
import glob
import re
from pathlib import Path

import pandas as pd

KEYS = ["AP", "Anchor_AP_Orig", "Anchor_AP_Trans", "Recall@1%", "Recall@5%",
        "Paired_MAE", "Flip_Rate", "Spearman_Corr"]
rows = []
for d in sorted(glob.glob("results/hosts_gamma_seed*mode4_*")):
    p = Path(d) / "circuit_level_summary.csv"
    if not p.exists():
        continue
    m = pd.read_csv(p)
    mac = m[m["Circuit"] == "MACRO_MEAN"]
    if not len(mac):
        continue
    ms = re.search(r"seed(\d+)", d)
    mode = "LOCO" if "_loco_" in d else "fold"
    mm = re.search(r"_(M\d)_", d)
    method = mm.group(1) if mm else "?"
    r = {"method": method, "mode": mode, "seed": int(ms.group(1))}
    for k in KEYS:
        if k in mac.columns:
            r[k] = float(mac.iloc[0][k])
    rows.append(r)
D = pd.DataFrame(rows)
if D.empty:
    print("没有结果")
    raise SystemExit(0)
D = D.drop_duplicates(subset=["method", "mode", "seed"]).sort_values(["method", "mode", "seed"])
use = [k for k in KEYS if k in D.columns]
print("=== 逐 run ===")
print(D[["method", "mode", "seed"] + use].round(4).to_string(index=False))
print()
print("=== 聚合（mean ± std）===")
g = D.groupby(["method", "mode"])[use].agg(["mean", "std"])
out = pd.DataFrame({k: (g[k]["mean"].round(4).astype(str) + " ± "
                        + g[k]["std"].round(4).astype(str)) for k in use})
out["n_seed"] = D.groupby(["method", "mode"]).size()
print(out.to_string())
print()
piv = D.groupby(["method", "mode"])[use].mean()
for me in sorted(D.method.unique()):
    if ("%s" % me, "fold") in piv.index and (me, "LOCO") in piv.index:
        print(f"=== {me}: LOCO − fold ===")
        print((piv.loc[(me, "LOCO")] - piv.loc[(me, "fold")]).round(4).to_string())
print()
if "M0" in set(D.method) and "M1" in set(D.method):
    print("=== M1 − M0（同模式）===")
    for md in ("fold", "LOCO"):
        try:
            print(f"  [{md}]", (piv.loc[("M1", md)] - piv.loc[("M0", md)]).round(4).to_dict())
        except KeyError:
            pass

