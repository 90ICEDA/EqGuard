#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
make_fold_cec_manifest.py — 把 fold 布局（trans/ + orig/ + views_meta.csv）
转成统一 CEC 驱动 `generate_trans/cec/matrix_cec.py` 需要的 view_manifest.csv。

fold 布局（generate_trans/folds/hosts_bt3）:
    orig/<src_view>.v           每个“源视图”一个 golden（= 木马注入后的宿主网表）
    trans/<view>.v              每个训练视图一个 candidate（keep × yosys pass 的产物）
    views_meta.csv              view,host,src_view,inst_id,kind,family,op,label1,label_usable,batch

输出:
    <fold>/view_manifest.csv    view_name,view_file,src_verilog,circuit,host,batch,op,src_view
    —— matrix_cec.py 只依赖其中 view_name / view_file / src_verilog 三列
       （candidate = --cand-dir/view_file，golden = --orig-dir/src_verilog）

用法:
    python make_fold_cec_manifest.py --fold generate_trans/folds/hosts_bt3
"""

import argparse
import csv
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=Path, required=True)
    ap.add_argument("--meta", type=str, default="views_meta.csv")
    ap.add_argument("--out", type=str, default="view_manifest.csv")
    args = ap.parse_args()

    fold = args.fold
    meta_path = fold / args.meta
    if not meta_path.exists():
        print(f"[ERROR] 找不到 {meta_path}")
        return 1

    with open(meta_path, "r", encoding="utf-8-sig", newline="") as f:
        meta = [dict(r) for r in csv.DictReader(f)]

    rows, missing = [], []
    for r in meta:
        view = str(r["view"]).strip()
        src_view = str(r.get("src_view") or view).strip()
        cand = fold / "trans" / f"{view}.v"
        gold = fold / "orig" / f"{src_view}.v"
        if not cand.exists() or not gold.exists():
            missing.append((view, cand.exists(), gold.exists()))
            continue
        rows.append({
            "view_name": view,
            "view_file": f"{view}.v",
            "src_verilog": f"{src_view}.v",
            "circuit": r.get("host", ""),
            "host": r.get("host", ""),
            "batch": r.get("batch", ""),
            "op": r.get("op", ""),
            "src_view": src_view,
        })

    out_path = fold / args.out
    fields = ["view_name", "view_file", "src_verilog", "circuit", "host", "batch", "op", "src_view"]
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"[OK] {out_path}  {len(rows)} 行")
    if missing:
        print(f"[WARN] {len(missing)} 个视图缺文件（前 5 个）: {missing[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
