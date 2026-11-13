"""a4_pair_diag.py —— N1：**木马 vs 结构匹配对照**的模型判据诊断（CPU ✓，复用已有 npz ✓）。

思路 ✓：matched control（`ctlmatch*` ✓）与木马**同触发规模/风格/载荷风格/长度** ✓，
        只差"名字前缀 + 触发信号另一批" ✓ → 若模型靠**结构**判断 ✗，两者分数应接近 ⚠️；
        若能把木马正节点排到对照之上 ✓，说明抓到了与木马语义相关的细节 ✓。

指标（逐视图 ✓，再按 pair/host/recipe 汇总 ✓）：
  `auc_rank`   视图内百分位后 ✓ AUC(木马正节点 vs 对照节点) ✓
  `fp_rate`    阈值 = 木马正节点分数 95 分位 ✓ → 对照视图被判正的节点比例 ✓
  `top1/top5`  木马正节点落在 top-1% / 5% 的比例 ✓
  `dmedian`    木马正节点中位分 − 对照节点中位分 ✓
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
PAIRS = {"injalpha": "ctlmatcha", "injbeta": "ctlmatchb", "injgamma": "ctlmatchc",
         "injdelta": "ctlmatchd", "injepsilon": "ctlmatche", "injzeta": "ctlmatchf",
         "injeta": "ctlmatchg", "injtheta": "ctlmatchh"}
DST = ROOT / "10.15" / "02_弱监督检测" / "N1_对照诊断"


def parse_view(v: str) -> tuple[str, str, str]:
    """`host__inst_d1_s42__recipe` → (host, inst, recipe) ✓。"""
    p = str(v).split("__")
    host = p[0]
    inst = re.split(r"_d\d+_s\d+", p[1])[0] if len(p) > 1 else ""
    recipe = p[2] if len(p) > 2 else ""
    return host, inst, recipe


def pct_rank(x: np.ndarray) -> np.ndarray:
    """视图内百分位（1 = 最高分 ✓）—— 消除"视图间分数不可比"✗。"""
    order = np.argsort(x)
    r = np.empty(len(x), dtype=np.float64)
    r[order] = np.arange(len(x)) / max(1, len(x) - 1)
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt")
    ap.add_argument("--npz", type=Path, nargs="+", required=True)
    ap.add_argument("--out-dir", type=Path, default=DST)
    a = ap.parse_args()
    work = a.pt.parents[2]
    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    y = np.asarray(d.y, np.int8).astype(np.int64)
    fids = np.asarray(json.loads((work / "data/for_train/metadata_trans.json")
                                 .read_text(encoding="utf-8"))["file_ids"])
    meta = json.loads((work / "views.json").read_text(encoding="utf-8"))
    test_views = list(meta["test_views"])

    groups = {}
    for v in test_views:
        h, inst, rec = parse_view(v)
        groups.setdefault((h, rec), {})[inst] = v

    rows = []
    for f in a.npz:
        g = np.load(f)
        idx = g["idx"].astype(np.int64)
        s = np.full(len(y), -1.0, np.float32)
        s[idx] = g["score"].astype(np.float32)
        seen = np.zeros(len(y), bool)
        seen[idx] = True
        for (h, rec), d_ in sorted(groups.items()):
            for tro, ctl in PAIRS.items():
                if tro not in d_ or ctl not in d_:
                    continue
                mt = (fids == d_[tro]) & seen
                mc = (fids == d_[ctl]) & seen
                yt, st, sc = y[mt], s[mt], s[mc]
                pos = int(yt.sum())
                if pos == 0 or len(sc) < 10:
                    continue
                rt, rc = pct_rank(st), pct_rank(sc)
                lab = np.r_[np.ones(pos), np.zeros(len(sc))]
                auc = float(roc_auc_score(lab, np.r_[rt[yt == 1], rc]))
                thr = float(np.percentile(st[yt == 1], 95))
                order = np.argsort(-st)
                top1 = float(yt[order[:max(1, int(len(st) * 0.01))]].sum() / pos)
                top5 = float(yt[order[:max(1, int(len(st) * 0.05))]].sum() / pos)
                rows.append(dict(npz=f.name, host=h, recipe=rec, pair=f"{tro}|{ctl}",
                                 family=tro, n_pos=pos, n_ctl=int(len(sc)), auc_rank=auc,
                                 fp_rate=float((sc > thr).mean()), top1=top1, top5=top5,
                                 dmedian=float(np.median(st[yt == 1]) - np.median(sc))))
    if not rows:
        raise SystemExit("[ERROR] test 视图里没有 inj*/ctlmatch* 配对 ✗（检查 fold 组成 ✓）")
    df = pd.DataFrame(rows)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out_dir / "tables" / "n1_pair_metrics.csv", index=False, encoding="utf-8-sig")

    lines = ["# N1 木马 vs 结构匹配对照：判据诊断（v3.1 ✓，复用已有 npz ✓）", "",
             "口径 ✓：分数先换成**视图内百分位** ✓（消除跨视图不可比 ✗）；"
             "阈值 = 木马正节点分数的 95 分位 ✓ → 看对照视图误报率 ✓。", ""]
    for npz_name, g in df.groupby("npz"):
        lines += [f"## {npz_name}", "",
                  "| 家族 | host/配方 | AUC(rank) | 对照误报率 | top-1% | top-5% | Δ中位分 |",
                  "|---|---|---|---|---|---|---|"]
        for _, r in g.sort_values("auc_rank").iterrows():
            lines.append(f"| `{r['family']}` | {r['host']}/{r['recipe']} | {r['auc_rank']:.3f} | "
                         f"{r['fp_rate']:.4f} | {r['top1']:.2f} | {r['top5']:.2f} | {r['dmedian']:+.4f} |")
        m = g.agg({"auc_rank": "mean", "fp_rate": "mean", "top1": "mean", "top5": "mean",
                   "dmedian": "mean"})
        lines += ["", f"> 均值 ✓：AUC **{m['auc_rank']:.3f}** ✓｜对照误报 **{m['fp_rate']:.4f}** ✓｜"
                      f"top-1% **{m['top1']:.2f}** ✓｜top-5% **{m['top5']:.2f}** ✓｜"
                      f"Δ中位分 **{m['dmedian']:+.4f}** ✓", ""]
    lines += ["## 判读", "",
              "- AUC(rank) 高 ✓ → 模型**能**把木马正节点排在其结构孪生对照之上 ✓；",
              "- 对照误报率高 ✗ → 模型在**结构相同**的良性代码上也报警 ✗（判据偏结构 ✗ 而非语义 ✓）；",
              "- top-1%/5% 与 Δ中位分给出\"头部可用性\" ✓（定位场景最关心 ✓）。"]
    (a.out_dir / "tables" / "n1_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:40]))
    print(f"\n[out] {a.out_dir / 'tables' / 'n1_pair_metrics.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
