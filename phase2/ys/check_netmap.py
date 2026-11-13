"""check_netmap.py —— **映射自检** ✓（改 `resolve` 前后必须过这一关 ✗）。

对每个 (host, inst_a, recipe_a) 视图，从 `node_pairs_sat_node.csv` 取前 N 个 proved 网名，
分别用 **旧口径**（`satrel_node_feats_sat.resolve`，只直查）与 **新口径**（`netmap.NetMapper`
= 直查 + assign 追踪 + 网→驱动单元）算命中率 ✓。

门槛 ✓：`--min-hit 0.85`（新口径每个视图都要 ≥85%，否则退出码 2 ✗ 不进训练 ✓）。

用法 ✓：
    ginvenv\\Scripts\\python.exe -X utf8 phase2/ys/check_netmap.py --limit 400
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import satrel_node_feats_sat as NF      # noqa: E402
import netmap as NM                     # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt-dir", type=Path,
                    default=NF.ROOT / "generate_trans/folds/hosts_bt31/data/processed")
    ap.add_argument("--work", type=Path,
                    default=NF.ROOT / "generate_trans/folds/hosts_bt31")
    ap.add_argument("--views-dir", type=Path, default=None,
                    help="默认 <work>/trans ✓")
    ap.add_argument("--tables", type=Path, default=NF.T)
    ap.add_argument("--limit", type=int, default=400, help="每个视图取前 N 个网名 ✓")
    ap.add_argument("--min-hit", type=float, default=0.85)
    ap.add_argument("--no-json", action="store_true", help="只用 .v 正则（不用 yosys JSON ⚠️）")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    names, fid = NF.load_names(a.pt_dir, a.work)
    views = sorted(set(fid))
    exact, basem = NF.build_maps(names, fid, views)
    vdir = a.views_dir or (a.work / "trans")
    mapper = NM.NetMapper(exact, basem, vdir,
                          struct_dirs=NM.default_struct_dirs(NF.BASE),
                          use_json=not a.no_json, verbose=a.verbose)
    print(f"[in] views={len(views)}｜views_dir={vdir}｜json={not a.no_json}")

    p = a.tables / "node_pairs_sat_node.csv"
    d = pd.read_csv(p, encoding="utf-8-sig").fillna("")
    d = d[d["status"].astype(str) == "proved"]
    if d.empty:
        raise SystemExit("[ERROR] 没有 proved 行 ✗")
    d["recipe_a"] = d["recipe_a"].map(lambda x: x if str(x).startswith("ys_") else f"ys_{x}")

    rows = []
    for (host, inst, rcp), g in d.groupby(["host", "inst_a", "recipe_a"]):
        view = f"{host}__{inst}_d1_s42__{rcp}"
        if view not in exact:
            continue
        nets = list(dict.fromkeys(g["net_a"].astype(str).tolist()))[: a.limit]
        if not nets:
            continue
        old = sum(1 for n in nets if NF.resolve(exact[view], basem[view], n))
        new = sum(1 for n in nets if mapper.ids(view, n))
        rows.append(dict(view=view, nets=len(nets), old=old, new=new,
                         old_rate=round(old / len(nets), 4),
                         new_rate=round(new / len(nets), 4)))
    if not rows:
        raise SystemExit("[ERROR] 没有可测视图 ✗（检查 views_dir ✓）")
    t = pd.DataFrame(rows).sort_values("new_rate")
    print(t.to_string(index=False))
    print(f"\n[sum] 视图 {len(t)}｜旧口径平均命中 {t['old_rate'].mean():.3f}"
          f"｜新口径平均命中 {t['new_rate'].mean():.3f}"
          f"｜新口径最低 {t['new_rate'].min():.3f}")
    bad = t[t["new_rate"] < a.min_hit]
    if len(bad):
        print(f"\n[WARN] {len(bad)} 个视图低于门槛 {a.min_hit:.2f} ✗")
        return 2
    print(f"\n[OK] 全部视图 ≥ {a.min_hit:.2f} ✓（可以重建特征 ✓）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
