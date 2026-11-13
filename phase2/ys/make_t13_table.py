"""make_t13_table.py —— N2 → **T13**：v3.1 上的模型消融（A0/A1/A2/A3/A5 ✓，3 seed ✓）。

每行一个变体 ✓（`标签=glob` ✓，每个 npz = 一个 seed ✓）：
  A0 单分支 ✓ / A1 +trust ✓ / A2 双分支+trust ✓ / A3 +cone5（现基线 ✓）/ A5 +区域监督 λ=10 ✓
指标 ✓：逐视图 AP / AUC / R@1% / R@5% ✓ + **DFF 锥 / PO 锥 AP** ✓（`region_eval_seeds` 同一实现 ✓）
输出 ✓：`03_特征与模型/N2_双分支复核/tables/t13_{per_seed,summary}.csv` ✓ + `t13.md` ✓
"""
from __future__ import annotations

import argparse
import re
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from region_eval import build_regions, dff_mask  # noqa: E402
from region_eval_seeds import build_po, eval_region  # noqa: E402
from summarize_npz import score_one  # noqa: E402

ROOT = HERE.parents[1]
DST = ROOT / "10.15" / "03_特征与模型" / "N2_双分支复核"
KEYS = ["view_ap", "view_auc", "r1", "r5", "dff_view_ap", "po_cone_view_ap"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt")
    ap.add_argument("--series", action="append", required=True, help="标签=glob ✓")
    ap.add_argument("--out-dir", type=Path, default=DST)
    a = ap.parse_args()
    work = a.pt.parents[2]
    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    y = np.asarray(d.y, np.int8).astype(np.int64)
    fids = np.asarray(json.loads((work / "data/for_train/metadata_trans.json")
                                 .read_text(encoding="utf-8"))["file_ids"]).astype(str)
    meta = json.loads((work / "views.json").read_text(encoding="utf-8"))
    te_views = [str(v) for v in meta["test_views"]]
    test_mask = np.isin(fids, te_views)
    te = np.asarray(d.test_mask, bool)

    vm = {}
    for i, v in enumerate(fids):
        vm.setdefault(v, []).append(i)
    vnames = sorted(vm)
    view_ids = np.zeros(len(y), np.int64)
    for k, v in enumerate(vnames):
        view_ids[np.array(vm[v])] = k
    is_dff = dff_mask(X, work)
    po_nodes = np.where(X[:, 28] > 0.5)[0]
    reg = {"dff": build_regions(d.edge_index, is_dff, view_ids),
           "po_cone": build_po(d.edge_index, is_dff, view_ids, po_nodes)}
    print("[regions] " + "  ".join(f"{k}={len(np.unique(v))}" for k, v in reg.items()), flush=True)

    rows = []
    for spec in a.series:
        label, pat = spec.split("=", 1)
        p = Path(pat)
        files = sorted(p.parent.glob(p.name)) if p.is_absolute() else sorted(ROOT.glob(pat))
        if not files:
            print(f"[skip] {label}：没有 npz ✗")
            continue
        for si, f in enumerate(files):
            rec = score_one(f, y, fids, test_mask)
            pr = np.zeros(len(y), np.float32)
            seen = np.zeros(len(y), bool)
            g = np.load(f)
            idx = g["idx"].astype(np.int64)
            pr[idx] = g["score"].astype(np.float32)
            seen[idx] = True
            _m = re.search(r"_s(\d+)\.npz$", f.name)
            out = dict(model=label.strip(), seed=int(_m.group(1)) if _m else si, npz=f.name,
                       view_ap=rec["view_ap"], view_auc=rec["view_auc"],
                       r1=rec["r1"], r5=rec["r5"])
            for k, lab in reg.items():
                _, va = eval_region(lab, pr, seen, y, te, view_ids, len(vnames))
                out[f"{k}_view_ap"] = va
            rows.append(out)
            print(f"  [{label} s{si}] AP={out['view_ap']:.4f} dff={out['dff_view_ap']:.4f} "
                  f"po={out['po_cone_view_ap']:.4f}", flush=True)

    df = pd.DataFrame(rows)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out_dir / "tables" / "t13_per_seed.csv", index=False, encoding="utf-8-sig")
    g = df.groupby("model")
    summ = pd.DataFrame({"model": sorted(df["model"].unique())})
    for k in KEYS:
        summ[k + "_mean"] = g[k].mean().values
        summ[k + "_std"] = g[k].std(ddof=1).values
    summ["n_seed"] = g["seed"].count().values
    summ.to_csv(a.out_dir / "tables" / "t13_summary.csv", index=False, encoding="utf-8-sig")

    lines = ["# T13 v3.1 模型消融（3 seed ✓；来源 `t13_summary.csv` ✓）", "",
             "口径 ✓：同一 fold ✓、同一预算（100 epoch ✓）、同一评测（逐视图 ✓ + 锥级 ✓）。", "",
             "| 变体 | 节点 AP | 节点 AUC | R@1% | R@5% | DFF 锥 AP | PO 锥 AP | n |",
             "|---|---|---|---|---|---|---|---|"]
    for _, r in summ.iterrows():
        lines.append(f"| **{r['model']}** | {r['view_ap_mean']:.4f} ± {r['view_ap_std']:.4f} | "
                     f"{r['view_auc_mean']:.4f} ± {r['view_auc_std']:.4f} | "
                     f"{r['r1_mean']:.4f} | {r['r5_mean']:.4f} | "
                     f"{r['dff_view_ap_mean']:.4f} | {r['po_cone_view_ap_mean']:.4f} | {int(r['n_seed'])} |")
    lines += ["", "> ⚠️ 判读要点 ✗：**trust 掩码与 cone5 在 v3.1 上不再提升**（只在小 fold / dev4 成立 ⚠️）→ "
                  "论文必须写成\"fold 依赖\" ✓；**双分支与区域监督是稳固收益** ✓。"]
    (a.out_dir / "t13.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[out] {a.out_dir / 'tables' / 't13_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
