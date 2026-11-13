# -*- coding: utf-8 -*-
"""_fix_views_meta.py —— 只重建 folds/<fold>/views_meta.csv（不重跑数据管线）。

用途：`build_hosts_fold.py` 早期把 140 个改写视图的 `kind` 一律写成 "trojan"，
导致对照派生的 80 个改写视图被错标。本脚本按 src_view 重新派生 kind，
并从已有 `generate_trans/hosts/{instances,rewrite_variants}.csv` 重建该表。

用法：
  python phase2/_fix_views_meta.py --fold-dir generate_trans/folds/hosts_gamma
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold-dir", type=Path, default=ROOT / "generate_trans" / "folds" / "hosts_gamma")
    ap.add_argument("--hosts-root", type=Path, default=ROOT / "generate_trans" / "hosts")
    args = ap.parse_args()
    rwv = pd.read_csv(args.hosts_root / "rewrite_variants.csv")
    inst = pd.read_csv(args.hosts_root / "instances.csv")
    ctl = inst[inst["kind"] == "control"]
    rows = []
    for r in rwv.itertuples():
        short = r.src_view.split("__")[1].split("_d1")[0]
        tro = int(short.startswith("inj"))
        rows.append({"view": r.rw_view, "host": r.host, "src_view": r.src_view,
                     "inst_id": short, "kind": ("trojan" if tro else "control"),
                     "ctl_type": "", "op": r.mode, "label1": tro, "seed": 42})
    for r in ctl.itertuples():
        short = r.view.split("__")[1].split("_d1")[0]
        rows.append({"view": r.view, "host": r.host, "src_view": r.view,
                     "inst_id": short, "kind": "control",
                     "ctl_type": (r.ctl_type or ""), "op": "inject",
                     "label1": 0, "seed": 42})
    d = pd.DataFrame(rows)
    out = args.fold_dir / "views_meta.csv"
    d.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"[OK] {out}（{len(d)} 行）")
    print(d.groupby(["kind", "op"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
