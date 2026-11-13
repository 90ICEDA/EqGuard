#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_fold_datasets.py — 批量物化 fold 视图 + parser2 建图 + 生成 fold .pt

用法：
  # 默认：除 single_to_composed_d2 之外的全部 fold
  python build_fold_datasets.py
  python build_fold_datasets.py --folds single_to_composed_d3,heldout_single_decomp
  python build_fold_datasets.py --skip-existing --cycle-mode contract
输出：
  generate_trans/folds/<fold>/{orig,trans,mappings,data/processed/*.pt}
  generate_trans/folds/_build_<fold>.log
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

CUR = Path(__file__).resolve().parent            # GIN_train/
GT = CUR / "generate_trans"

ALL_FOLDS = [
    "single_to_composed_d2", "single_to_composed_d3",
    "heldout_single_decomp", "heldout_single_balance",
    "heldout_single_refactor", "heldout_single_resub",
    "heldout_composed_decomp", "heldout_composed_balance",
    "heldout_composed_refactor", "heldout_composed_resub",
]


def main():
    ap = argparse.ArgumentParser(description="批量构建 fold 数据集")
    ap.add_argument("--folds", type=str, default="",
                    help="逗号分隔；默认 = 全部 fold 去掉 --exclude")
    ap.add_argument("--exclude", type=str, default="single_to_composed_d2")
    ap.add_argument("--matrix-root", type=Path, default=GT / "matrix")
    ap.add_argument("--orig-dir", type=Path, default=GT / "orig")
    ap.add_argument("--parser", type=Path, default=CUR / "data" / "verilog_data" / "parser2.py")
    ap.add_argument("--cycle-mode", choices=["none", "contract"], default="contract")
    ap.add_argument("--python", type=str, default="", help="parser2 的解释器（默认当前解释器）")
    ap.add_argument("--skip-existing", action="store_true", default=True)
    ap.add_argument("--force", action="store_true", help="重建已存在的 fold")
    args = ap.parse_args()

    if args.folds.strip():
        folds = [f.strip() for f in args.folds.split(",") if f.strip()]
    else:
        drop = {f.strip() for f in args.exclude.split(",") if f.strip()}
        folds = [f for f in ALL_FOLDS if f not in drop]

    py = args.python.strip() or sys.executable
    done, failed = [], []
    for fold in folds:
        work = GT / "folds" / fold
        pt = work / "data" / "processed" / "trans_graph.pt"
        if pt.exists() and not args.force:
            print(f"[SKIP] {fold} 已有 .pt", flush=True)
            done.append(fold)
            continue
        vj = args.matrix_root / "folds" / fold / "views.json"
        if not vj.exists():
            print(f"[FAIL] {fold}: 缺 {vj}", flush=True)
            failed.append(fold)
            continue
        cmd = [py, "-X", "utf8", str(GT / "make_dataset.py"),
               "--matrix-root", str(args.matrix_root), "--orig-dir", str(args.orig_dir),
               "--work-dir", str(work), "--views-list", str(vj), "--fold-json", str(vj),
               "--cycle-mode", args.cycle_mode, "--run-parser", "--parser", str(args.parser),
               "--build-pt", "--python", py]
        log = GT / "folds" / f"_build_{fold}.log"
        t0 = time.time()
        print(f"\n===== {fold}（{len(json.loads(vj.read_text(encoding='utf-8'))['train_views'])} "
              f"train + {len(json.loads(vj.read_text(encoding='utf-8'))['test_views'])} test 视图）=====",
              flush=True)
        with open(log, "w", encoding="utf-8") as lf:
            rc = subprocess.call(cmd, cwd=str(GT), stdout=lf, stderr=subprocess.STDOUT)
        dt = (time.time() - t0) / 60
        print(f"  rc={rc}｜{dt:.1f} min｜日志 {log}", flush=True)
        (done if rc == 0 else failed).append(fold)

    print(f"\n[汇总] 成功 {len(done)}：{done}\n       失败 {len(failed)}：{failed}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
