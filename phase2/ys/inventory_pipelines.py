#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
inventory_pipelines.py — 盘点各日期快照目录里“流水线脚本”的版本（md5 + mtime）。

目的：回答“某天的结果是用哪版脚本跑出来的”，避免训练/转网表/CEC 用错版本。

用法：
    python phase2/ys/inventory_pipelines.py \
        --out 10.15/99_共用资产/运行登记/pipeline_inventory.csv

输出列：snapshot, repo_root, script, rel_path, md5_10, size, mtime
"""

import argparse
import csv
import hashlib
import os
from pathlib import Path

# 关心的流水线脚本（相对 repo 根）
KEY_SCRIPTS = [
    "train_test2.3.py",
    "train_test2.2.py",
    "train_test2.py",
    "config.yaml",
    "data/verilog_data/parser2.py",
    "phase2/inject_trojan.py",
    "phase2/build_hosts_fold.py",
    "phase2/netlist_lib.py",
    "generate_trans/cec/matrix_cec.py",
    "generate_trans/cec/direct_cec.py",
    "generate_trans/cec/join_cec.py",
    "generate_trans/cec/README_CEC.md",
]
# phase2/ys 下按名字前缀收（版本差异最常发生的地方）
YS_GLOBS = [
    "assign_to_gates.py",
    "make_inst_alignment.py",
    "make_name_alignment.py",
    "make_a1_transform_stats.py",
    "make_a2_anchors.py",
    "make_a4_views.py",
    "make_a5_manifest.py",
    "build_fold_v3.py",
    "build_fold_v2.py",
    "register_into_fold.py",
    "keep_ablation.py",
    "meas_a3_inst_ident.py",
    "a4_benign_cec.py",
]


def md5_10(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:10]


def find_repo_roots(base: Path):
    """快照目录 → 其中的 GIN_train 仓库根（若本身就是仓库则用自身）。"""
    if (base / "phase2").is_dir() and (base / "generate_trans").is_dir():
        return [base]
    roots = []
    for child in sorted(base.iterdir()):
        if child.is_dir() and (child / "phase2").is_dir():
            roots.append(child)
        elif child.is_dir():
            roots += find_repo_roots(child)
    return roots


def collect(snapshot: str, repo: Path):
    rows = []
    for rel in KEY_SCRIPTS + [f"phase2/ys/{n}" for n in YS_GLOBS]:
        p = repo / rel
        if not p.exists():
            rows.append({"snapshot": snapshot, "repo_root": str(repo), "script": p.name,
                         "rel_path": rel, "md5_10": "MISSING", "size": "", "mtime": ""})
            continue
        st = p.stat()
        rows.append({
            "snapshot": snapshot, "repo_root": str(repo), "script": p.name, "rel_path": rel,
            "md5_10": md5_10(p), "size": st.st_size,
            "mtime": __import__("datetime").datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desk", type=Path, default=Path(r"C:\Users\91344\Desktop"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    snapshots = []
    # 1) GIN训练/<date>（历史快照）
    hist = args.desk / "GIN训练"
    if hist.is_dir():
        for d in sorted(hist.iterdir()):
            if d.is_dir() and d.name[0].isdigit():
                snapshots.append((f"GIN训练/{d.name}", d))
    # 2) GraphSAINT/GIN_train 工作区 + 其日期夹
    work = args.desk / "GraphSAINT" / "GIN_train"
    if work.is_dir():
        snapshots.append(("GraphSAINT/GIN_train(working)", work))
        for d in sorted(work.iterdir()):
            if d.is_dir() and d.name[:2].isdigit() and "." in d.name[:5]:
                snapshots.append((f"GraphSAINT/GIN_train/{d.name}", d))

    all_rows = []
    for name, base in snapshots:
        roots = find_repo_roots(base)
        if not roots:
            all_rows.append({"snapshot": name, "repo_root": str(base), "script": "(no repo)",
                             "rel_path": "", "md5_10": "", "size": "", "mtime": ""})
            continue
        for repo in roots:
            all_rows += collect(name, repo)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["snapshot", "repo_root", "script", "rel_path", "md5_10", "size", "mtime"]
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in all_rows:
            w.writerow(r)
    print(f"[OK] {args.out}  {len(all_rows)} 行  快照 {len(snapshots)} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
