"""make_t12_region_table.py —— T12：区域级监督（λ=10 ✓）× 3 seed 的对照表 ✓。

对比：基线（`gnn_v31_s{42,1,2}.npz`）vs 区域损失（`gnn_v31r_l100_s{42,1,2}.npz` ✓）
指标：节点（view AP/AUC/R@1%/R@5% ✓）+ 区域（DFF 锥 / PO 锥的 per-view AP ✓）
输出：`C6_区域级监督/tables/t12_region_loss{,_summary}.csv` ✓ + `t12_region_loss.md` ✓（可直接贴进 TABLES.md ✓）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from region_eval_seeds import build_po, eval_region  # noqa: E402
from region_eval import build_regions, dff_mask       # noqa: E402
from summarize_npz import score_one                   # noqa: E402

ROOT = HERE.parents[1]   # HERE = phase2/ys ✓
DST = ROOT / "10.15" / "03_特征与模型" / "C6_区域级监督"
KEYS = ["view_ap", "view_auc", "r1", "r5", "dff_view_ap", "po_cone_view_ap"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt")
    ap.add_argument("--base", type=Path, nargs=3, required=True)
    ap.add_argument("--reg", type=Path, nargs=3, required=True)
    ap.add_argument("--out-dir", type=Path, default=DST / "tables")
    a = ap.parse_args()
    work = a.pt.parents[2]

    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    y = np.asarray(d.y, np.int8).astype(np.int64)
    fids = np.asarray(json.loads((work / "data/for_train/metadata_trans.json")
                                 .read_text(encoding="utf-8"))["file_ids"])
    meta = json.loads((work / "views.json").read_text(encoding="utf-8"))
    test_views = set(meta["test_views"])
    test_mask = np.isin(fids, list(test_views))
    te = np.asarray(d.test_mask, bool)

    vm = {}
    for i, v in enumerate(fids):
        vm.setdefault(str(v), []).append(i)
    vnames = sorted(vm)
    view_ids = np.zeros(len(y), np.int64)
    for k, v in enumerate(vnames):
        view_ids[np.array(vm[v])] = k

    is_dff = dff_mask(X, work)
    po_nodes = np.where(X[:, 28] > 0.5)[0]
    reg = {"dff": build_regions(d.edge_index, is_dff, view_ids),
           "po_cone": build_po(d.edge_index, is_dff, view_ids, po_nodes)}
    print(f"[regions] " + "  ".join(f"{k}={len(np.unique(v))}" for k, v in reg.items()), flush=True)

    rows = []
    for tag, files in (("base", a.base), ("region_l10", a.reg)):
        for i, f in enumerate(files):
            rec = score_one(f, y, fids, test_mask)
            p = np.zeros(len(y), np.float32)
            seen = np.zeros(len(y), bool)
            g = np.load(f)
            idx = g["idx"].astype(np.int64)
            p[idx] = g["score"].astype(np.float32)
            seen[idx] = True
            out = dict(model=tag, seed=i, npz=f.name,
                       view_ap=rec["view_ap"], view_auc=rec["view_auc"],
                       r1=rec["r1"], r5=rec["r5"])
            for k, lab in reg.items():
                _, va = eval_region(lab, p, seen, y, te, view_ids, len(vnames))
                out[f"{k}_view_ap"] = va
            rows.append(out)
            print(f"  [{tag} seed{i}] {f.name}: AP={out['view_ap']:.4f} "
                  f"dff={out['dff_view_ap']:.4f} po={out['po_cone_view_ap']:.4f}", flush=True)

    df = pd.DataFrame(rows)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out_dir / "t12_region_loss.csv", index=False, encoding="utf-8-sig")
    g = df.groupby("model")
    summ = pd.DataFrame({"model": sorted(df["model"].unique())})
    for k in KEYS:
        summ[k + "_mean"] = g[k].mean().values
        summ[k + "_std"] = g[k].std(ddof=1).values
    summ["n_seed"] = g["seed"].count().values
    summ.to_csv(a.out_dir / "t12_region_loss_summary.csv", index=False, encoding="utf-8-sig")

    b = summ.set_index("model").loc["base"]
    r = summ.set_index("model").loc["region_l10"]
    lines = ["# T12 区域级监督（λ=10 ✓）× 3 seed（v3.1 ✓）", "",
             "口径 ✓：`--region-loss 10.0 --region-mode dff` ✓（锥内 **max** logit 的 BCE，`pos_weight=30` ✓）；",
             "种子 42/1/2 ✓，100 epoch ✓；指标全部是**逐视图均值** ✓（pooled 不作主指标 ✗）。", "",
             "| 指标 | 基线 | **+ 区域损失 λ=10** | Δ |",
             "|---|---|---|---|"]
    for k, name in (("view_ap", "节点 AP"), ("view_auc", "节点 AUC"),
                    ("r1", "R@1%"), ("r5", "R@5%"),
                    ("dff_view_ap", "DFF 锥 AP"), ("po_cone_view_ap", "**PO 锥 AP**")):
        bm, bs = float(b[k + "_mean"]), float(b[k + "_std"])
        rm, rs = float(r[k + "_mean"]), float(r[k + "_std"])
        rel = (rm / bm - 1) * 100 if bm else float("nan")
        lines.append(f"| {name} | {bm:.4f} ± {bs:.4f} | **{rm:.4f} ± {rs:.4f}** | {rel:+.1f}% |")
    lines += ["", f"> n=3 ✓（{int(b['n_seed'])} vs {int(r['n_seed'])}）；"
                  "节点 AP 与 PO 锥 AP 同时提升才算\"证据成团\"✓，只看节点会低估区域收益 ⚠️。"]
    (a.out_dir.parent / "t12_region_loss.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[out] {a.out_dir / 't12_region_loss_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
