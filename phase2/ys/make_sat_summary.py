"""make_sat_summary.py —— B03/B02b：汇总 P0 的 SAT 结果 ✓ + **真正的功能关系图**（F6 ✓）。

输入 ✓：`N4_三向泛化/tables/functional_relations_<host>.csv`（每 host 一份 ✓）
输出 ✓：
  · `tables/functional_relations.csv`（合并 ✓ + `primary` 列 ✓）
  · `tables/sat_summary.csv`（每 host×inst：覆盖率 / 可达数 / 最小可达深度 ✓）
  · `figs/F6_functional_relations.png`（**四面板** ✓：
       A 关系图（割集 → PO → 可观测点 ✓，节点颜色 = 验证状态 ✓，边注 = SAT 裁决 ✓）
       B 逐实现 verdict（条件激活 / 下游影响 ✓）
       C BMC 可达深度 ✓
       D 覆盖率 ✓）

口径 ✓：
  · 条件激活 = `decided`（钉死割集后 PO 被决定 ✓，SAT ✓）
  · 下游影响 = `influence`（割集=木马侧时 PO 被强制为 1 ✓，且关闭时不能强制 ✓）
  · 输出可观测 = **结构 BFS 实测** ✓（`n_po_reached` / `n_dff_reached` ✓，不再硬编码 ✗）
  · 验证状态 = `status`（proved/partial ✓）+ `reach_status`（BMC ✓：reachable@N / unreachable_in_horizon / unknown_timeout ✓）
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(_eqguard_path(''))
BASE = ROOT / "10.15" / "06_统一评测协议" / "N4_三向泛化"
TDIR, FIGD = BASE / "tables", ROOT / "10.15" / "07_论文图表" / "figs"


def main() -> int:
    parts = [p for p in sorted(TDIR.glob("functional_relations*.csv"))
             if p.name != "functional_relations.csv"]
    if not parts:
        print("[warn] 没有分 host 结果 ✗")
        return 1
    df = pd.concat([pd.read_csv(p, encoding="utf-8-sig") for p in parts], ignore_index=True)
    df["host"] = df["design"].astype(str).str.split("__").str[0]
    # ---- 去重 ✓：每 (host, inst, recipe) 只留**最优**一条（proved > partial > timeout > no_case ✓）
    prio = {"proved": 0, "partial": 1, "timeout": 2, "no_case": 3}
    df["_p"] = df["status"].map(lambda s: prio.get(str(s), 9))
    df = (df.sort_values(["host", "inst", "recipe", "_p"])
            .drop_duplicates(subset=["host", "inst", "recipe"], keep="first")
            .drop(columns=["_p"]))
    df["primary"] = 0
    for _, idx in df.groupby(["host", "inst", "recipe"]).groups.items():
        sub = df.loc[idx]
        best = sub.sort_values(["decided", "n_po_reached", "influence"], ascending=False).index[0]
        df.loc[best, "primary"] = 1
    cols = ["host"] + [c for c in df.columns if c != "host"]
    df = df[cols].sort_values(["host", "inst", "recipe", "primary"],
                              ascending=[True, True, True, False])
    df.to_csv(TDIR / "functional_relations.csv", index=False, encoding="utf-8-sig")

    prim = df[df["primary"] == 1]
    rows = []
    for (host, inst), g in df.groupby(["host", "inst"]):
        p = prim[(prim["host"] == host) & (prim["inst"] == inst)]
        n_impl = g["recipe"].nunique()
        rows.append(dict(
            host=host, inst=inst, n_impl=n_impl,
            n_proved=int((p["status"] == "proved").sum()),
            coverage=round(float((p["status"] == "proved").sum()) / max(n_impl, 1), 3),
            n_reachable=int((p["reach_status"] == "reachable").sum()),
            min_reach_depth=int(p.loc[p["reach_status"] == "reachable", "reach_depth"]
                                .dropna().astype(float).min()) if (p["reach_status"] == "reachable").any() else -1,
            mean_n_po=round(float(g["n_po_reached"].mean()), 2),
            mean_n_dff=round(float(g["n_dff_reached"].mean()), 2),
            targets=";".join(sorted({str(t) for t in p["target"].dropna().unique()}))))
    sm = pd.DataFrame(rows)
    sm.to_csv(TDIR / "sat_summary.csv", index=False, encoding="utf-8-sig")
    print(sm.to_string(index=False))
    make_fig(df, prim, sm)
    print(f"[out] {TDIR / 'functional_relations.csv'}（{len(df)} 行 ✓）")
    print(f"[out] {TDIR / 'sat_summary.csv'}（{len(sm)} 行 ✓）")
    print(f"[out] {FIGD / 'F6_functional_relations.png'}")
    return 0


def _rel_graph(ax, row: pd.Series) -> None:
    """Panel A ✓：割集 net → PO → 可观测点（DFF/PO 计数）✓，颜色 = 验证状态 ✓。"""
    nets = [s for s in str(row["cut_nets"]).split(";") if s and s != "nan"] or ["(cut)"]
    ok = row["status"] == "proved"
    c_state = "#2e8b57" if ok else "#8c8c8c"
    ax.set_xlim(-0.15, 3.0)
    ax.set_ylim(-0.5, max(len(nets), 2) - 0.5)
    ys = [len(nets) - 1 - i for i in range(len(nets))]
    for y, nm in zip(ys, nets):
        ax.scatter([0.0], [y], s=900, color="#40739e", zorder=3)
        ax.text(0.0, y, nm, ha="center", va="center", fontsize=6, color="white", zorder=4)
    ymid = sum(ys) / len(ys)
    ax.scatter([1.4], [ymid], s=1500, color=c_state, zorder=3)
    ax.text(1.4, ymid, f"PO\n{row['target']}", ha="center", va="center",
            fontsize=7, color="white", zorder=4)
    for y in ys:
        ax.annotate("", xy=(1.25, ymid), xytext=(0.15, y),
                    arrowprops=dict(arrowstyle="-|>", color="#40739e", lw=1.2))
    ax.text(0.75, ymid + 0.28, "cut (SAT)", fontsize=6, color="#40739e", ha="center")
    n_po, n_dff = int(row["n_po_reached"]), int(row["n_dff_reached"])
    ax.annotate("", xy=(2.6, ymid), xytext=(1.55, ymid),
                arrowprops=dict(arrowstyle="-|>", color=c_state, lw=1.4))
    ax.text(2.1, ymid + 0.3, "observable", fontsize=6, color=c_state, ha="center")
    ax.scatter([2.75], [ymid], s=700, color="#e84118", zorder=3)
    ax.text(2.75, ymid - 0.42, f"DFF×{n_dff}\nPO×{n_po}", ha="center", fontsize=6,
            color="#e84118")
    reach = str(row["reach_status"])
    depth = "" if str(row["reach_depth"]) in ("", "nan") else f"@{int(float(row['reach_depth']))}"
    ax.set_title(f"A · relation graph · {row['recipe']} ({row['kind']})\n"
                 f"activation={int(row['decided'])} influence={int(row['influence'])} "
                 f"· {reach}{depth}", fontsize=8)
    ax.axis("off")


def make_fig(df: pd.DataFrame, prim: pd.DataFrame, sm: pd.DataFrame) -> None:
    FIGD.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.2), dpi=150)

    # ---- A：关系图（挑一个 proved 的 primary ✓）
    axA = axes[0][0]
    cand = prim[prim["status"] == "proved"]
    if not cand.empty:
        _rel_graph(axA, cand.iloc[0])
    else:
        axA.text(0.5, 0.5, "no proved case", ha="center")

    # ---- B：逐实现 verdict ✓
    axB = axes[0][1]
    if not prim.empty:
        lab = [f"{r.host[:6]}/{r.inst}/{r.recipe}" for r in prim.itertuples()]
        x = range(len(prim))
        axB.bar([i - 0.2 for i in x], prim["decided"], width=0.4, color="#40739e",
                label="activation (cut decides PO)")
        axB.bar([i + 0.2 for i in x], prim["influence"], width=0.4, color="#e84118",
                label="downstream influence")
        axB.set_xticks(list(x))
        axB.set_xticklabels(lab, rotation=90, fontsize=5)
        axB.set_ylim(0, 1.15)
        axB.legend(fontsize=6, loc="lower right")
    axB.set_title("B · SAT verdict per implementation (primary target)", fontsize=8)
    axB.set_ylabel("1 = proved")

    # ---- C：BMC 可达深度 ✓
    axC = axes[1][0]
    rc = prim[prim["reach_status"] == "reachable"].copy()
    if not rc.empty:
        rc["d"] = pd.to_numeric(rc["reach_depth"], errors="coerce")
        lab = [f"{r.host[:6]}/{r.inst}/{r.recipe}" for r in rc.itertuples()]
        axC.bar(range(len(rc)), rc["d"], color="#2e8b57", width=0.55)
        axC.set_xticks(range(len(rc)))
        axC.set_xticklabels(lab, rotation=90, fontsize=5)
        axC.set_ylabel("minimal reachable depth (cycles)")
        for i, v in enumerate(rc["d"]):
            if pd.notna(v):
                axC.text(i, v + 0.5, f"{int(v)}", ha="center", fontsize=6)
    axC.set_title("C · BMC reachability of the trigger net (unconstrained init)", fontsize=8)

    # ---- D：覆盖率 ✓
    axD = axes[1][1]
    if not sm.empty:
        lab = [f"{r.host[:6]}/{r.inst}" for r in sm.itertuples()]
        axD.bar(range(len(sm)), sm["coverage"], color="#40739e", width=0.55)
        axD.set_xticks(range(len(sm)))
        axD.set_xticklabels(lab, fontsize=6)
        axD.set_ylim(0, 1.1)
        axD.set_ylabel("coverage = proved / implementations")
        for i, v in enumerate(sm["coverage"]):
            axD.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=7)
    axD.set_title("D · coverage (5 recipes: id/abc/opt proved; aig/nand via cone prober)", fontsize=8)

    fig.suptitle("F6 · SAT-verified functional relations (cut decides PO · influence · observability · "
                 "activation reachability)", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = FIGD / "F6_functional_relations.png"
    tmp = FIGD / "_F6_tmp.png"
    fig.savefig(tmp)
    try:                                   # 目标可能被看图软件占用 ✗ → 先写临时再替换 ✓
        out.unlink(missing_ok=True)
        tmp.replace(out)
    except Exception:                      # noqa: BLE001
        alt = FIGD / "F6_functional_relations_v2.png"
        tmp.replace(alt)
        print(f"[warn] F6 被占用 ✗ → 已写 {alt}")



if __name__ == "__main__":
    raise SystemExit(main())

