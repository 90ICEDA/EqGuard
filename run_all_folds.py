#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_all_folds.py — 批量跑多个 fold（每个 fold 内跑 4 组 × N seeds）

等价于对每个 fold 调一次 run_fold_groups.py，但按 fold 串行、统一 tag-suffix/amp/epochs，
并在结尾打印进度汇总。数据集缺失的 fold 会被跳过（先跑 build_fold_datasets.py）。

用法：
  python run_all_folds.py --seeds 42,43,44 --amp --tag-suffix _amp --view-budget 4
  python run_all_folds.py --folds heldout_single_decomp,heldout_single_resub
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

CUR = Path(__file__).resolve().parent
GT = CUR / "generate_trans"

ALL_FOLDS = [
    # 先小后大，便于结果尽早出来
    "heldout_single_decomp", "heldout_single_balance",
    "heldout_single_refactor", "heldout_single_resub",
    "single_to_composed_d2", "single_to_composed_d3",
    "heldout_composed_decomp", "heldout_composed_balance",
    "heldout_composed_refactor", "heldout_composed_resub",
]


def main():
    ap = argparse.ArgumentParser(description="批量跑多个 fold 的 4 组实验")
    ap.add_argument("--folds", type=str, default="", help="逗号分隔；默认全部 10 个（按小→大）")
    ap.add_argument("--seeds", type=str, default="42,43,44")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--view-budget", type=int, default=4)
    ap.add_argument("--tag-suffix", type=str, default="_amp")
    ap.add_argument("--amp", action="store_true")
    ap.add_argument("--fold-mode", choices=["fold", "loco"], default="fold",
                    help="fold=变换泛化（默认）；loco=逐个目标电路留一（电路泛化）")
    ap.add_argument("--python", type=str, default="", help="训练用的解释器（默认当前解释器）")
    ap.add_argument("--log-dir", type=Path, default=CUR / "logs_groups")
    ap.add_argument("--skip-missing", action="store_true", default=True)
    args = ap.parse_args()

    folds = ([f.strip() for f in args.folds.split(",") if f.strip()] or ALL_FOLDS)
    py = args.python.strip() or sys.executable
    args.log_dir.mkdir(parents=True, exist_ok=True)
    t_all = time.time()
    summary = []

    for i, fold in enumerate(folds, 1):
        work = GT / "folds" / fold
        vj = GT / "matrix" / "folds" / fold / "views.json"
        pt = work / "data" / "processed" / "trans_graph.pt"
        if not pt.exists():
            print(f"[{i}/{len(folds)}] {fold}: 数据集不存在，跳过（先跑 build_fold_datasets.py）",
                  flush=True)
            summary.append({"fold": fold, "status": "missing_dataset"})
            continue
        n_views = len(json.loads(vj.read_text(encoding="utf-8"))["train_views"]) + \
            len(json.loads(vj.read_text(encoding="utf-8"))["test_views"])
        print(f"\n[{i}/{len(folds)}] ===== {fold}（{n_views} 视图）"
              f" at {time.strftime('%H:%M:%S')} =====", flush=True)
        cmd = [py, "-X", "utf8", str(CUR / "run_fold_groups.py"),
               "--work-dir", str(work), "--fold-json", str(vj),
               "--fold-mode", args.fold_mode, "--epochs", str(args.epochs),
               "--view-budget", str(args.view_budget), "--seeds", args.seeds,
               "--tag-suffix", args.tag_suffix, "--python", py]
        if args.amp:
            cmd.append("--amp")
        log = args.log_dir / f"allfolds_{fold}{args.tag_suffix}.log"
        t0 = time.time()
        with open(log, "w", encoding="utf-8") as lf:
            rc = subprocess.call(cmd, cwd=str(CUR), stdout=lf, stderr=subprocess.STDOUT)
        dt = (time.time() - t0) / 60
        print(f"    fold 完成 rc={rc}｜{dt:.1f} min｜日志 {log}", flush=True)
        summary.append({"fold": fold, "status": "ok" if rc == 0 else f"rc={rc}",
                        "minutes": round(dt, 1)})

    print(f"\n===== 全部 fold 结束（总 {(time.time()-t_all)/60:.1f} min）=====")
    for s in summary:
        print(f"  {s['fold']:<26s} {s['status']:<16s} {s.get('minutes', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
