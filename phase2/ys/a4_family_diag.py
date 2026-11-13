"""a4_family_diag.py —— A4 **三胞胎**诊断（`a4trojan_sK` vs `a4ctldead_sK` / `a4ctlequiv_sK` ✓）。

为什么这是最干净的"判据"实验 ✓：三者在**同 host、同 shape** 下结构匹配 ✓，
唯一区别是"载荷接死线（ctldead ✓）/ 结构等价改写（ctlequiv ✓）vs 真木马（trojan ✓）" ✓。
若模型靠结构 ✗ → 三者分数应当接近 ⚠️；若能分开 ✓ → 抓到的是**语义**（载荷是否接真实输出 ✓）。

指标 ✓（逐视图、再按 host/shape 汇总 ✓）：`auc_rank` / `fp_rate` / `top1` / `top5` / `dmedian`。

用法：
  py -X utf8 phase2/ys/a4_family_diag.py --pt generate_trans/folds/_dev_a4/data/processed/trans_graph.pt \
      --npz _devcfg/gnn_a4_s42.npz
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
DST = ROOT / "10.15" / "02_弱监督检测" / "N1_对照诊断"


def parse_view(v: str):
    p = str(v).split("__")
    host = p[0]
    m = re.match(r"(a4\w+?)_s(\d+)_", p[1]) if len(p) > 1 else None
    kind = m.group(1) if m else ""
    shape = int(m.group(2)) if m else -1
    return host, kind, shape


def pct_rank(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x)
    r = np.empty(len(x), dtype=np.float64)
    r[order] = np.arange(len(x)) / max(1, len(x) - 1)
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/_dev_a4/data/processed/trans_graph.pt")
    ap.add_argument("--npz", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=DST)
    a = ap.parse_args()
    work = a.pt.parents[2]
    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    y = np.asarray(d.y, np.int8).astype(np.int64)
    fids = np.asarray(json.loads((work / "data/for_train/metadata_trans.json")
                                 .read_text(encoding="utf-8"))["file_ids"]).astype(str)
    meta = json.loads((work / "views.json").read_text(encoding="utf-8"))
    test_views = [str(v) for v in meta["test_views"]]

    g = np.load(a.npz)
    idx = g["idx"].astype(np.int64)
    s = np.full(len(y), -1.0, np.float32)
    s[idx] = g["score"].astype(np.float32)
    seen = np.zeros(len(y), bool)
    seen[idx] = True

    tri = {}
    for v in test_views:
        h, kind, shape = parse_view(v)
        tri.setdefault((h, shape), {})[kind] = v

    rows = []
    for (h, shape), dd in sorted(tri.items()):
        vt = dd.get("a4trojan")
        if not vt:
            continue
        mt = (fids == vt) & seen
        yt, st = y[mt], s[mt]
        pos = int(yt.sum())
        if pos == 0 or len(st) < 10:
            continue
        for kind in ("a4ctldead", "a4ctlequiv"):
            vc = dd.get(kind)
            if not vc:
                continue
            mc = (fids == vc) & seen
            sc = s[mc]
            if len(sc) < 10:
                continue
            rt, rc = pct_rank(st), pct_rank(sc)
            lab = np.r_[np.ones(pos), np.zeros(len(sc))]
            auc = float(roc_auc_score(lab, np.r_[rt[yt == 1], rc]))
            thr = float(np.percentile(st[yt == 1], 95))
            order = np.argsort(-st)
            rows.append(dict(host=h, shape=shape, control=kind, n_pos=pos, n_ctl=int(len(sc)),
                             auc_rank=auc, fp_rate=float((sc > thr).mean()),
                             top1=float(yt[order[:max(1, int(len(st) * 0.01))]].sum() / pos),
                             top5=float(yt[order[:max(1, int(len(st) * 0.05))]].sum() / pos),
                             dmedian=float(np.median(st[yt == 1]) - np.median(sc))))
    if not rows:
        raise SystemExit("[ERROR] 没有可用的 A4 三胞胎 ✗（检查 _dev_a4 fold ✓ + test 视图 ✓）")
    df = pd.DataFrame(rows)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out_dir / "tables" / "a4_triplet_metrics.csv", index=False, encoding="utf-8-sig")

    lines = ["# N1 · A4 三胞胎诊断（结构匹配 ✓，`_dev_a4` ✓）", "",
             "三者同 host、同 shape ✓：`a4trojan`（真木马 ✓）vs `a4ctldead`（载荷接死线 ✓）vs "
             "`a4ctlequiv`（结构等价 ✓）。", "",
             "| host | shape | 对照 | AUC(rank) | 对照误报率 | top-1% | top-5% | Δ中位分 |",
             "|---|---|---|---|---|---|---|---|"]
    for _, r in df.sort_values(["host", "shape", "control"]).iterrows():
        lines.append(f"| {r['host']} | s{int(r['shape'])} | {r['control']} | {r['auc_rank']:.3f} | "
                     f"{r['fp_rate']:.4f} | {r['top1']:.2f} | {r['top5']:.2f} | {r['dmedian']:+.4f} |")
    g2 = df.groupby("control").agg(auc=("auc_rank", "mean"), fp=("fp_rate", "mean"),
                                   top1=("top1", "mean"), top5=("top5", "mean"),
                                   dm=("dmedian", "mean"), n=("auc_rank", "count"))
    lines += ["", "## 按对照类型汇总 ✓", "", "```",
              g2.round(4).to_string(), "```", "",
              '> ✓ **判据解读**：AUC(rank) > 0.5 ⇒ 模型能把「真木马」排在同结构对照之上 ✓；'
              '对照误报率低 ⇒ 不是「见到相似结构就报警」✓。']
    (a.out_dir / "a4_triplet_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:40]))
    print(f"\n[out] {a.out_dir / 'tables' / 'a4_triplet_metrics.csv'}（{len(df)} 行 ✓）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
