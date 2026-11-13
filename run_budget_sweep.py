#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_budget_sweep.py — 视图预算扫描：对同一 fold 依次跑 budget ∈ {1,2,4,8}

每个 budget 内仍是 4 组 × N seeds（G1 不用 trans 视图，故 budget 对它无影响）。
结果表：results/<fold>_seed<seed>_groups_macro_b<budget>.csv

用法：
  python run_budget_sweep.py --fold single_to_composed_d2 --budgets 1,2,8 --seeds 42,43,44 --amp
"""

import argparse
import subprocess
import sys
from pathlib import Path

CUR = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description="视图预算扫描")
    ap.add_argument("--fold", type=str, default="single_to_composed_d2")
    ap.add_argument("--budgets", type=str, default="1,2,8")
    ap.add_argument("--seeds", type=str, default="42,43,44")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--amp", action="store_true")
    ap.add_argument("--fold-mode", choices=["fold", "loco"], default="fold")
    ap.add_argument("--python", type=str, default="")
    ap.add_argument("--log-dir", type=Path, default=CUR / "logs_groups")
    args = ap.parse_args()

    py = args.python.strip() or sys.executable
    args.log_dir.mkdir(parents=True, exist_ok=True)
    for b in [int(x) for x in args.budgets.split(",") if x.strip()]:
        tag = f"_b{b}"
        cmd = [py, "-X", "utf8", str(CUR / "run_all_folds.py"), "--folds", args.fold,
               "--seeds", args.seeds, "--tag-suffix", tag, "--view-budget", str(b),
               "--epochs", str(args.epochs), "--fold-mode", args.fold_mode,
               "--python", py]
        if args.amp:
            cmd.append("--amp")
        log = args.log_dir / f"budget{tag}_{args.fold}.log"
        print(f"\n===== budget={b} =====", flush=True)
        with open(log, "w", encoding="utf-8") as lf:
            rc = subprocess.call(cmd, cwd=str(CUR), stdout=lf, stderr=subprocess.STDOUT)
        print(f"  rc={rc}｜日志 {log}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
