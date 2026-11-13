# -*- coding: utf-8 -*-
"""
feature_audit_hosts.py —— 受控主机数据的**特征四问**（C1–C4）

数据：`generate_trans/hosts_fold/`（只跑了 parser2，拿到 39 维特征 + file_ids）
名单：`generate_trans/hosts/<host>/provenance.json`（哪些门是我们注入的木马/对照）

四问（第 1 问"等价稳定性"在 phase2/feature_audit.py 里做，这里做第 2/3/4 问）：
  Q2 clean↔infected **对应门**：同名门的 39 维特征变化多少（全局 / 木马 1-hop 邻域）
  Q3 Trojan vs **合法对照**：单特征 AUC（能不能靠这一维区分"真木马"和"长得像木马的正常逻辑"）
  Q4 **换 host** 之后 Q3 的区分力还在不在（逐 host AUC + 跨 host 一致性）

用法：
  python phase2/feature_audit_hosts.py --work-dir generate_trans/hosts_fold \
      --hosts-root generate_trans/hosts --out-dir results/phase2/feature_audit_hosts --plots
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase2 import netlist_lib as NL  # noqa: E402
from phase2.feature_audit import feature_names  # noqa: E402
from phase2.name_index import build_name_index  # noqa: E402

HOSTS = ["rs232t1000", "s15850t100", "s35932t200", "s38417t100", "s38584t100"]


def auc(x: np.ndarray, y: np.ndarray) -> float:
    """单特征 AUC（y ∈ {0,1}）；用秩公式，不依赖 sklearn。"""
    pos, neg = x[y == 1], x[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    from scipy.stats import rankdata
    r = rankdata(np.concatenate([pos, neg]))
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2)
                 / (len(pos) * len(neg)))


def one_hop_inputs(view_path: Path, lib, new_gates: set) -> set:
    """返回"作为木马/对照门输入的良性门名字集合"（= 特征会被改动的局部邻域）。"""
    if not view_path.exists():
        return set()
    nl = NL.parse_netlist(view_path, lib)
    nets = {n for i in nl.insts if i.name in new_gates for _p, n in nl.ins(i)}
    out = set()
    for i in nl.insts:
        if i.name in new_gates:
            continue
        for _p, n in nl.outs(i):
            if n in nets:
                out.add(i.name)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="四问：clean / 合法对照 / 跨 host")
    ap.add_argument("--work-dir", type=Path, default=Path("generate_trans/hosts_fold"))
    ap.add_argument("--hosts-root", type=Path, default=Path("generate_trans/hosts"))
    ap.add_argument("--out-dir", type=Path, default=Path("results/phase2/feature_audit_hosts"))
    ap.add_argument("--lib", type=Path,
                    default=Path("../GraphSAINT-train/vali/verilog_lib.v"))
    ap.add_argument("--plots", action="store_true")
    args = ap.parse_args()

    W, HR = args.work_dir.resolve(), args.hosts_root.resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    lib = NL.load_library(args.lib)
    names, groups = feature_names(W)
    idx = build_name_index(W)
    Xo = np.load(W / "data" / "for_train" / "feats_orig.npy")
    Xt = np.load(W / "data" / "for_train" / "feats_trans.npy")
    g_of = dict(zip(names, groups))

    prov = {}
    for h in HOSTS:
        p = HR / h / "provenance.json"
        if p.exists():
            prov[h] = json.loads(p.read_text(encoding="utf-8"))

    # ===================== Q3 / Q4：木马 vs 合法对照 =====================
    rows = []
    for h in HOSTS:
        for rec in prov.get(h, []):
            vi = idx["trans"].get(rec["view"]) or {}
            for g in rec["new_gates"]:
                if g in vi:
                    rows.append({"host": h, "view": rec["view"], "kind": rec["kind"],
                                 "ctl_type": rec.get("ctl_type") or "",
                                 "gate": g, "node": vi[g]})
    G = pd.DataFrame(rows)
    G = G[G["kind"].isin(["trojan", "control"])].copy()
    Xg = Xt[G["node"].to_numpy()]
    for j, nm in enumerate(names):
        G[nm] = Xg[:, j]
    G.to_csv(args.out_dir / "gates_features.csv", index=False, encoding="utf-8-sig")
    y = (G["kind"] == "trojan").to_numpy().astype(int)
    host_arr = G["host"].to_numpy()

    q3 = []
    for nm in names:
        v = G[nm].to_numpy(dtype=float)
        row = {"feature": nm, "group": g_of[nm], "auc_all": round(auc(v, y), 4)}
        for h in HOSTS:
            m = host_arr == h
            row[f"auc_{h}"] = round(auc(v[m], y[m]), 4)
        q3.append(row)
    q3df = pd.DataFrame(q3)
    ac = [f"auc_{h}" for h in HOSTS]
    q3df["auc_mean_host"] = q3df[ac].mean(axis=1).round(4)
    q3df["auc_min_host"] = q3df[ac].min(axis=1).round(4)
    q3df["auc_max_host"] = q3df[ac].max(axis=1).round(4)
    q3df["auc_flip"] = q3df[ac].apply(
        lambda r: int(any((v - 0.5) * (r.mean() - 0.5) < 0 for v in r)), axis=1)
    q3df["abs_auc_all"] = (q3df["auc_all"] - 0.5).abs().round(4)
    q3df = q3df.sort_values("abs_auc_all", ascending=False)
    q3df["n_trojan"] = int(y.sum())
    q3df["n_control"] = int((1 - y).sum())
    q3df.to_csv(args.out_dir / "q3_q4_trojan_vs_control.csv", index=False,
                encoding="utf-8-sig")
    print(f"=== Q3/Q4  Trojan({int(y.sum())}) vs 合法对照({int((1-y).sum())})，单特征 AUC ===")
    print(q3df.head(12)[["feature", "group", "auc_all", "auc_mean_host",
                         "auc_min_host", "auc_flip"]].to_string(index=False))

    # ===================== Q2：clean ↔ infected（同名门）=====================
    q2 = []
    for h in HOSTS:
        clean = idx["orig"].get(f"{h}_clean", {})
        if not clean:
            continue
        for rec in prov.get(h, []):
            vi = idx["trans"].get(rec["view"]) or {}
            if not vi:
                continue
            new = set(rec["new_gates"])
            local = one_hop_inputs(HR / h / f"{rec['view']}.v", lib, new)
            common = [n for n in clean if n in vi and n not in new]
            if len(common) < 8:
                continue
            A = Xo[[clean[n] for n in common]].astype(float)
            B = Xt[[vi[n] for n in common]].astype(float)
            D = np.abs(B - A)
            is_loc = np.array([n in local for n in common])
            for j, nm in enumerate(names):
                d = D[:, j]
                q2.append({"host": h, "view": rec["view"], "kind": rec["kind"],
                           "feature": nm, "n_matched": len(common),
                           "n_local": int(is_loc.sum()),
                           "mean_abs_delta_all": round(float(d.mean()), 6),
                           "mean_abs_delta_local": round(float(d[is_loc].mean()), 6)
                           if is_loc.any() else np.nan,
                           "frac_changed_local": round(float((d[is_loc] > 1e-9).mean()), 4)
                           if is_loc.any() else np.nan})
    q2df = pd.DataFrame(q2)
    if not q2df.empty:
        q2df.to_csv(args.out_dir / "q2_per_view.csv", index=False, encoding="utf-8-sig")
        tro = q2df[q2df["kind"] == "trojan"]
        summ = tro.groupby("feature").agg(
            delta_all=("mean_abs_delta_all", "mean"),
            delta_local=("mean_abs_delta_local", "mean"),
            changed_local=("frac_changed_local", "mean"),
            n_local=("n_local", "max")).round(6).reset_index()
        summ["group"] = [g_of[f] for f in summ["feature"]]
        summ["local_global_ratio"] = (summ["delta_local"]
                                      / summ["delta_all"].replace(0, np.nan)).round(3)
        summ = summ.sort_values("delta_local", ascending=False)
        summ.to_csv(args.out_dir / "q2_clean_vs_infected.csv", index=False,
                    encoding="utf-8-sig")
        print("\n=== Q2  clean↔infected：同名门特征变化（木马视图平均）===")
        print(summ.head(12)[["feature", "group", "delta_all", "delta_local",
                             "changed_local", "local_global_ratio"]].to_string(index=False))

    # ===================== C4：四问合并 =====================
    q1f = Path("results/phase2/feature_audit/single_to_composed_d2_feature_stability.csv")
    if q1f.exists():
        q1 = pd.read_csv(q1f)[["feature", "stab_view_view_median"]]
        m = q3df.merge(q1, on="feature", how="left")
        if not q2df.empty:
            m = m.merge(summ[["feature", "delta_local", "local_global_ratio"]],
                        on="feature", how="left")
        m.to_csv(args.out_dir / "four_questions.csv", index=False, encoding="utf-8-sig")
        keep = m[(m["stab_view_view_median"] >= 0.9) & (m["abs_auc_all"] >= 0.05)]
        print("\n=== C4 四问合并：Q1 稳定(≥0.9) 且 Q3 有区分力(|AUC-0.5|≥0.05) 的候选 ===")
        cols = [c for c in ["feature", "group", "stab_view_view_median", "auc_all",
                            "auc_mean_host", "auc_min_host", "auc_flip"] if c in keep]
        print(keep[cols].to_string(index=False))
        print(f"（共 {len(keep)} 个候选 / {len(m)} 维）")
    if args.plots:
        make_plots(q3df, args.out_dir / "figures")
    print(f"\n[导出] {args.out_dir}")
    return 0


def make_plots(q3df: pd.DataFrame, fig_dir: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig_dir.mkdir(parents=True, exist_ok=True)
    d = q3df.sort_values("auc_all")
    fig, ax = plt.subplots(figsize=(7, 9), dpi=140)
    ax.barh(range(len(d)), d["auc_all"] - 0.5, color="tab:blue")
    ax.set_yticks(range(len(d)))
    ax.set_yticklabels(d["feature"], fontsize=5.5)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("AUC − 0.5（Trojan vs 合法对照）")
    ax.set_title("Q3 单特征区分力（39 维）")
    fig.tight_layout()
    fig.savefig(fig_dir / "q3_trojan_vs_control.png")
    plt.close(fig)
    print(f"[plots] -> {fig_dir / 'q3_trojan_vs_control.png'}")


if __name__ == "__main__":
    raise SystemExit(main())


