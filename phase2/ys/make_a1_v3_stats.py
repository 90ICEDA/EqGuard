#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
make_a1_v3_stats.py — A1 的 **fold v3 版**统计（替代 A1 说明里 v2/hosts_beta2 的数字）。

A1（10-15）统计的是 `folds/hosts_beta2`（339 视图）+ `hosts_bt2`，
本脚本按**当前 fold v3**（`generate_trans/folds/hosts_bt3`，417 可用视图）重算：

  · 每个视图：图节点数（= 实例数，见 A1 §2）、正标签节点数、**传输覆盖**
    （= 该视图里出现在 `class_map_trans_transported.json` 的节点数 / 节点数）、
    CEC 状态、算子、batch；
  · 每个算子聚合：视图数、节点中位数、相对源视图的节点比、
    传输覆盖（合计口径 ✓）、有正标签视图数、正节点数、CEC 通过数；
  · 源（orig）侧：每个源视图的节点数与金标准正节点数（`class_map_orig.json`）。

说明：`class_map_trans_transported.json` / `metadata_trans.json.file_ids` 都是**全局**索引，
按 `file_ids[i] == view` 归到视图 ✓（与 A1 的 `t_idx` 口径一致 ✓）。

用法：
    python phase2/ys/make_a1_v3_stats.py
    python phase2/ys/make_a1_v3_stats.py --fold generate_trans/folds/hosts_bt3 --out-dir <dir>
"""

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FOLD_DEFAULT = ROOT / "generate_trans" / "folds" / "hosts_bt3"
OUT_DEFAULT = ROOT / "10.15" / "01_数据与标签" / "A1_变换统计" / "tables"


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def per_view_counts(meta_path: Path, class_map_path: Path):
    """→ {view: [n_nodes, n_labeled, n_pos]}"""
    meta = load_json(meta_path)
    fids = meta["file_ids"] if isinstance(meta, dict) else meta
    cm = load_json(class_map_path)
    out = defaultdict(lambda: [0, 0, 0])
    for i, v in enumerate(fids):
        rec = out[str(v)]
        rec[0] += 1
        lab = cm.get(str(i))
        if lab is not None:
            rec[1] += 1
            if int(lab) == 1:
                rec[2] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=Path, default=FOLD_DEFAULT)
    ap.add_argument("--out-dir", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args()
    fold = args.fold

    ft = fold / "data" / "for_train"
    dm = load_json(fold / "data" / "processed" / "dataset_meta.json")
    per_view = dm.get("per_view", {})

    trans = per_view_counts(ft / "metadata_trans.json", ft / "class_map_trans_transported.json")
    orig = per_view_counts(ft / "metadata_orig.json", ft / "class_map_orig.json")

    # 视图 → 源视图（fold 的 views_meta.csv）
    src_of = {}
    meta_csv = fold / "views_meta.csv"
    if meta_csv.exists():
        with open(meta_csv, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                src_of[str(r["view"])] = str(r.get("src_view") or "")

    rows = []
    for v, rec in per_view.items():
        op = str(rec.get("operators") or "?")
        n_t, n_lab_t, n_pos_t = trans.get(v, [0, 0, 0])
        src = src_of.get(v, "")
        n_o, _, n_pos_o = orig.get(src, [0, 0, 0])
        rows.append({
            "view": v,
            "host": rec.get("file_stem", ""),
            "circuit": rec.get("circuit", ""),
            "op": op,
            "batch": rec.get("batch", ""),
            "role": rec.get("role", ""),
            "nodes_trans": int(rec.get("nodes") or n_t),
            "nodes_orig": n_o,
            "node_ratio": round(n_t / n_o, 4) if n_o else "",
            "transported_nodes": n_lab_t,
            "transported_cover": round(n_lab_t / n_t, 4) if n_t else "",
            "pos_trans": n_pos_t,
            "pos_orig": n_pos_o,
            "cec_status": rec.get("cec_status", "UNKNOWN"),
            "src_view": src,
        })

    rows.sort(key=lambda r: (r["op"], r["view"]))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with open(args.out_dir / "a1_v3_views.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    by = defaultdict(list)
    for r in rows:
        by[r["op"]].append(r)
    agg = []
    for op in sorted(by):
        g = by[op]
        nodes = [r["nodes_trans"] for r in g]
        ratios = [r["node_ratio"] for r in g if r["node_ratio"] != ""]
        tn = sum(r["transported_nodes"] for r in g)
        nn = sum(r["nodes_trans"] for r in g)
        agg.append({
            "op": op,
            "views": len(g),
            "nodes_median": statistics.median(nodes) if nodes else 0,
            "node_ratio_median": round(statistics.median(ratios), 4) if ratios else "",
            "transported_cover": round(tn / nn, 4) if nn else "",
            "views_with_pos": sum(1 for r in g if r["pos_trans"] > 0),
            "pos_nodes": sum(r["pos_trans"] for r in g),
            "cec_pass": sum(1 for r in g if r["cec_status"] == "PASS"),
        })
    with open(args.out_dir / "a1_v3_by_op.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(agg[0]))
        w.writeheader()
        w.writerows(agg)

    print("op".ljust(14), "views".rjust(5), "nodes_med".rjust(9), "ratio".rjust(7),
          "cover".rjust(7), "with_pos".rjust(8), "pos".rjust(5), "cec_pass".rjust(8))
    for a in agg:
        print(str(a["op"]).ljust(14), str(a["views"]).rjust(5), str(a["nodes_median"]).rjust(9),
              str(a["node_ratio_median"]).rjust(7), str(a["transported_cover"]).rjust(7),
              str(a["views_with_pos"]).rjust(8), str(a["pos_nodes"]).rjust(5),
              str(a["cec_pass"]).rjust(8))
    print(f"\n[TOTAL] views={len(rows)} pos_views={sum(1 for r in rows if r['pos_trans'] > 0)} "
          f"pos={sum(r['pos_trans'] for r in rows)} cec={dict(Counter(r['cec_status'] for r in rows))}")
    print(f"[OUT] {args.out_dir / 'a1_v3_views.csv'} / a1_v3_by_op.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
