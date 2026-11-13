"""make_g10_seedbars.py —— G10：**多种子**指标的均值 ± std（论文误差棒 ✓）。

口径与 `summarize_npz.py` 完全一致 ✓：
  * 每个 npz = 一个 seed 的 `--dump-scores` 产物 ✓；
  * 指标 = **逐视图** AP / AUC / Recall@1% / Recall@5% 的均值 ✓（不是 pooled ✗ ——
    pooled AP 对"视图间分数是否可比"极其敏感 ✗，dev4 上 pooled 0.0019 vs per-view 0.0478 ✓）。

用法（每个 npz 一个 seed ✓）：
  python -X utf8 phase2/ys/make_g10_seedbars.py \
    --pt generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt \
    --series "EquiGuard=_devcfg/gnn_v31_s*.npz" \
    --out 10.15/07_论文图表/G10_seed_bars.png \
    --csv 10.15/07_论文图表/tables/G10_seed_bars.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from summarize_npz import score_one  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "10.15" / "07_论文图表"
METRICS = [("view_ap", "Per-view AP"), ("view_auc", "Per-view ROC-AUC"),
           ("r1", "Recall@1%"), ("r5", "Recall@5%")]


def load_labels(pt: Path, work: Path):
    d = torch.load(pt, map_location="cpu", weights_only=False, mmap=True)
    y = np.asarray(d.y, np.int8).astype(np.int64)
    fids = json.loads((work / "data/for_train/metadata_trans.json")
                      .read_text(encoding="utf-8"))["file_ids"]
    meta = json.loads((work / "views.json").read_text(encoding="utf-8"))
    if isinstance(meta, dict) and "test_views" in meta:
        test_views = set(meta["test_views"])
    elif isinstance(meta, dict):
        test_views = {k for k, v in meta.items() if str(v).lower() == "test"}
    else:
        test_views = {r["view"] for r in meta if str(r.get("split", "")).lower() == "test"}
    test_mask = np.isin(np.asarray(fids), list(test_views)) if test_views else np.ones(len(fids), bool)
    return y, fids, test_mask


def expand(spec: str) -> tuple[str, list[Path]]:
    if "=" not in spec:
        raise SystemExit(f"[ERROR] --series 需要 `标签=glob` ✗ 收到：{spec}")
    label, pat = spec.split("=", 1)
    pat = pat.strip().replace("\\", "/")
    p = Path(pat)
    files = sorted(p.parent.glob(p.name)) if p.is_absolute() else sorted(Path.cwd().glob(pat))
    if not files:
        raise SystemExit(f"[ERROR] 没有匹配到 npz ✗ {spec}")
    return label.strip(), files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path, required=True)
    ap.add_argument("--series", action="append", required=True, help="标签=glob ✓ 可重复 ✓")
    ap.add_argument("--out", type=Path, default=OUT / "G10_seed_bars.png")
    ap.add_argument("--csv", type=Path, default=OUT / "tables" / "G10_seed_bars.csv")
    a = ap.parse_args()

    work = a.pt.parents[2]
    y, fids, test_mask = load_labels(a.pt, work)

    rows = []
    for spec in a.series:
        label, files = expand(spec)
        for f in files:
            rec = score_one(f, y, fids, test_mask)
            rec["series"] = label
            rec["seed_npz"] = f.name
            rows.append(rec)
            print(f"  [seed] {label:<12s} {f.name:<28s} "
                  f"view_AP={rec['view_ap']:.4f} AUC={rec['view_auc']:.4f} "
                  f"R@5%={rec['r5']:.4f}")
    df = pd.DataFrame(rows)
    a.csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.csv, index=False, encoding="utf-8-sig")

    labels = list(dict.fromkeys(df["series"]))
    fig, axs = plt.subplots(1, len(METRICS), figsize=(12.5, 3.6))
    for ax, (key, title) in zip(axs, METRICS):
        xs = np.arange(len(labels))
        vals = [df.loc[df["series"] == lb, key].to_numpy(float) for lb in labels]
        means = [float(np.nanmean(v)) for v in vals]
        stds = [float(np.nanstd(v, ddof=1)) if len(v) > 1 else 0.0 for v in vals]
        ax.bar(xs, means, yerr=stds, capsize=4, width=0.55,
               color="#4C78A8", edgecolor="black", linewidth=0.6)
        for xi, (m, v) in enumerate(zip(means, vals)):
            ax.text(xi, m + (max(stds) if max(stds) > 0 else 0.02) + 0.01, f"{m:.3f}",
                    ha="center", fontsize=8)
        ax.set_xticks(xs)
        ax.set_xticklabels([f"{lb}\n(n={len(v)})" for lb, v in zip(labels, vals)], fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle("G10 — seed variance (per-view means, mean ± std)", fontsize=11)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(a.out, dpi=150)
    plt.close(fig)

    print("\n[汇总] mean ± std（ddof=1 ✓）")
    for lb in labels:
        sub = df[df["series"] == lb]
        txt = "  ".join(f"{k}={sub[k].mean():.4f}±{sub[k].std(ddof=1) if len(sub) > 1 else 0:.4f}"
                        for k, _ in METRICS)
        print(f"  {lb:<14s} n={len(sub)}  {txt}")
    print(f"\n[fig] {a.out}\n[csv] {a.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
