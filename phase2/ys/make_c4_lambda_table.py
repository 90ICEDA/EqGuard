"""make_c4_lambda_table.py —— C4：一致性权重 λ 的消融表（dev4，seed 42 ✓）。

口径与 `summarize_npz.py` 完全一致 ✓（逐视图 AP/AUC/R@k 的均值 ✓；pooled 仅参考 ⚠️）。
输入：`_devcfg/dev4_lc{0,0p3,1p0,3p0}.npz` + `_devcfg/dev4_funconly.npz` ✓
输出：`C4_lambda_table.csv` + `C4_lambda_table.md` ✓（λ 从文件名解析 ✓，不手填 ✓）。

用法：
  python -X utf8 phase2/ys/make_c4_lambda_table.py \
    --pt generate_trans/folds/_dev4/data/processed/trans_graph.pt
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from summarize_npz import score_one  # noqa: E402

ROOT = HERE.parents[1]
COLS = ["view_ap", "view_auc", "r1", "r5", "pooled_ap", "pooled_auc"]


def load_labels(pt: Path, work: Path):
    d = torch.load(pt, map_location="cpu", weights_only=False, mmap=True)
    y = np.asarray(d.y, np.int8).astype(np.int64)
    fids = json.loads((work / "data/for_train/metadata_trans.json")
                      .read_text(encoding="utf-8"))["file_ids"]
    meta = json.loads((work / "views.json").read_text(encoding="utf-8"))
    if isinstance(meta, dict) and "test_views" in meta:
        tv = set(meta["test_views"])
    elif isinstance(meta, dict):
        tv = {k for k, v in meta.items() if str(v).lower() == "test"}
    else:
        tv = {r["view"] for r in meta if str(r.get("split", "")).lower() == "test"}
    return y, fids, (np.isin(np.asarray(fids), list(tv)) if tv else np.ones(len(fids), bool))


def lam_of(name: str) -> float:
    """`dev4_lc0p3.npz` → 0.3 ✓；`dev4_funconly.npz` → nan ✓。"""
    m = re.search(r"lc(\d+)p(\d+)", name)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    m = re.search(r"lc(\d+)(?![\dp])", name)
    return float(m.group(1)) if m else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/_dev4/data/processed/trans_graph.pt")
    ap.add_argument("--dir", type=Path, default=ROOT / "_devcfg")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.15/03_特征与模型/C4_等价一致性")
    a = ap.parse_args()
    work = a.pt.parents[2]
    y, fids, test_mask = load_labels(a.pt, work)

    rows = []
    for f in sorted(a.dir.glob("dev4_lc*.npz")) + sorted(a.dir.glob("dev4_funconly.npz")):
        if not f.name.startswith(("dev4_lc", "dev4_funconly")):
            continue
        rec = score_one(f, y, fids, test_mask)
        rec["lambda"] = lam_of(f.name)
        rec["variant"] = "func-only" if "funconly" in f.name else "dual+consistency"
        rows.append(rec)
        print(f"  [seed42] {f.name:<20s} lambda={rec['lambda']} view_AP={rec['view_ap']:.4f} "
              f"AUC={rec['view_auc']:.4f} R@5%={rec['r5']:.4f}")
    if not rows:
        raise SystemExit(f"[ERROR] 没找到 npz ✗ {a.dir}")
    df = pd.DataFrame(rows).sort_values(["variant", "lambda"])
    a.out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out_dir / "C4_lambda_table.csv", index=False, encoding="utf-8-sig")

    lines = ["# C4 —— 一致性权重 λ 消融（dev4，seed 42 ✓）", "",
             "口径 ✓：逐视图 AP/AUC/R@k 的均值（pooled 仅参考 ⚠️）；`λ=0` = 不加一致性损失 ✓。", "",
             "| 变体 | λ | view_AP | view_AUC | R@1% | R@5% | pooled_AP ⚠️ |",
             "|---|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        lam = "—" if pd.isna(r["lambda"]) else f"{r['lambda']:.1f}"
        lines.append(f"| {r['variant']} | {lam} | {r['view_ap']:.4f} | {r['view_auc']:.4f} | "
                     f"{r['r1']:.4f} | {r['r5']:.4f} | {r['pooled_ap']:.4f} |")
    dual = df[df["variant"] == "dual+consistency"].dropna(subset=["lambda"])
    if len(dual) > 1:
        best = dual.loc[dual["view_ap"].idxmax()]
        lines += ["", f"> 最佳 λ = **{best['lambda']:.1f}**（view_AP {best['view_ap']:.4f}）✓；"
                      f"λ=0 为 {float(dual[dual['lambda'] == 0]['view_ap'].iloc[0]):.4f} ✓。"]
    (a.out_dir / "C4_lambda_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n" + "\n".join(lines))
    print(f"\n[导出] {a.out_dir / 'C4_lambda_table.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
