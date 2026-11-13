#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_fold_groups.py — 顺序跑一个 fold 的 4 组实验，并汇总成一张 MACRO 对照表

4 组（与 train_test2.2 的 train_mode 语义对齐，视图预算策略在 2.3 里才真正生效）：
  G1_OrigOnly   train_mode=1  --view-policy all                  （只用 Orig，无 trans 项）
  G2_EqAug      train_mode=2  --view-policy random  --budget B   （随机 B 个 trans 视图，无一致性项）
  G3_RandCons   train_mode=3  --view-policy random  --budget B   （同 G2 视图，加一致性项 → 隔离 λ_const 的影响）
  G4_PredHard   train_mode=4  --view-policy pred_hard --budget B （按当前模型难度选视图 + 一致性项）

用法：
  python run_fold_groups.py --work-dir ../generate_trans/folds/single_to_composed_d2 \
      --fold-json ../generate_trans/matrix/folds/single_to_composed_d2/views.json \
      --fold-mode fold --epochs 100 --seed 42 --view-budget 4
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent

GROUPS = [
    ("G1_OrigOnly", 1, "all", 1),
    ("G2_EqAug", 2, "random", None),          # None -> 用 --view-budget
    ("G3_RandCons", 3, "random", None),
    ("G4_PredHard", 4, "pred_hard", None),
]
MACRO_KEYS = ["AP", "ROC-AUC", "Anchor_AP_Orig", "Anchor_AP_Trans", "Recall@1%", "Recall@2%",
              "Recall@5%", "Paired_MAE", "Paired_MAE_PerOrig", "Flip_Rate", "Flip_Rate_PerOrig",
              "Spearman_Corr", "Spearman_Corr_PerOrig", "Precision", "Recall", "FPR",
              "Macro-F1", "Anchor_Coverage"]


def parse_args():
    ap = argparse.ArgumentParser(description="跑一个 fold 的 4 组实验并汇总")
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--fold-json", type=Path, required=True)
    ap.add_argument("--fold-mode", choices=["fold", "loco"], default="fold")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--seeds", type=str, default="",
                    help="多 seed（逗号分隔，如 42,43,44）：每个 seed 跑完整 4 组并各出一张对照表；"
                         "给了 --seeds 时忽略 --seed")
    ap.add_argument("--view-budget", type=int, default=4)
    ap.add_argument("--view-policy-backend", default="pred_hard",
                    help="mode4 使用的策略名（默认 pred_hard）")
    ap.add_argument("--groups", type=str, default="",
                    help="只跑这些组（逗号分隔，如 G1_OrigOnly,G4_PredHard）")
    ap.add_argument("--tag-suffix", type=str, default="", help="追加到结果目录名的后缀")
    ap.add_argument("--amp", action="store_true",
                    help="bf16 autocast（CUDA 下显存约减半；大 fold 必需）")
    ap.add_argument("--save-ckpt", action="store_true",
                    help="透传给 train_test2.3.py：把每组最优 state_dict 存到结果目录，供 phase2 复用")
    ap.add_argument("--log-dir", type=Path, default=CUR / "logs_groups")
    ap.add_argument("--python", type=str, default="")
    return ap.parse_args()


def main():
    args = parse_args()
    seeds = ([int(s) for s in args.seeds.split(",") if s.strip()]
             if args.seeds.strip() else [args.seed])
    rc = 0
    for k, seed in enumerate(seeds):
        print(f"\n########## seed {seed}（{k + 1}/{len(seeds)}） ##########", flush=True)
        rc |= run_one_seed(args, seed)
    return rc


def run_one_seed(args, seed: int) -> int:
    py = args.python.strip() or sys.executable
    args.log_dir.mkdir(parents=True, exist_ok=True)
    fold = json.loads(Path(args.fold_json).read_text(encoding="utf-8"))["fold"]
    keep = {g.strip() for g in args.groups.split(",") if g.strip()}
    rows = []

    for name, mode, policy, budget in GROUPS:
        if keep and name not in keep:
            continue
        b = int(budget if budget is not None else args.view_budget)
        tag = f"{name}{args.tag_suffix}"
        log = args.log_dir / f"{fold}_seed{seed}_mode{mode}_{tag}.log"
        cmd = [py, "-X", "utf8", str(CUR / "train_test2.3.py"),
               "--work-dir", str(args.work_dir), "--fold-json", str(args.fold_json),
               "--fold-mode", args.fold_mode, "--epochs", str(args.epochs),
               "--seed", str(seed), "--train-mode", str(mode),
               "--view-policy", policy, "--view-budget", str(b), "--tag", tag]
        if args.amp:
            cmd.append("--amp")
        if args.save_ckpt:
            cmd.append("--save-ckpt")
        print(f"\n===== {name}（train_mode={mode} policy={policy} budget={b}）=====", flush=True)
        print("  " + " ".join(cmd), flush=True)
        t0 = time.time()
        with open(log, "w", encoding="utf-8") as lf:
            rc = subprocess.call(cmd, cwd=str(CUR), stdout=lf, stderr=subprocess.STDOUT)
        dt = time.time() - t0
        print(f"  rc={rc}｜{dt/60:.1f} min｜日志 {log}", flush=True)
        if rc != 0:
            print(f"  [FAIL] {name} 失败，继续下一组（见日志）", flush=True)

        res_dir = CUR / "results"
        cand = sorted(res_dir.glob(f"{fold}_seed{seed}mode{mode}_*_{args.fold_mode}_{tag}"))
        if cand:
            cl = cand[-1] / "circuit_level_summary.csv"
            row = {"Group": name, "Train_Mode": mode, "Valid_View_ViewPolicy": policy,
                   "View_Budget": b, "Seed": seed, "Fold": fold, "Result_Dir": cand[-1].name,
                   "Minutes": round(dt / 60, 1)}
            if cl.exists():
                df = pd.read_csv(cl)
                macro = df[df["Circuit"] == "MACRO_MEAN"]
                if len(macro):
                    for k in MACRO_KEYS:
                        if k in macro.columns:
                            row[k] = float(macro.iloc[0][k])
                row["N_Circuits"] = int(len(df) - 2)
            rows.append(row)

    if not rows:
        return 0
    # 表名要带 fold_mode，否则 loco 会覆盖 fold 模式的表（fold 模式保持旧命名，兼容既有分析）
    mode_tag = "" if args.fold_mode == "fold" else f"_{args.fold_mode}"
    out = CUR / "results" / f"{fold}_seed{seed}_groups_macro{args.tag_suffix}{mode_tag}.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n[OK] 4 组对照表 -> {out}", flush=True)
    show = [c for c in ["Group", "AP", "Anchor_AP_Orig", "Anchor_AP_Trans",
                        "Recall@1%", "Recall@5%", "Paired_MAE", "Flip_Rate",
                        "Spearman_Corr"] if c in pd.DataFrame(rows).columns]
    print(pd.DataFrame(rows)[show].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
