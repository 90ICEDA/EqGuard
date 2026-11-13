# -*- coding: utf-8 -*-
"""
loco_metrics.py —— 用 LOCO 的 checkpoint 精确复算「检查预算」口径

`loco_report.py` 只能从 `variant_level_summary.csv` 复算（没有 first-hit rank）。
本脚本直接用 LOCO run 目录里**每个留出电路的** `best_model_<circuit>.pt`：
  * 只在该电路的 test 视图上评测（这才是 LOCO 的定义）；
  * 输出 AP_T / Recall@1-5% / **FirstHitRank_Norm** / **AnyMiss@K%** / **InspectionCost**
    / Paired_MAE / Flip_Rate / Trojan_Drift；
  * 再做电路级宏平均（先电路内平均、再对电路平均）。

兼容 M0（GINNodeClassifier）与 M1/M2/M3（SecGIN，ckpt 里带 `model_kind=sec`）。

用法：
  python phase2/loco_metrics.py --work-dir generate_trans/folds/single_to_composed_d2 \
      --run-glob "results/single_to_composed_d2_*_loco_*" --amp
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase2 import p2common as C  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="LOCO 精确检查预算指标")
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--run-glob", type=str, default="results/*_loco_*")
    ap.add_argument("--results-root", type=Path, default=C.ROOT)
    ap.add_argument("--out-dir", type=Path, default=C.ROOT / "results" / "phase2" / "loco")
    ap.add_argument("--amp", action="store_true")
    args = ap.parse_args()

    import torch
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    work = args.work_dir.resolve()
    orig, trans, meta = C.load_fold(work / "data" / "processed")
    for d in (orig, trans):
        d.x = d.x.to(device); d.edge_index = d.edge_index.to(device); d.y = d.y.to(device)
    alignment = trans.alignment.to(device)
    vidx = {v: ix.to(device) for v, ix in C.view_index(trans).items()}
    al_o = alignment[0].cpu().numpy(); al_t = alignment[1].cpu().numpy()

    runs = sorted(p for p in args.results_root.glob(args.run_glob) if p.is_dir())
    rows = []
    for run in runs:
        cks = sorted(run.glob("best_model_*.pt"))
        if not cks:
            continue
        group = next((g for g in ("M0_loco", "M1", "M2", "M3", "G1_OrigOnly", "G2_EqAug",
                                  "G3_RandCons", "G4_PredHard") if g.strip("_loco") in run.name), run.name)
        for ck in cks:
            circ = ck.stem.replace("best_model_", "")
            tviews = [v for v in vidx if v.split("__")[0] == circ and trans.view_role.get(v) == "test"]
            if not tviews:
                continue
            model, blob = C.load_ckpt(ck, device)
            thr = float(blob["threshold"])
            with C.Embedder(model) as emb:
                _, lo = emb.forward(orig.x, orig.edge_index, amp=args.amp)
                _, lt = emb.forward(trans.x, trans.edge_index, amp=args.amp)
            pt = torch.softmax(lt, 1)[:, 1].cpu().numpy()
            in_circ = np.isin(al_t, np.concatenate([vidx[v].cpu().numpy() for v in tviews]))
            ao = torch.tensor(al_o[in_circ], dtype=torch.long, device=device)
            at = torch.tensor(al_t[in_circ], dtype=torch.long, device=device)
            pc = (C.paired_consistency(lo, lt, torch.stack([ao, at]), orig.y, thr)
                  if len(ao) > 1 else {})
            for v in tviews:
                idx = vidx[v].cpu().numpy()
                y = trans.y[vidx[v]].detach().cpu().numpy().astype(int)
                if int(y.sum()) == 0:
                    continue
                rows.append({"run": run.name, "group": group, "heldout_circuit": circ,
                             "view": v, "threshold": thr,
                             **C.view_budget_metrics(pt[idx], y), **pc})
    if not rows:
        print("[WARN] 没有可用 (run, circuit, view)")
        return 1
    df = pd.DataFrame(rows)
    df.to_csv(args.out_dir / "loco_per_view_ckpt.csv", index=False, encoding="utf-8-sig")
    keys = ["AP_T", "Recall@1%", "Recall@2%", "Recall@5%", "FirstHitRank_Norm",
            "AnyMiss@1%", "AnyMiss@2%", "AnyMiss@5%", "InspectionCost",
            "Paired_MAE", "Flip_Rate", "Trojan_Drift"]
    per_circ = df.groupby(["group", "run", "heldout_circuit"])[keys].mean(numeric_only=True).reset_index()
    per_circ.to_csv(args.out_dir / "loco_per_circuit_ckpt.csv", index=False, encoding="utf-8-sig")
    macro = per_circ.groupby(["group", "run"])[keys].mean(numeric_only=True).round(4).reset_index()
    summ = macro.groupby("group")[keys].mean(numeric_only=True).round(4).reset_index()
    macro.to_csv(args.out_dir / "loco_macro_by_run_ckpt.csv", index=False, encoding="utf-8-sig")
    summ.to_csv(args.out_dir / "loco_summary_ckpt.csv", index=False, encoding="utf-8-sig")
    print("\n=== LOCO（逐电路 ckpt，宏平均）===")
    print(summ[["group", "AP_T", "Recall@5%", "FirstHitRank_Norm", "AnyMiss@5%",
                "InspectionCost", "Paired_MAE", "Flip_Rate"]].to_string(index=False))
    print(f"\n[导出] {args.out_dir / 'loco_summary_ckpt.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
