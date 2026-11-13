"""region_eval_seeds.py —— **多种子**区域级评估（G03 的误差棒 ✓）。

对每个 `--npz`（= 一个 seed 的 `--dump-scores` ✓）同时算：
  · 节点级：pooled AP/AUC + 逐视图 AP/AUC/R@1%/R@5%（口径同 `summarize_npz.py` ✓）
  · 区域级（三种粒度 ✓，区域分数 = 区域内节点分数 **max** ✓，区域标签 = 是否含正 ✓）：
      `dff`      DFF 边界锥（B2 的 M1 ✓）
      `po_cone`  每个 PO 的反向组合锥，遇 DFF 停（B4 的 M4 ✓，PO 用 f28 `touches_PO` ✓）
      `view`     整个视图 = 1 区（M5 下界基线 ✓）
输出：`region_seeds.csv`（每 seed 一行 ✓）+ `region_seeds_mean.csv`（mean ± std ✓）。

用法：
  python -X utf8 phase2/ys/region_eval_seeds.py \
    --pt generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt \
    --npz _devcfg/gnn_v31_s42.npz _devcfg/gnn_v31_s1.npz _devcfg/gnn_v31_s2.npz \
    --out-dir _devcfg/region_seeds
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from region_eval import build_regions, dff_mask  # noqa: E402
from summarize_npz import score_one  # noqa: E402

KEYS = ["view_ap", "view_auc", "r1", "r5", "pooled_ap", "pooled_auc",
        "dff_pooled_ap", "dff_view_ap", "po_cone_pooled_ap", "po_cone_view_ap",
        "view_pooled_ap", "view_view_ap"]


def build_po(edge_index, is_dff, view_ids, po_nodes) -> np.ndarray:
    """M4：从 PO 反向传播，遇 DFF 停 ✓（与 region_methods.py 的 M4 一致 ✓）。"""
    src, dst = edge_index[0].numpy(), edge_index[1].numpy()
    lab = np.full(len(is_dff), -1, np.int64)
    lab[po_nodes] = po_nodes
    keep = ~is_dff[src]
    s, t = src[keep], dst[keep]
    for _ in range(256):
        m = (lab[s] < 0) & (lab[t] >= 0)
        if not m.any():
            break
        ss, tt = s[m], lab[t][m]
        _, first = np.unique(ss, return_index=True)
        lab[ss[first]] = tt[first]
    left = np.where(lab < 0)[0]
    if left.size:
        lab[left] = left
    return lab + view_ids.astype(np.int64) * (len(is_dff) + 1)


def eval_region(labels, p, seen, y, te, view_ids, nviews) -> tuple[float, float]:
    """返回（区域级 pooled AP ✓，区域级 per-view 均值 AP ✓）。只统计测试区且两类都有的 ✓。"""
    uniq, inv = np.unique(labels, return_inverse=True)
    R = len(uniq)
    size = np.bincount(inv, minlength=R)
    rmax = np.zeros(R, np.float32)
    np.maximum.at(rmax, inv, p)
    rpos = np.zeros(R, np.int32)
    np.add.at(rpos, inv, y)
    rseen = np.bincount(inv, weights=seen.astype(np.float32), minlength=R) > 0
    rte = np.bincount(inv, weights=te.astype(np.float32), minlength=R) > 0
    rview = np.zeros(R, np.int64)
    rview[inv] = view_ids
    m = rte & (size >= 2) & rseen
    if not (0 < (rpos[m] > 0).sum() < m.sum()):
        return float("nan"), float("nan")
    pooled = float(average_precision_score((rpos[m] > 0).astype(int), rmax[m]))
    aps = []
    for k in range(nviews):
        mm = m & (rview == k)
        if mm.sum() < 5:
            continue
        yy = (rpos[mm] > 0).astype(int)
        if not (0 < yy.sum() < mm.sum()):
            continue
        aps.append(float(average_precision_score(yy, rmax[mm])))
    return pooled, (float(np.mean(aps)) if aps else float("nan"))


def main() -> int:
    ap = argparse.ArgumentParser(description="多种子区域级评估（G03 误差棒）")
    ap.add_argument("--pt", type=Path, required=True)
    ap.add_argument("--npz", type=Path, nargs="+", required=True)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "_devcfg" / "region_seeds")
    a = ap.parse_args()
    work = a.pt.parents[2]

    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    y = np.asarray(d.y, np.int8).astype(np.int64)
    te = np.asarray(d.test_mask, bool)
    fids = json.loads((work / "data/for_train/metadata_trans.json")
                      .read_text(encoding="utf-8"))["file_ids"]
    meta = json.loads((work / "views.json").read_text(encoding="utf-8"))
    if isinstance(meta, dict) and "test_views" in meta:
        test_views = set(meta["test_views"])
    else:
        test_views = set(fids)
    test_mask = np.isin(np.asarray(fids), list(test_views))

    view_ids = np.zeros(len(y), np.int64)
    vm = {}
    for i, v in enumerate(fids):
        vm.setdefault(v, []).append(i)
    vnames = sorted(vm)
    for k, v in enumerate(vnames):
        view_ids[np.array(vm[v])] = k

    is_dff = dff_mask(X, work)
    po_nodes = np.where(X[:, 28] > 0.5)[0]      # f28 = touches_PO ✓
    reg = {
        "dff": build_regions(d.edge_index, is_dff, view_ids),
        "po_cone": build_po(d.edge_index, is_dff, view_ids, po_nodes),
        "view": view_ids.copy(),
    }
    print(f"[区域] 节点 {len(y)}｜DFF {int(is_dff.sum())}｜PO {len(po_nodes)}")
    for k, v in reg.items():
        u = np.unique(v)
        print(f"  {k:<8s} 区域 {len(u):>8d}｜平均 {len(y) / max(1, len(u)):.1f} 门/区")

    rows = []
    for i, f in enumerate(a.npz):
        rec = score_one(f, y, fids, test_mask)
        p = np.zeros(len(y), np.float32)
        seen = np.zeros(len(y), bool)
        g = np.load(f)
        idx = g["idx"].astype(np.int64)
        p[idx] = g["score"].astype(np.float32)
        seen[idx] = True
        out = {"seed": i, "npz": f.name,
               "view_ap": rec["view_ap"], "view_auc": rec["view_auc"],
               "r1": rec["r1"], "r5": rec["r5"],
               "pooled_ap": rec["pooled_ap"], "pooled_auc": rec["pooled_auc"]}
        for k, lab in reg.items():
            pa, va = eval_region(lab, p, seen, y, te, view_ids, len(vnames))
            out[f"{k}_pooled_ap"] = pa
            out[f"{k}_view_ap"] = va
        rows.append(out)
        print(f"  [seed {i}] {f.name}: node={out['view_ap']:.4f} "
              f"dff={out['dff_view_ap']:.4f} po={out['po_cone_view_ap']:.4f} "
              f"view={out['view_view_ap']:.4f}")

    df = pd.DataFrame(rows)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out_dir / "region_seeds.csv", index=False, encoding="utf-8-sig")

    keys = [k for k in KEYS if k in df.columns]
    summ = pd.DataFrame({
        "metric": keys,
        "mean": [float(df[k].mean()) for k in keys],
        "std": [float(df[k].std(ddof=1)) if len(df) > 1 else 0.0 for k in keys],
        "n": [len(df)] * len(keys),
    })
    summ.to_csv(a.out_dir / "region_seeds_mean.csv", index=False, encoding="utf-8-sig")
    print("\n[均值 ± std]")
    for _, r in summ.iterrows():
        print(f"  {r['metric']:<18s} {r['mean']:.4f} ± {r['std']:.4f}  (n={int(r['n'])})")
    print(f"\n[导出] {a.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
