"""make_netlist_compare_fig.py —— 第 5 块 ① **综合前后网表对比图** ✓（F0 ✓）。

素材 ✓（全部已入库 ✓，只读 ✓）：
  · `10.15/01_数据与标签/A1_变换统计/tables/a1_v3_views.csv` ✓ 逐视图 418 行 ✓
    （`nodes_orig / nodes_trans / node_ratio / transported_cover / cec_status` ✓）
  · `.../a1_by_op.csv` ✓ 逐配方中位数 ✓

口径 ✓：以 `ys_id` 为**基线** ✓（同源设计 ✓），比较其它配方的
  ① **门数比** `nodes_trans / nodes_orig` ✓（>1 = 综合后膨胀 ✓）
  ② **标签可溯源覆盖** `transported_cover` ✓（越低 = 标签越难搬 ✓）
  ③ **CEC 通过率** ✓（必须 100% ✓ 否则该配方不可用 ✗）
输出：`10.15/07_论文图表/figs/F0_netlist_compare.png` ✓ + `tables/netlist_compare.csv` ✓
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
A1 = ROOT / "10.15" / "01_数据与标签" / "A1_变换统计" / "tables"
OUT = ROOT / "10.15" / "07_论文图表"
ORDER = ["ys_id", "ys_rt", "ys_aig", "ys_opt", "ys_nand", "ys_abc"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=OUT)
    a = ap.parse_args()

    v = pd.read_csv(A1 / "a1_v3_views.csv", encoding="utf-8-sig")
    # ⚠️ 该表 `op` 列存的是**视图类型**（a4ctldead / ctldup / injalpha… ✗），
    #    配方要从 `view` 名尾部取 ✓（`…__keepcur__ys_abc` → `ys_abc` ✓）
    v["recipe"] = v["view"].astype(str).str.split("__").str[-1]
    v["kind"] = np.where(v["view"].astype(str).str.contains("inj|a4trojan"),
                         "trojan", "control")
    v = v[v["recipe"].isin(ORDER)].copy()
    v["node_ratio"] = pd.to_numeric(v["node_ratio"], errors="coerce")
    v["transported_cover"] = pd.to_numeric(v["transported_cover"], errors="coerce")
    v["cec_ok"] = v["cec_status"].astype(str).str.upper().eq("PASS")

    rows = []
    for op in ORDER:
        d = v[v["recipe"] == op]
        if d.empty:
            continue
        rows.append(dict(recipe=op, views=len(d),
                         nodes_orig_med=float(d["nodes_orig"].median()),
                         nodes_trans_med=float(d["nodes_trans"].median()),
                         ratio_med=float(d["node_ratio"].median()),
                         ratio_p10=float(d["node_ratio"].quantile(.10)),
                         ratio_p90=float(d["node_ratio"].quantile(.90)),
                         cover_med=float(d["transported_cover"].median()),
                         cover_p10=float(d["transported_cover"].quantile(.10)),
                         cover_p90=float(d["transported_cover"].quantile(.90)),
                         cec_rate=float(d["cec_ok"].mean())))
    t = pd.DataFrame(rows)
    t["vs_id_ratio"] = t["ratio_med"] / float(t.loc[t.recipe == "ys_id", "ratio_med"].iloc[0])
    t["vs_id_cover"] = t["cover_med"] / float(t.loc[t.recipe == "ys_id", "cover_med"].iloc[0])
    print(t.round(4).to_string(index=False))

    (a.out_dir / "tables").mkdir(parents=True, exist_ok=True)
    t.to_csv(a.out_dir / "tables" / "netlist_compare.csv", index=False, encoding="utf-8-sig")

    # ---- 图 ✓（两面板 ✓ 英文 ✓）----
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    x = np.arange(len(t))
    lab = [r.replace("ys_", "") for r in t["recipe"]]
    for ax, col, lo, hi, ylab, ttl in (
        (axes[0], "ratio_med", "ratio_p10", "ratio_p90",
         "gate-count ratio  (trans / orig)", "(a) Netlist size after synthesis"),
        (axes[1], "cover_med", "cover_p10", "cover_p90",
         "label traceability  (transported / nodes)", "(b) How much label survives"),
    ):
        med = t[col].to_numpy()
        err = np.vstack([med - t[lo].to_numpy(), t[hi].to_numpy() - med])
        cols = ["#7f8fa6" if r == "ys_id" else "#40739e" for r in t["recipe"]]
        ax.bar(x, med, color=cols, width=0.62, yerr=err, capsize=3,
               error_kw=dict(lw=0.9, ecolor="#555555"))
        for xi, m, cv in zip(x, med, t["cec_rate"]):
            ax.text(xi, m, f"{m:.2f}", ha="center", va="bottom", fontsize=8)
            if cv < 1.0:
                ax.text(xi, 0.02, f"CEC {cv:.0%}", ha="center", va="bottom",
                        fontsize=7, color="#c0392b")
        ax.set_xticks(x)
        ax.set_xticklabels(lab, fontsize=9)
        ax.set_ylabel(ylab, fontsize=9)
        ax.set_title(ttl, fontsize=10, weight="bold")
        ax.grid(axis="y", ls=":", lw=0.5, alpha=0.6)
        if col == "cover_med":
            ax.set_ylim(0, 1.05)
    fig.suptitle(
        "F0  Pre- vs post-synthesis netlists (same source design; ys_id = baseline)\n"
        f"bars = median, whiskers = p10-p90, n per recipe in table; "
        f"CEC pass required (100% except where annotated)",
        fontsize=9.5)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    p = a.out_dir / "figs" / "F0_netlist_compare.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=170)
    plt.close(fig)
    print("[out]", p)
    print("[out]", a.out_dir / "tables" / "netlist_compare.csv")

    # ---- F0b ✓：逻辑深度（yosys `ltp` ✓）+ 名字存活率 ✓（`netlist_depth.csv` ✓ 存在才画 ✓）----
    dp = a.out_dir / "tables" / "netlist_depth.csv"
    if dp.exists():
        dd = pd.read_csv(dp, encoding="utf-8-sig")
        dd = dd[dd["depth"] > 0]
        if not dd.empty:
            g = (dd.groupby("recipe")
                 .agg(depth_med=("depth", "median"),
                      depth_p10=("depth", lambda s: s.quantile(.10)),
                      depth_p90=("depth", lambda s: s.quantile(.90)),
                      nodes_med=("nodes", "median"),
                      inst_keep=("inst_keep", "median"),
                      port_keep=("port_keep", "median"),
                      n=("depth", "count"))
                 .reindex([r for r in ORDER if r in set(dd["recipe"])]).dropna())
            g.to_csv(a.out_dir / "tables" / "netlist_depth_summary.csv",
                     encoding="utf-8-sig")
            fig, ax = plt.subplots(figsize=(7.2, 4.0))
            x = np.arange(len(g))
            med = g["depth_med"].to_numpy()
            err = np.vstack([med - g["depth_p10"].to_numpy(),
                             g["depth_p90"].to_numpy() - med])
            cols = ["#7f8fa6" if r == "ys_id" else "#40739e" for r in g.index]
            ax.bar(x, med, color=cols, width=0.62, yerr=err, capsize=3,
                   error_kw=dict(lw=0.9, ecolor="#555555"))
            for xi, m, hi, nd, ik, pk, n in zip(x, med, g["depth_p90"], g["nodes_med"],
                                                g["inst_keep"], g["port_keep"], g["n"]):
                ax.text(xi, hi + 0.02 * med.max(), f"{m:.0f}",
                        ha="center", va="bottom", fontsize=9)
                ax.text(xi, m * 0.42,
                        f"cells≈{nd:.0f}\nname-keep\n{ik:.0%} / {pk:.0%}\nn={int(n)}",
                        ha="center", va="center", fontsize=6.8, color="white")
            ax.set_xticks(x)
            ax.set_xticklabels([r.replace("ys_", "") for r in g.index], fontsize=9)
            ax.set_ylabel("logic depth  (longest topological path, levels)", fontsize=9)
            ax.set_title("F0b  Synthesis changes the depth, not the names\n"
                         "bars = median (whiskers = p10-p90);  "
                         "name-keep = instance / port names vs clean-ys_id",
                         fontsize=9.2, weight="bold")
            ax.grid(axis="y", ls=":", lw=0.5, alpha=0.6)
            ax.margins(y=0.22)
            fig.tight_layout()
            p2 = a.out_dir / "figs" / "F0b_netlist_depth.png"
            fig.savefig(p2, dpi=170)
            plt.close(fig)
            print("[out]", p2)
            print("[out]", a.out_dir / "tables" / "netlist_depth_summary.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
