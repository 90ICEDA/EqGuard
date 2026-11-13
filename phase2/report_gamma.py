# -*- coding: utf-8 -*-
"""
report_gamma.py —— 把 hosts_gamma（受控跨宿主）上的所有 run 汇总成
"第七块"要求的完整指标表 + 图，**不重训**（全部从已有 run 目录里复算）。

第七块逐条落点：
  AP / Recall@1%·5% / **worst-view** / paired drift·flip /
  **benign control 误报率** ；first-hit rank 与 AnyMiss 由 loco_metrics.py
  产出后并入。并分「同 host、未见实现(fold)」与「未见 host(LOCO)」两栏。

用法：
  python phase2/report_gamma.py
  python phase2/report_gamma.py --extra-dirs results/_prefix_noPairs --tag-suffix _prefix
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

TROJAN_PAT = re.compile(r"__(inj[a-z]+)_d\d+_s\d+")
CTL_PAT = re.compile(r"__(ctl[a-z]+)_d\d+_s\d+")


def parse_args():
    ap = argparse.ArgumentParser(description="γ 受控跨宿主：完整指标汇总 + 出图")
    ap.add_argument("--results-root", type=Path, default=ROOT / "results")
    ap.add_argument("--extra-dirs", type=Path, nargs="*", default=[],
                    help="额外的 run 目录（如修复前的归档 results/_prefix_noPairs）")
    ap.add_argument("--tag-suffix", type=str, default="",
                    help="给额外目录里的 run 加后缀，便于和正式结果区分")
    ap.add_argument("--loco-ckpt-summary", type=Path,
                    default=ROOT / "results" / "phase2" / "loco_gamma" / "loco_summary_ckpt.csv")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.10" / "results")
    return ap.parse_args()


def kind_of(view: str) -> str:
    if TROJAN_PAT.search(view):
        return "trojan"
    if CTL_PAT.search(view):
        return "control"
    return "orig"


def run_meta(name: str) -> dict:
    """`hosts_gamma_seed42mode4_pred_hardb4_loco_M0_gamma_loco` -> 字段字典。"""
    ms = re.search(r"seed(\d+)", name)
    mm = re.search(r"_(M\d)_", name)
    mode = "LOCO" if "_loco_" in name else "fold"
    return {"run": name, "seed": int(ms.group(1)) if ms else -1,
            "method": mm.group(1) if mm else "?",
            "mode": mode, "stage": "after_fix"}


def collect(results_root: Path, dirs, tag_suffix: str = ""):
    per_view, per_run = [], []
    for root in [results_root] + list(dirs or []):
        for d in sorted(Path(root).glob("hosts_gamma_seed*mode4_*_M[0-3]_gamma*")):
            if "smoke" in d.name or not d.is_dir():
                continue
            vp = d / "variant_level_summary.csv"
            cp = d / "circuit_level_summary.csv"
            if not vp.exists():
                continue
            m = run_meta(d.name)
            if Path(root) != Path(results_root):
                m["stage"] = "before_fix" + tag_suffix
            df = pd.read_csv(vp)
            df["kind"] = df["View"].map(kind_of)
            df["method"], df["mode"], df["seed"] = m["method"], m["mode"], m["seed"]
            df["run"] = d.name
            df["stage"] = m["stage"]
            per_view.append(df)
            row = dict(m)
            if cp.exists():
                mac = pd.read_csv(cp)
                mac = mac[mac["Circuit"] == "MACRO_MEAN"]
                if len(mac):
                    for k in ("Paired_MAE", "Flip_Rate", "Spearman_Corr",
                              "Anchor_AP_Orig", "Anchor_AP_Trans", "Anchor_Coverage"):
                        if k in mac.columns:
                            row[k] = float(mac.iloc[0][k])
            t = df[(df["Type"] == "TRANS") & (df["kind"] == "trojan")]
            c = df[(df["Type"] == "TRANS") & (df["kind"] == "control")]
            if len(t):
                row.update({"n_trojan_views": len(t),
                            "AP_Trojan": float(t["AP"].mean()),
                            "AP_Trojan_WORSTVIEW": float(t["AP"].min()),   # worst-view
                            "Recall@1%_Trojan": float(t["Recall@1%"].mean()),
                            "Recall@5%_Trojan": float(t["Recall@5%"].mean()),
                            "FPR_Trojan": float(t["FPR"].mean())})
            if len(c):
                row.update({"n_control_views": len(c),
                            "FPR_BenignControl": float(c["FPR"].mean()),   # 合法对照误报率
                            "FPR_BenignControl_WORST": float(c["FPR"].max()),
                            "AP_BenignControl": float(c["AP"].mean())})
            per_run.append(row)
    return (pd.concat(per_view, ignore_index=True) if per_view else pd.DataFrame(),
            pd.DataFrame(per_run))


MKEYS = ["AP_Trojan", "AP_Trojan_WORSTVIEW", "Recall@1%_Trojan", "Recall@5%_Trojan",
         "FPR_Trojan", "FPR_BenignControl", "FPR_BenignControl_WORST", "AP_BenignControl",
         "Paired_MAE", "Flip_Rate", "Spearman_Corr", "Anchor_AP_Orig", "Anchor_AP_Trans"]


def fig_bars(per_run: pd.DataFrame, metric: str, ylabel: str, title: str, path: Path) -> None:
    """per_run 是**数值**表（每 run 一行），此处按 method×mode 取均值 + 跨 seed 的 std 误差棒。"""
    if metric not in per_run.columns:
        return
    piv = per_run.pivot_table(index="method", columns="mode", values=metric, aggfunc="mean")
    err = per_run.pivot_table(index="method", columns="mode", values=metric,
                              aggfunc=lambda s: float(np.nanstd(s)))
    if piv.empty:
        return
    ax = piv.plot(kind="bar", yerr=err, capsize=3, figsize=(6.4, 4.0), rot=0)
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=9)
    ax.grid(axis="y", alpha=.3)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def fig_box(per_view: pd.DataFrame, path: Path) -> None:
    d = per_view[per_view["Type"] == "TRANS"].copy()
    if d.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    for ax, (metric, ylab) in zip(axes, [("AP", "per-view AP"), ("FPR", "per-view FPR")]):
        labels, data = [], []
        for mode in ("fold", "LOCO"):
            for meth in sorted(d["method"].unique()):
                for kd in ("trojan", "control"):
                    v = d[(d["mode"] == mode) & (d["method"] == meth) & (d["kind"] == kd)][metric]
                    if len(v):
                        labels.append(f"{meth}|{mode[:4]}|{kd[:5]}")
                        data.append(v.dropna().values)
        if data:
            ax.boxplot(data, labels=labels, showfliers=False)
            ax.set_ylabel(ylab)
            ax.grid(axis="y", alpha=.3)
            ax.tick_params(axis="x", labelsize=6, rotation=60)
    fig.suptitle("Trojan vs legal-control views (per-view distribution)", fontsize=10)
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    per_view, per_run = collect(args.results_root, args.extra_dirs, args.tag_suffix)
    if per_run.empty:
        print("[WARN] 没找到任何 hosts_gamma run")
        return 1
    per_run = per_run.sort_values(["stage", "method", "mode", "seed"])
    per_run.to_csv(args.out_dir / "gamma_by_run.csv", index=False, encoding="utf-8-sig")
    per_view.to_csv(args.out_dir / "gamma_per_view.csv", index=False, encoding="utf-8-sig")

    use = [k for k in MKEYS if k in per_run.columns]
    g = per_run.groupby(["stage", "method", "mode"])[use].agg(["mean", "std", "count"])
    summary = pd.DataFrame({k: (g[k]["mean"].round(4).astype(str) + " ± "
                               + g[k]["std"].round(4).astype(str)) for k in use})
    summary["n_seed"] = g[use[0]]["count"]
    summary.to_csv(args.out_dir / "gamma_summary.csv", encoding="utf-8-sig")
    print("=== γ 汇总（mean ± std；stage=after_fix 为正式结果）===")
    print(summary.to_string())

    # ---- LOCO 的 first-hit / AnyMiss（由 loco_metrics.py 用逐电路 ckpt 复算）----
    if args.loco_ckpt_summary.exists():
        lk = pd.read_csv(args.loco_ckpt_summary)
        lk.to_csv(args.out_dir / "gamma_firsthit_loco.csv", index=False, encoding="utf-8-sig")
        print("\n=== LOCO first-hit / AnyMiss / 检查预算（逐电路 ckpt，宏平均）===")
        cols = [c for c in ("group", "AP_T", "Recall@5%", "FirstHitRank_Norm", "AnyMiss@5%",
                            "InspectionCost", "Paired_MAE", "Flip_Rate") if c in lk.columns]
        print(lk[cols].to_string(index=False))

    # ---- 图（只用 stage=after_fix 的正式 run）----
    stable = per_run[per_run["stage"] == "after_fix"]
    fig_bars(stable, "AP_Trojan", "AP over Trojan views",
             "Trojan-view AP — fold(seen host) vs LOCO(unseen host)",
             args.out_dir / "fig_gamma_ap_trojan.png")
    fig_bars(stable, "FPR_BenignControl", "FPR over legal-control views",
             "False-positive rate on legal low-activity controls",
             args.out_dir / "fig_gamma_fpr_benign.png")
    fig_bars(stable, "AP_Trojan_WORSTVIEW", "worst-view AP over Trojan views",
             "Worst-view AP (min over Trojan views)",
             args.out_dir / "fig_gamma_worstview.png")
    fig_box(per_view[per_view["stage"] == "after_fix"] if "stage" in per_view.columns else per_view,
            args.out_dir / "fig_gamma_per_view_box.png")
    print(f"\n[导出] {args.out_dir}"
          "（gamma_by_run.csv / gamma_summary.csv / gamma_per_view.csv / fig_*.png）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

