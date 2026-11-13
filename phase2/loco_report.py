# -*- coding: utf-8 -*-
"""
loco_report.py —— 任务6：LOCO 优先的评测口径

不再只看同设计 fold 的 AP，而是对每个 **留出电路** 报：
    AP_T / Recall@5% / worst-view Recall@5% / AnyMiss@5%（= Recall@5% 为 0 的视图比例）
并做电路级宏平均（先电路内平均、再对电路平均），最后按 seed 汇总 mean±std。

数据来源：已有 LOCO run 目录 `results/<fold>_seed*<group>_loco_*<tag>/variant_level_summary.csv`
（`Split` 列 = 被留出的电路）。本脚本**不训练**，只做重算与重排版，
因此对冻结结果（G1–G4）可立即复算；对 M1/M2 只要补跑 LOCO + `--save-ckpt` 即可同法汇总。

注意：`variant_level_summary.csv` 里没有 first-hit rank（需要逐节点分数），
故这里用 **worst-view Recall@5%** 与 **AnyMiss@5%** 作为「有限检查预算」代理指标；
若 run 目录里有 `best_model_*.pt`，可用 phase2/audit_shortcuts.py 补出精确的
FirstHitRank / InspectionCost。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase2 import p2common as C  # noqa: E402

GROUP_RE = re.compile(r"mode\d+_[a-z_]*?b\d+_(?:loco|fold)_(G\d+_[A-Za-z]+|M\d+_[A-Za-z0-9]+)")


def group_of(run_name: str) -> str:
    m = GROUP_RE.search(run_name)
    if m:
        return m.group(1)
    for g in ("G1_OrigOnly", "G2_EqAug", "G3_RandCons", "G4_PredHard"):
        if g in run_name:
            return g
    for g in ("M1_adv", "M2_dual"):
        if g in run_name:
            return g
    return "UNKNOWN"


def per_circuit(vs: pd.DataFrame) -> pd.DataFrame:
    t = vs[vs["Type"] == "TRANS"].copy()
    if t.empty:
        return pd.DataFrame()
    t["AnyMiss"] = (t["Recall@5%"] <= 1e-9).astype(float)
    t = t.rename(columns={"Recall@5%": "Recall5"})
    g = t.groupby("Split").agg(
        n_views=("View", "size"),
        AP_T=("AP_T", "mean"),
        Recall5=("Recall5", "mean"),
        worst_view_Recall5=("Recall5", "min"),
        AnyMiss5=("AnyMiss", "mean")).reset_index()
    return g.rename(columns={"Split": "heldout_circuit"})


def main() -> int:
    ap = argparse.ArgumentParser(description="任务6：LOCO 优先评测汇总")
    ap.add_argument("--results-root", type=Path, default=C.ROOT / "results")
    ap.add_argument("--fold", type=str, default="single_to_composed_d2")
    ap.add_argument("--mode", choices=["loco", "fold"], default="loco")
    ap.add_argument("--suffix", type=str, default="_amp")
    ap.add_argument("--out-dir", type=Path, default=C.ROOT / "results" / "phase2" / "loco")
    args = ap.parse_args()

    pat = f"{args.fold}_seed*_{args.mode}_*{args.suffix}"
    runs = [d for d in sorted(args.results_root.glob(pat))
            if (d / "variant_level_summary.csv").exists()]
    if not runs:
        print(f"[WARN] 没找到 run（pattern: {pat}）")
        return 1

    rows = []
    for d in runs:
        m = re.search(r"seed(\d+)", d.name)
        seed = int(m.group(1)) if m else -1
        pc = per_circuit(pd.read_csv(d / "variant_level_summary.csv"))
        if pc.empty:
            continue
        pc.insert(0, "seed", seed)
        pc.insert(0, "group", group_of(d.name))
        pc.insert(0, "run", d.name)
        rows.append(pc)
    per_run = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    C.ensure_dir(args.out_dir)
    tag = f"{args.fold}_{args.mode}{args.suffix}"
    per_run.to_csv(args.out_dir / f"{tag}_per_circuit.csv", index=False, encoding="utf-8-sig")

    # 电路级宏平均（每个 run 内先对电路平均）
    macro = per_run.groupby(["group", "seed"]).agg(
        LOCO_AP_T=("AP_T", "mean"),
        LOCO_Recall5=("Recall5", "mean"),
        LOCO_worst_view_Recall5=("worst_view_Recall5", "min"),
        LOCO_AnyMiss5=("AnyMiss5", "mean"),
        n_circuits=("heldout_circuit", "nunique")).reset_index()
    summ = macro.groupby("group").agg(
        n_seeds=("seed", "nunique"),
        AP_T_mean=("LOCO_AP_T", "mean"), AP_T_std=("LOCO_AP_T", "std"),
        Recall5_mean=("LOCO_Recall5", "mean"),
        worst_view_Recall5=("LOCO_worst_view_Recall5", "mean"),
        AnyMiss5=("LOCO_AnyMiss5", "mean")).round(4).reset_index()
    macro.to_csv(args.out_dir / f"{tag}_per_seed.csv", index=False, encoding="utf-8-sig")
    summ.to_csv(args.out_dir / f"{tag}_summary.csv", index=False, encoding="utf-8-sig")

    print(f"\n=== LOCO 优先汇总（{args.fold}｜{args.mode}｜{len(runs)} 个 run）===")
    print(summ.to_string(index=False))
    print(f"\n[导出] {args.out_dir / f'{tag}_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
