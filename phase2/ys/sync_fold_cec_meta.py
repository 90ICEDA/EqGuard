#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
sync_fold_cec_meta.py — 把 fold 的 `view_manifest_cec.csv`（统一 CEC 的最新结论）
同步进 `data/processed/dataset_meta.json`，让训练/评测读到的 CEC 状态不再过期。

背景：`process_pt2.py` 在 prep 阶段把 CEC 状态写进 `dataset_meta.json`，
之后重跑 CEC 不会自动刷新 → 会出现“CEC 明明 PASS，评测却显示 0/70”的假象。

做的事：
  1. per_view[*].cec_status ← view_manifest_cec.csv 的 cec_status（缺失 → UNKNOWN）
  2. views_train/val/test ← views.json（同步被剔除的视图）
  3. n_views / n_train_views / n_val_views / n_test_views / cec_all_pass 重算
  4. 打印分布

用法：
    python phase2/ys/sync_fold_cec_meta.py --fold generate_trans/folds/hosts_bt3
"""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=Path, required=True)
    ap.add_argument("--meta", type=str, default="data/processed/dataset_meta.json")
    ap.add_argument("--cec", type=str, default="view_manifest_cec.csv")
    ap.add_argument("--views", type=str, default="views.json")
    args = ap.parse_args()

    fold = args.fold
    meta_path = fold / args.meta
    cec_path = fold / args.cec
    views_path = fold / args.views
    for p in (meta_path, cec_path, views_path):
        if not p.exists():
            print(f"[ERROR] 找不到 {p}")
            return 1

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    with open(cec_path, "r", encoding="utf-8-sig", newline="") as f:
        cec = {str(r["view_name"]): (str(r.get("cec_status") or "UNKNOWN")) for r in csv.DictReader(f)}
    views = json.loads(views_path.read_text(encoding="utf-8"))

    per_view = meta.setdefault("per_view", {})
    changed = 0
    for name, rec in per_view.items():
        new = cec.get(name, "UNKNOWN")
        if rec.get("cec_status") != new:
            rec["cec_status"] = new
            changed += 1
    # 补齐 CEC 有、meta 没有的视图（理论上不会发生）
    for name, st in cec.items():
        if name not in per_view:
            per_view[name] = {"cec_status": st, "role": "unknown"}
            changed += 1

    for key, role in (("views_train", "train"), ("views_val", "val"), ("views_test", "test")):
        if key in views:
            meta[key] = list(views[key])
    meta["n_views"] = len(per_view)
    meta["n_train_views"] = len(meta.get("views_train", []))
    meta["n_val_views"] = len(meta.get("views_val", []))
    meta["n_test_views"] = len(meta.get("views_test", []))

    test_views = meta.get("views_test", [])
    meta["cec_all_pass"] = bool(test_views) and all(
        per_view.get(v, {}).get("cec_status") == "PASS" for v in test_views
    )
    meta["cec_all_pass_all"] = all(r.get("cec_status") == "PASS" for r in per_view.values())

    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    cnt = Counter(r.get("cec_status") for r in per_view.values())
    test_cnt = Counter(per_view.get(v, {}).get("cec_status") for v in test_views)
    print(f"[OK] {meta_path}  更新 {changed} 条")
    print(f"[CEC] 全 fold: {dict(cnt)}")
    print(f"[CEC] test split ({len(test_views)}): {dict(test_cnt)}  cec_all_pass={meta['cec_all_pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
