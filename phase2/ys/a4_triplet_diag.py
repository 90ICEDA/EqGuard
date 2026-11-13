"""a4_triplet_diag.py —— N1 · **A4 三胞胎诊断**（trojan vs ctldead vs ctlequiv ✓）快速版。

⚠️ 口径 ✓（必须写进论文 ✗→✓）：
  · 本脚本用 **已入库的 `hosts_bt31` fold** 里现成的 `a4*` 视图 ✓（**rs232t1000 × 2 shape × 8 变体 = 48 视图** ✓），
    **不是**全量 5 host × 8 shape ✗（全量需先修 `_dev_a4` 的 fold 构建：CEC + orig_view_map ✗）。
  · 只做**推理打分** ✓，不训练 ✓（复用 `_devcfg/*.npz` ✓）。
  · 判定口径 ✓（与 `a4_pair_diag.py` 一致 ✓）：分数先转**视图内百分位** ✓；
    阈值 = `a4trojan` 正节点分数的 **95 分位** ✓ → 看 `ctldead/ctlequiv` 的**误报率** ✓。

输出 ✓：`tables/a4_triplet_metrics.csv` ✓ + `tables/a4_triplet_summary.md` ✓
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "10.15" / "02_弱监督检测" / "N1_对照诊断" / "tables"
FOLD = ROOT / "generate_trans" / "folds" / "hosts_bt31"


def kind_of(v: str) -> str:
    m = re.search(r"__(a4trojan|a4ctldead|a4ctlequiv)_", v)
    return m.group(1) if m else "other"


def shape_of(v: str) -> str:
    m = re.search(r"_s([0-9]+)_d", v)
    return f"s{m.group(1)}" if m else "?"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=Path, default=FOLD,
                    help="fold 目录 ✓（默认 hosts_bt31 ✓；A4 用 generate_trans/folds/_dev_a4 ✓）")
    ap.add_argument("--npz", nargs="+", default=["_devcfg/gnn_v31_s42.npz",
                                                 "_devcfg/gnn_v31r_l100_s42.npz"])
    ap.add_argument("--pt", type=Path, default=None,
                    help="默认 <fold>/data/processed/trans_graph.pt ✓")
    ap.add_argument("--out-dir", type=Path, default=OUT)
    a = ap.parse_args()
    fold = a.fold
    pt = a.pt or (fold / "data" / "processed" / "trans_graph.pt")

    d = torch.load(pt, map_location="cpu", weights_only=False, mmap=True)
    y = np.asarray(d.y).astype(int)
    fids = np.asarray(json.loads((fold / "data/for_train/metadata_trans.json")
                                 .read_text(encoding="utf-8"))["file_ids"]).astype(str)

    rows = []
    for npz in a.npz:
        p = ROOT / npz if not Path(npz).is_absolute() else Path(npz)
        if not p.exists():
            print(f"[skip] {p} 不存在 ✗")
            continue
        g = np.load(p)
        s = np.full(len(y), np.nan, np.float32)
        s[g["idx"].astype(np.int64)] = g["score"].astype(np.float32)

        views = sorted({v for v in fids if kind_of(v) != "other"})
        per = []
        for v in views:
            m = (fids == v) & ~np.isnan(s)
            if m.sum() < 2:
                continue
            sv, yv = s[m], y[m]
            pr = (sv - sv.min()) / max(1e-9, float(sv.max() - sv.min()))
            per.append(dict(model=p.stem, view=v, kind=kind_of(v), shape=shape_of(v),
                            nodes=int(m.sum()), pos=int(yv.sum()),
                            ap=(average_precision_score(yv, pr)
                                if 0 < yv.sum() < len(yv) else np.nan),
                            auc=(roc_auc_score(yv, pr)
                                 if 0 < yv.sum() < len(yv) else np.nan),
                            top1=float(np.mean(np.sort(pr)[-max(1, len(pr) // 100):])),
                            top5=float(np.mean(np.sort(pr)[-max(1, len(pr) // 20):]))))
        pdf = pd.DataFrame(per)
        # 阈值：a4trojan 的**正节点** 95 分位 ✓
        tro = pdf[pdf["kind"] == "a4trojan"]
        rows.append(pdf)
        print(f"\n=== {p.stem} ===  视图 {len(pdf)}")
        for k, g2 in pdf.groupby("kind"):
            print(f"  {k:11s} n={len(g2):2d}  AP={g2['ap'].mean():.4f}  "
                  f"top1%={g2['top1'].mean():.4f}  top5%={g2['top5'].mean():.4f}  "
                  f"pos={g2['pos'].mean():.1f}")
        # 误报率：每条对照视图里 top1% 均值 > trojan 的 top1% 均值 的比例 ✓
        if not tro.empty:
            t_thr = float(tro["top1"].mean())
            for k in ("a4ctldead", "a4ctlequiv"):
                g2 = pdf[pdf["kind"] == k]
                if len(g2):
                    print(f"  FP@{k}: top1% ≥ trojan 均值({t_thr:.3f}) 的视图 "
                          f"{int((g2['top1'] >= t_thr).sum())}/{len(g2)} "
                          f"= {(g2['top1'] >= t_thr).mean():.3f}")

    if not rows:
        print("[ERR] 没有可用模型 ✗")
        return 1
    allf = pd.concat(rows, ignore_index=True)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    allf.to_csv(a.out_dir / "a4_triplet_metrics.csv", index=False, encoding="utf-8-sig")

    # ✓ 跨 seed 汇总（同 kind 上 mean±std ✓；控制族 ap 全 nan → 只汇总 top1/top5 ✓）
    agg = (allf.groupby("kind")
           .agg(models=("model", "nunique"), views=("view", "nunique"),
                ap_mean=("ap", "mean"), ap_std=("ap", "std"),
                top1_mean=("top1", "mean"), top1_std=("top1", "std"),
                top5_mean=("top5", "mean"), top5_std=("top5", "std"))
           .reset_index())
    agg.to_csv(a.out_dir / "a4_triplet_seed_summary.csv", index=False,
               encoding="utf-8-sig")
    print("\n== 跨 seed 汇总 ✓ ==")
    print(agg.round(4).to_string(index=False))

    lines = ["# A4 三胞胎诊断（trojan vs ctldead vs ctlequiv ✓）", "",
             "> ⚠️ **口径**：`hosts_bt31` 内现成 `a4*` 视图 ✓ = **rs232t1000 × 2 shape × 8 变体 = 48 视图** ✓，",
             "> **不是**全量 5 host × 8 shape ✗（全量需补 `_dev_a4` 的 CEC + `orig_view_map.json` ✗）。",
             "> 分数 = 视图内 min-max 归一 ✓；`a4trojan` 才有正节点 ✓，两个控制族**没有真值** ✓ → 只看**误报倾向** ✓。", ""]
    for m, g2 in allf.groupby("model"):
        lines += [f"## {m}", "", "| kind | views | AP | top-1% 均分 | top-5% 均分 | 正节点/视图 |",
                  "|---|---:|---|---:|---:|---:|"]
        for k, g3 in g2.groupby("kind"):
            lines.append(f"| `{k}` | {len(g3)} | {g3['ap'].mean():.4f} | "
                         f"{g3['top1'].mean():.4f} | {g3['top5'].mean():.4f} | "
                         f"{g3['pos'].mean():.1f} |")
        lines.append("")
    (a.out_dir / "a4_triplet_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[out] {a.out_dir / 'a4_triplet_metrics.csv'}")
    print(f"[out] {a.out_dir / 'a4_triplet_summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
