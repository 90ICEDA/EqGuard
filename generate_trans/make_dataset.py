#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
make_dataset.py — P0：把选定视图物化成独立工作目录，并在其中构建图数据集

  1) materialize：<work-dir>/{orig,trans,mappings} + 库/查找表（视图用硬链接省磁盘）
  2) run parser2（label-free raw provenance + 独立 label transport）
  3) 汇总 <work-dir>/dataset_manifest.json（视图清单/图规模/provenance 统计/每个视图的 CEC 状态）

用法：
  python make_dataset.py --matrix-root matrix --orig-dir orig --work-dir /tmp/ds1 \
      --views rs232t1000__decomp_d1_s42,rs232t1000__resub_d1_s42 [--run-parser --parser <parser2.py>]
  python make_dataset.py ... --fold-json matrix/split_specs/single_to_composed_d2.json --fold-name single_to_composed_d2
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


def link_or_copy(src: Path, dst: Path) -> str:
    if dst.exists():
        return "exists"
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def load_view_keys(path: Path) -> List[str]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        keys: List[str] = []
        for key in ("views", "train_views", "test_views"):
            keys.extend(payload.get(key, []) or [])
        for fold in payload.get("folds", []) or []:
            keys.extend(fold.get("train_views", []) or [])
            keys.extend(fold.get("test_views", []) or [])
        return sorted(set(keys))
    keys = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            keys.append(s)
    return sorted(set(keys))


def collect_views(args) -> List[str]:
    views: List[str] = []
    if args.views:
        views += [v.strip() for v in args.views.split(",") if v.strip()]
    if args.views_list:
        views += load_view_keys(Path(args.views_list))
    if args.fold_json:
        payload = json.loads(Path(args.fold_json).read_text(encoding="utf-8"))
        if args.fold_name:
            hit = None
            for fold in payload.get("folds", []):
                if fold.get("fold") == args.fold_name:
                    hit = fold
                    break
            if hit is None:
                raise SystemExit(f"[ERROR] fold {args.fold_name} 不在 {args.fold_json}")
            views += (hit.get("train_views", []) or []) + (hit.get("test_views", []) or [])
        else:
            for fold in payload.get("folds", []):
                views += (fold.get("train_views", []) or []) + (fold.get("test_views", []) or [])
    if args.circuits:
        keep = tuple(c.strip() for c in args.circuits.split(",") if c.strip())
        views = [v for v in views if v.startswith(keep)]
    return sorted(set(views))


def main() -> int:
    ap = argparse.ArgumentParser(description="P0：视图物化 + 数据集构建编排")
    ap.add_argument("--matrix-root", type=Path, required=True, help="generate_trans/matrix")
    ap.add_argument("--orig-dir", type=Path, required=True, help="原始网表目录（orig/）")
    ap.add_argument("--work-dir", type=Path, required=True, help="工作目录（创建/复用）")
    ap.add_argument("--views", type=str, default="", help="逗号分隔的视图名")
    ap.add_argument("--views-list", type=Path, default=None)
    ap.add_argument("--fold-json", type=Path, default=None)
    ap.add_argument("--fold-name", type=str, default="")
    ap.add_argument("--circuits", type=str, default="",
                    help="只保留这些电路的视图（逗号分隔前缀，如 rs232；默认全部）")
    ap.add_argument("--build-pt", action="store_true",
                    help="parser2 跑完后继续调用 process_pt2.py 生成 orig_graph.pt/trans_graph.pt")
    ap.add_argument("--trans-label", choices=["transported", "name"], default="transported",
                    help="trans 标签来源（透传给 process_pt2.py）")
    ap.add_argument("--assets-dir", type=Path, default=None,
                    help="含 verilog_lib.v / gatelookup_recommended.json / gate_full_to_simplified_mapping.json 的目录")
    ap.add_argument("--run-parser", action="store_true", help="物化后运行 parser2")
    ap.add_argument("--parser", type=Path, default=None, help="parser2.py 路径（--run-parser 时必填）")
    ap.add_argument("--python", type=str, default="",
                    help="运行 parser2 的解释器（默认：当前解释器 sys.executable；"
                         "数据准备是纯 Python，Windows/ginvenv 里跑最省事，yosys 才需要 Linux）")
    ap.add_argument("--cycle-mode", choices=["none", "contract"], default="none",
                    help="组合环处理：contract=先在触发器输出切断时序边界，再对 SCC 收缩后算拓扑特征并回填"
                         "（旧 33 维逐字节不变 + 追加 in_cycle/scc_size 等 6 维 = 39 维）")
    ap.add_argument("--require-label-match", action="store_true",
                    help="血缘建立时要求两侧 Trojan label 相同（**旧的 label-gated 行为**，"
                         "仅用于『标签是否参与血缘』的对照实验；默认 label-free）")
    args = ap.parse_args()

    views = collect_views(args)
    if not views:
        print("[ERROR] 没有选定任何视图（--views / --views-list / --fold-json）")
        return 1

    matrix = args.matrix_root.resolve()
    orig_dir = args.orig_dir.resolve()
    work = args.work_dir.resolve()
    if args.assets_dir:
        assets = args.assets_dir.resolve()
    else:
        candidates = [orig_dir.parent / "data" / "verilog_data",
                      orig_dir.parent.parent / "data" / "verilog_data",
                      orig_dir.parent]
        assets = next((c for c in candidates if (c / "verilog_lib.v").exists()), candidates[0])
    print(f"[INFO] assets-dir = {assets}")

    (work / "orig").mkdir(parents=True, exist_ok=True)
    (work / "trans").mkdir(parents=True, exist_ok=True)
    (work / "mappings").mkdir(parents=True, exist_ok=True)
    (work / "logs").mkdir(parents=True, exist_ok=True)
    # parser2 会向 ./data/for_train 与 ./data/not_for_train 写中间产物
    (work / "data" / "for_train").mkdir(parents=True, exist_ok=True)
    (work / "data" / "not_for_train").mkdir(parents=True, exist_ok=True)

    used_circuits, missing = set(), []
    link_modes: Dict[str, int] = {}
    for v in views:
        cand = matrix / "verilog" / f"{v}.v"
        if not cand.exists():
            missing.append(v)
            continue
        mode = link_or_copy(cand, work / "trans" / cand.name)
        link_modes[mode] = link_modes.get(mode, 0) + 1
        mp = matrix / "mappings" / f"{v}.json"
        if mp.exists():
            link_or_copy(mp, work / "mappings" / mp.name)
        stem = v.split("__")[0]
        used_circuits.add(stem)
        g = orig_dir / f"{stem}.v"
        if g.exists():
            link_or_copy(g, work / "orig" / g.name)
        else:
            missing.append(f"orig:{stem}")

    for asset in ["verilog_lib.v", "gatelookup_recommended.json",
                  "gate_full_to_simplified_mapping.json"]:
        src = assets / asset
        if src.exists():
            shutil.copy2(src, work / asset)
        else:
            print(f"[WARN] 缺少资产 {src}")

    (work / "views.txt").write_text("\n".join(views) + "\n", encoding="utf-8")
    print(f"[OK] 物化 {len(views) - len(missing)} 个视图 -> {work}")
    print(f"     电路 {sorted(used_circuits)}｜trans={len(list((work / 'trans').glob('*.v')))} "
          f"orig={len(list((work / 'orig').glob('*.v')))} "
          f"mappings={len(list((work / 'mappings').glob('*.json')))}")
    if missing:
        print(f"[WARN] 缺失 {len(missing)}: {missing[:5]}")

    parser_stats: Dict[str, object] = {}
    if args.run_parser:
        if not args.parser:
            print("[ERROR] --run-parser 需要 --parser <parser2.py>")
            return 1
        log = work / "logs" / "parser2.log"
        py = args.python.strip() or sys.executable or "python3"
        cmd = [py, str(args.parser.resolve()),
               "--out-root", "./data/for_train", "--skip-debug",
               "--cycle-mode", str(args.cycle_mode)]
        if args.require_label_match:
            cmd.append("--require-label-match")
        print(f"[INFO] parser2 解释器: {py}")
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"      # 让中文日志可读（否则 GBK 写入 UTF-8 文件会乱码）
        with open(log, "w", encoding="utf-8") as lf:
            rc = subprocess.call(cmd, cwd=str(work), stdout=lf, stderr=subprocess.STDOUT, env=env)
        print(f"[{'OK' if rc == 0 else 'FAIL'}] parser2 rc={rc}，日志 {log}")
        if rc != 0:
            return rc
        for name in ("provenance_stats.json", "label_transport.json"):
            p = work / "data" / "for_train" / name
            if p.exists():
                parser_stats[name] = json.loads(p.read_text(encoding="utf-8"))

    pt_info: Dict[str, object] = {}
    if args.build_pt:
        if not args.fold_json:
            print("[ERROR] --build-pt 需要 --fold-json（matrix/folds/<fold>/views.json）")
            return 1
        pt2 = Path(__file__).resolve().parent.parent / "process_pt2.py"
        cmd = [sys.executable or "python", str(pt2),
               "--work-dir", str(work), "--fold-json", str(Path(args.fold_json).resolve()),
               "--trans-label", str(args.trans_label)]
        if args.circuits:
            cmd += ["--circuits", str(args.circuits)]
        if args.matrix_root:
            cmd += ["--matrix-root", str(Path(args.matrix_root).resolve())]
        print(f"[INFO] 构建 .pt: {pt2.name} ...")
        rc = subprocess.call(cmd, cwd=str(Path(__file__).resolve().parent.parent))
        print(f"[{'OK' if rc == 0 else 'FAIL'}] process_pt2 rc={rc}")
        if rc != 0:
            return rc
        meta_path = work / "data" / "processed" / "dataset_meta.json"
        if meta_path.exists():
            pt_info = json.loads(meta_path.read_text(encoding="utf-8"))

    target_views = set(views)
    cec_status: Dict[str, str] = {}
    vm = matrix / "view_manifest_cec.csv"
    if vm.exists():
        with open(vm, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if str(r.get("view_name")) in target_views:
                    cec_status[str(r["view_name"])] = str(r.get("cec_status", ""))

    for_dir: Dict[str, object] = {}
    df = work / "data" / "for_train"
    if df.exists():
        for name in ["feats_orig.npy", "feats_trans.npy", "adj_full_orig.npz",
                     "adj_full_trans.npz", "alignment.json",
                     "class_map_trans_transported.json"]:
            p = df / name
            for_dir[name] = p.stat().st_size if p.exists() else None

    manifest = {
        "work_dir": str(work),
        "n_views": len(views),
        "views": views,
        "circuits": sorted(used_circuits),
        "missing": missing,
        "link_modes": link_modes,
        "n_views_cec_pass": sum(1 for v in views if cec_status.get(v) == "PASS"),
        "view_cec_status": cec_status,
        "files": for_dir,
        "parser_stats": parser_stats,
        "pt": pt_info,
    }
    (work / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] dataset_manifest.json -> {work / 'dataset_manifest.json'}")
    print(f"     CEC PASS {manifest['n_views_cec_pass']}/{len(views)}｜图文件 "
          f"{json.dumps(for_dir, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

