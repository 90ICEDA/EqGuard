#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
merge_fold_cec.py — 把统一 CEC 驱动（generate_trans/cec/matrix_cec.py）在
fold 布局上的产出 `cec/cec_results.csv` 并回 fold 的 `view_manifest_cec.csv`。

列（向后兼容旧的 view_name,cec_status,host,batch，并追加证据列）：
    view_name, cec_status, host, batch, op, src_view,
    proven, unproven, total_equiv, runtime_sec, note

用法：
    python phase2/ys/merge_fold_cec.py --fold generate_trans/folds/hosts_bt3
"""

import argparse
import csv
from pathlib import Path

OUT_FIELDS = [
    "view_name", "cec_status", "host", "batch", "op", "src_view",
    "proven", "unproven", "total_equiv", "runtime_sec", "note",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=Path, required=True)
    ap.add_argument("--results", type=str, default="cec/cec_results.csv")
    ap.add_argument("--manifest", type=str, default="view_manifest.csv")
    ap.add_argument("--out", type=str, default="view_manifest_cec.csv")
    args = ap.parse_args()

    fold = args.fold
    res_path = fold / args.results
    man_path = fold / args.manifest
    if not res_path.exists():
        print(f"[ERROR] 找不到 CEC 结果 {res_path}（先跑 matrix_cec.py）")
        return 1

    with open(man_path, "r", encoding="utf-8-sig", newline="") as f:
        man = {str(r["view_name"]): r for r in csv.DictReader(f)}
    with open(res_path, "r", encoding="utf-8-sig", newline="") as f:
        results = {str(r["view_name"]): r for r in csv.DictReader(f)}

    rows = []
    for view_name, m in man.items():
        r = results.get(view_name, {})
        rows.append({
            "view_name": view_name,
            "cec_status": (r.get("status") or "UNKNOWN"),
            "host": m.get("host", ""),
            "batch": m.get("batch", ""),
            "op": m.get("op", ""),
            "src_view": m.get("src_view", ""),
            "proven": r.get("proven", ""),
            "unproven": r.get("unproven", ""),
            "total_equiv": r.get("total_equiv", ""),
            "runtime_sec": r.get("runtime_sec", ""),
            "note": r.get("note", ""),
        })

    out_path = fold / args.out
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    from collections import Counter
    cnt = Counter(r["cec_status"] for r in rows)
    print(f"[OK] {out_path}  {len(rows)} 行  {dict(cnt)}")
    bad = [r["view_name"] for r in rows if r["cec_status"] != "PASS"]
    if bad:
        print(f"[WARN] 非 PASS {len(bad)} 个（前 5）: {bad[:5]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
