# -*- coding: utf-8 -*-
"""
feature_audit_yosys.py —— 第三块：用 **yosys 生成的等价网表** 做特征审视。

目标（任务书第三块 + 你的要求）：
  找出「**等价变换后变化不大**、但**插入木马后变化大**」的特征。

做法：
  1. 对每个设计（干净基底 / 木马视图 / 合法对照）取原网表 + K 个 yosys 等价变体
     （变体已逐个 CEC 验证通过，见 `generate_trans/yosys_netlists/ys_manifest.csv`）；
  2. 每个网表用 `phase2/ys/netlist_feats.py` 抽「结构 + 功能」特征（含信号概率、
     toggle rate、SCOAP 可控性/可观测性、布尔影响度、支撑集、到输出/寄存器的可达性）；
  3. **EquivDrift(f)**：原网表与各变体之间，f 的**稳健分位数漂移**
     （只用有限值；`INF` 与语义未知的比例单独记入诊断表，不静默当 0）；
  4. **TrojanDelta(f)**：木马门集合 vs 其 1-hop 邻域的特征差（按 pooled IQR 归一）；
     对 40 个**合法对照**用同样口径算一遍 → **负对照**（它大说明测的是"插入痕迹"而非"木马"）；
  5. `selectivity = TrojanDelta / (EquivDrift + eps)` → 排序，出 CSV + 图。

用法：
  py phase2/ys/feature_audit_yosys.py --hosts rs232t1000,s15850t100
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from phase2.netlist_lib import load_library, parse_netlist  # noqa: E402
from phase2.ys import netlist_feats as NF  # noqa: E402

VALI_LIB = Path("C:/Users/91344/Desktop/GraphSAINT/GraphSAINT-train/vali/verilog_lib.v")
HOSTS = ROOT / "generate_trans" / "hosts"
YS = ROOT / "generate_trans" / "yosys_netlists"
Q = [0.05, 0.25, 0.5, 0.75, 0.95]


def parse_args():
    ap = argparse.ArgumentParser(description="第三块：yosys 等价网表上的特征审视")
    ap.add_argument("--hosts", type=str, default="")
    ap.add_argument("--recipes", type=str, default="id,opt,abc,aig,nand")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.10" / "results")
    ap.add_argument("--max-designs", type=int, default=0,
                    help=">0 时每个 host 只取前 N 个设计（快速冒烟用）")
    ap.add_argument("--hosts-root", type=Path, default=HOSTS,
                    help="感染视图目录（B 型用 generate_trans/hosts_bt）")
    ap.add_argument("--ys-root", type=Path, default=YS,
                    help="yosys 等价网表目录（B 型用 yosys_netlists_beta）")
    return ap.parse_args()


def load_prov():
    """{view_stem: [插入门实例名]}，木马与对照一起。"""
    out = {}
    for pj in HOSTS.glob("*/provenance.json"):
        for rec in json.loads(pj.read_text(encoding="utf-8")):
            out[rec.get("view", "")] = {"kind": rec.get("kind"),
                                        "gates": rec.get("new_gates") or [],
                                        "ctl_type": rec.get("ctl_type")}
    return out


def designs(hosts, recipes, max_n):
    """-> [(host, kind, stem, gold_path, [variant_paths...])]"""
    man = YS / "ys_manifest.csv"
    m = pd.read_csv(man) if man.exists() else pd.DataFrame()
    if len(m):
        m = m[m["cec"].astype(str).str.contains("PASS", na=False)]
    got = {}
    for _i, r in m.iterrows():
        got.setdefault((r["host"], r["stem"]), {})[r["recipe"]] = True
    out = []
    for host in hosts:
        rows = []
        base = HOSTS / host / "base"
        for f in sorted(base.glob("*_clean.v")):
            rows.append((host, "clean", f.stem, f))
        for f in sorted((HOSTS / host).glob("*.v")):
            s = f.stem
            if "__inj" in s:
                rows.append((host, "trojan", s, f))
            elif "__ctl" in s:
                rows.append((host, "control", s, f))
        if max_n > 0:
            rows = rows[:max_n]
        for host_, kind, stem, f in rows:
            vs = [YS / host_ / f"{stem}__ys_{r}.v" for r in recipes]
            vs = [v for v in vs if v.exists()]
            if vs:
                out.append((host_, kind, stem, f, vs))
    return out


def main() -> int:
    global HOSTS, YS
    args = parse_args()
    HOSTS, YS = args.hosts_root.resolve(), args.ys_root.resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    lib, sem = load_library(VALI_LIB), NF.load_cell_semantics(VALI_LIB)
    prov = load_prov()
    hosts = ([h.strip() for h in args.hosts.split(",") if h.strip()]
             or sorted({p.parent.name for p in YS.glob("*/*.v")}))
    recipes = [r.strip() for r in args.recipes.split(",") if r.strip()]
    ds = designs(hosts, recipes, args.max_designs)
    print(f"[INFO] hosts={hosts} 设计数={len(ds)}")
    if not ds:
        print("[ERROR] 没有可用的 (设计, 变体)")
        return 1

    eq = {f: [] for f in NF.FEATS}
    td, cd = {f: [] for f in NF.FEATS}, {f: [] for f in NF.FEATS}
    diag, per_design = [], []
    for host, kind, stem, gold, variants in ds:
        nl_gold = parse_netlist(gold, lib)
        gd, gi = feats_of(gold, lib, sem)
        gates = NF.build_circuit(nl_gold, sem)[0]
        if not len(gd):
            continue
        base_scale = {f: iqr(gd[f]) for f in NF.FEATS if f in gd.columns}
        for v in variants:
            vd, vi = feats_of(v, lib, sem)
            if not len(vd):
                continue
            for f in NF.FEATS:
                if f not in gd.columns or f not in vd.columns:
                    continue
                a, b = qvec(gd[f]), qvec(vd[f])
                s = base_scale.get(f, np.nan)
                if a is None or b is None or not s or s <= 0:
                    continue
                eq[f].append(float(np.abs(a - b).mean() / (s + 1e-6)))
            diag.append({"host": host, "kind": kind, "stem": stem,
                         "which": Path(v).stem.split("__ys_")[-1],
                         "n_gates": vi["n_gates"], "n_unknown_sem": vi["n_unknown_sem"],
                         "frac_co_inf": float((vd["co"] >= NF.INF / 2).mean()),
                         "frac_cc_inf": float((vd["cc0"] >= NF.INF / 2).mean()),
                         "frac_op_unknown": float(vd["op_unknown"].mean())})
        diag.append({"host": host, "kind": kind, "stem": stem, "which": "gold",
                     "n_gates": gi["n_gates"], "n_unknown_sem": gi["n_unknown_sem"],
                     "frac_co_inf": float((gd["co"] >= NF.INF / 2).mean()),
                     "frac_cc_inf": float((gd["cc0"] >= NF.INF / 2).mean()),
                     "frac_op_unknown": float(gd["op_unknown"].mean())})
        pv = prov.get(stem, {})
        names = pv.get("gates") or []
        ti, ni = masks(gates, names) if names else (None, None)
        if ti:
            for f in NF.FEATS:
                if f not in gd.columns:
                    continue
                a = qvec(gd[f].values[ti])
                b = qvec(gd[f].values[ni]) if ni else None
                s = base_scale.get(f, np.nan)
                if a is None or b is None or not s or s <= 0:
                    continue
                x = float(abs(a[2] - b[2]) / (s + 1e-6))     # 中位数差 / pooled IQR
                (td if kind == "trojan" else cd)[f].append(x)
            per_design.append({"host": host, "kind": kind, "stem": stem,
                               "n_prov_gates": len(names), "n_marked": len(ti),
                               "n_neighbor": len(ni or [])})
    return summarise(args, eq, td, cd, diag, per_design)


def qvec(v, qs=Q):
    """只用有限值算分位数；没有有限值返回 None（INF 长尾不给统计量添乱）。"""
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    v = v[v < NF.INF / 2]
    if v.size == 0:
        return None
    return np.quantile(v, qs)


def iqr(v):
    q = qvec(v, [0.25, 0.75])
    return (q[1] - q[0]) if q is not None else np.nan


def masks(gates, names):
    """木马/对照门集合 与 其 1-hop 邻域（用真实图，不靠网名猜测）。"""
    idx = [i for i, g in enumerate(gates) if any(g.name.startswith(p) for p in names)]
    if not idx:
        return None, None
    out_nets = {gates[i].out for i in idx}
    in_nets = {x for i in idx for x in gates[i].ins}
    st = set(idx)
    nb = [j for j, g in enumerate(gates)
          if j not in st and (g.out in in_nets or any(x in out_nets for x in g.ins))]
    return idx, nb


GROUP = {}
for _f in ("sp", "toggle_rate", "cc0", "cc1", "co", "influence_in", "fanin_support",
           "reach_po", "reach_dff"):
    GROUP[_f] = "functional"
for _f in ("depth", "hops_to_po", "n_inputs", "degree", "fanin_2hop", "fanout_2hop",
           "is_ff", "is_pi", "is_po"):
    GROUP[_f] = "structural"
for _f in ("op_and", "op_or", "op_xor", "op_not", "op_mux", "op_cat", "op_unknown"):
    GROUP[_f] = "gate_type"
for _f in ("cut_sp", "cut_entropy", "cut_reliability", "cut_bd_sum", "cut_bd_max",
           "cut_n_leaves"):
    GROUP[_f] = "functional_cut"


def feats_of(path, lib, sem):
    nl = parse_netlist(path, lib)
    gates, rows, info = NF.circuit_features(nl, sem)
    d = pd.DataFrame(rows)
    if len(d):
        d["gname"] = [g.name for g in gates]
    return d, info


def summarise(args, eq, td, cd, diag, per_design) -> int:
    rows = []
    for f in NF.FEATS:
        if f not in GROUP:
            continue
        rows.append({"feature": f, "group": GROUP[f],
                     "equiv_drift": float(np.nanmean(eq[f])) if eq[f] else np.nan,
                     "equiv_drift_std": float(np.nanstd(eq[f])) if eq[f] else np.nan,
                     "trojan_delta": float(np.nanmean(td[f])) if td[f] else np.nan,
                     "ctrl_delta": float(np.nanmean(cd[f])) if cd[f] else np.nan,
                     "n_equiv": len(eq[f]), "n_delta": len(td[f]), "n_ctrl": len(cd[f])})
    t = pd.DataFrame(rows)
    t["selectivity"] = t["trojan_delta"] / (t["equiv_drift"] + 0.02)
    t["sel_vs_ctrl"] = (t["trojan_delta"] - t["ctrl_delta"]) / (t["equiv_drift"] + 0.02)
    t = t.sort_values("selectivity", ascending=False)
    t.to_csv(args.out_dir / "ys_feature_table.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(diag).to_csv(args.out_dir / "ys_diag.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(per_design).to_csv(args.out_dir / "ys_per_design.csv", index=False,
                                    encoding="utf-8-sig")
    print("\n=== 特征表（按 selectivity 排序；equiv_drift 小、delta 大 ⇒ 好）===")
    print(t[["feature", "group", "equiv_drift", "trojan_delta", "ctrl_delta",
             "selectivity", "sel_vs_ctrl", "n_equiv"]].round(4).to_string(index=False))

    ok = t.dropna(subset=["equiv_drift", "trojan_delta"])
    if len(ok):
        fig, ax = plt.subplots(figsize=(7.8, 5.4))
        for grp, sub in ok.groupby("group"):
            ax.scatter(sub["equiv_drift"], sub["trojan_delta"], label=grp, s=42)
            for _i, r in sub.iterrows():
                ax.annotate(r["feature"], (r["equiv_drift"], r["trojan_delta"]),
                            fontsize=6, xytext=(2, 2), textcoords="offset points")
        ax.set_xlabel("EquivDrift (lower = stable under yosys rewriting)")
        ax.set_ylabel("TrojanDelta (higher = Trojan-sensitive)")
        ax.set_title("Block 3: equivalence stability vs Trojan sensitivity", fontsize=10)
        ax.grid(alpha=.3)
        ax.legend(fontsize=7)
        plt.tight_layout()
        plt.savefig(args.out_dir / "fig_ys_stability_vs_trojan.png", dpi=170)
        plt.close()
        top = ok.head(15).iloc[::-1]
        fig, ax = plt.subplots(figsize=(7.8, 5.0))
        ax.barh(top["feature"], top["selectivity"],
                color=["#1f77b4" if g == "functional" else
                       ("#2ca02c" if g == "structural" else "#d62728")
                       for g in top["group"]])
        ax.set_xlabel("selectivity = TrojanDelta / (EquivDrift + 0.02)")
        ax.set_title("Top-15: stable under equivalence AND Trojan-sensitive", fontsize=10)
        ax.grid(axis="x", alpha=.3)
        plt.tight_layout()
        plt.savefig(args.out_dir / "fig_ys_top_selectivity.png", dpi=170)
        plt.close()
    print(f"\n[导出] {args.out_dir}（ys_feature_table.csv / ys_diag.csv / ys_per_design.csv"
          f" / fig_ys_*.png）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
