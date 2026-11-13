"""make_d_tables.py —— D1/D3/D4/D5 的分析表（纯 CPU ✓，用已入库的 CSV + dev4 特征）。

D1 rt vs abc：结构/标签/CEC/绑定 的配方级对照
D3 特征来源归因：每个配方相对 `ys_id` 的特征漂移（按组：门类型 / 结构位 / 锥特征）
D4 AIG 标签：每配方的标签覆盖 / 绑定 / 正样本
D5 失败案例：绑不上 / CEC FAIL / 无正样本 / 低覆盖 的清单 + "高分集中在哪" 的量化
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
A2 = ROOT / "10.15" / "01_数据与标签" / "A2_锚点与逻辑锥" / "tables" / "a2_coverage_v3.csv"
A5 = ROOT / "10.15" / "01_数据与标签" / "A5_统一manifest" / "tables" / "manifest_v3.csv"
EXCL = ROOT / "10.15" / "01_数据与标签" / "B1_可信标签" / "tables" / "b1_excluded_views.csv"
OUT = ROOT / "10.15" / "04_ABC_AIG专项"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/_dev4/data/processed/trans_graph.pt")
    ap.add_argument("--gnn", type=Path, default=ROOT / "_devcfg/gnn_dev4_g0.npz")
    a = ap.parse_args()

    man = pd.read_csv(A5)
    cov = pd.read_csv(A2)
    cov = cov[cov.kind == "trojan"].copy()
    cov["recipe"] = cov.recipe.str.replace("ys_", "", regex=False)

    man["recipe2"] = man.recipe.str.replace("ys_", "", regex=False)
    # ---------- D1 ----------
    g = man.groupby("recipe2").agg(
        views=("sample_id", "size"),
        src_inst=("n_src_inst", "median"),
        conv_gates=("n_conv_gates", "median"),
        pos=("n_pos", "sum"),
        cec_pass=("status", lambda s: int((s == "PASS").sum())),
    )
    g["node_ratio"] = (g.conv_gates / g.src_inst).round(3)
    cc = cov.groupby("recipe").agg(cov_core=("cover_core", "mean"),
                                   cov_region=("cover_region", "mean"),
                                   cov_pos=("cover_pos", "mean"))
    g = g.join(cc).round(4)
    g.to_csv(OUT / "D1_rt_vs_abc" / "tables" / "recipe_structure.csv", index=True)
    print("== D1 配方对照 ==")
    print(g.to_string())

    # ---------- D3 / D4（特征与标签，dev4） ----------
    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    y = np.asarray(d.y, np.int8)
    fids = json.loads((a.pt.parents[2] / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))["file_ids"]
    rec = np.array([v.split("__")[-1] for v in fids])       # 配方 = 最后一段（ys_abc ✓）
    cones = np.load(a.pt.parent / "cone_feats.npy") if (a.pt.parent / "cone_feats.npy").exists() else None
    F = np.concatenate([X, cones], 1) if cones is not None else X
    names = [f"f{i:02d}" for i in range(X.shape[1])] + [f"cone{i}" for i in range(F.shape[1] - X.shape[1])]
    groups = {"gate": names[:25], "struct": names[25:39], "cone": names[39:]}

    rows = []
    idmask = rec == "ys_id"
    if idmask.sum() == 0:
        idmask = np.ones(len(rec), bool)
    mu0, sd0 = F[idmask].mean(0), F[idmask].std(0) + 1e-6
    for r in sorted(set(rec.tolist())):
        m = rec == r
        z = np.abs(F[m].mean(0) - mu0) / sd0
        rows.append({"recipe": r, "nodes": int(m.sum()),
                     "gate_drift": round(float(np.mean([z[names.index(c)] for c in groups["gate"]])), 3),
                     "struct_drift": round(float(np.mean([z[names.index(c)] for c in groups["struct"]])), 3),
                     "cone_drift": round(float(np.mean([z[names.index(c)] for c in groups["cone"]])), 3),
                     "pos": int(y[m].sum())})
    D3 = pd.DataFrame(rows)
    D3.to_csv(OUT / "D3_特征对比" / "tables" / "recipe_feature_drift.csv", index=False, encoding="utf-8-sig")
    print("\n== D3 特征漂移（相对 ys_id ✓）==")
    print(D3.to_string(index=False))

    # ---------- D4：按配方的标签/绑定 ----------
    D4 = g[["views", "pos", "cec_pass", "cov_core", "cov_pos"]].copy()
    D4.to_csv(OUT / "D4_aig标签" / "tables" / "recipe_label_quality.csv", index=True)
    print("\n== D4 标签质量 ==")
    print(D4.to_string())

    # ---------- D5：失败清单 + 高分位置 ----------
    bad_bind = pd.read_csv(EXCL)
    no_pos = man[(man.kind == "trojan") & (man.n_pos == 0)][["sample_id", "recipe2", "cov_core"]]
    cec_fail = man[man.status != "PASS"][["sample_id", "recipe2", "status"]]
    low_cov = cov[(cov.cover_core < 0.5)][["view", "recipe", "cover_core"]].head(20)
    base = OUT / "D5_失败案例" / "tables"
    base.mkdir(parents=True, exist_ok=True)
    bad_bind.to_csv(base / "unbindable.csv", index=False, encoding="utf-8-sig")
    no_pos.to_csv(base / "trojan_no_pos.csv", index=False, encoding="utf-8-sig")
    cec_fail.to_csv(base / "cec_fail.csv", index=False, encoding="utf-8-sig")
    low_cov.to_csv(base / "low_core_cov.csv", index=False, encoding="utf-8-sig")
    print(f"\n== D5 失败统计 == unbindable {len(bad_bind)} / trojan_no_pos {len(no_pos)} / "
          f"cec_fail {len(cec_fail)} / low_cov(top20) {len(low_cov)}")

    # 高分是否集中在 PO 附近（用 G0 分数 ✓）
    if a.gnn.exists():
        z = np.load(a.gnn)
        sc = np.zeros(len(y), np.float32)
        sc[z["idx"].astype(np.int64)] = z["score"].astype(np.float32)
        te = np.asarray(d.test_mask, bool)
        dist_po = X[:, 30]
        k = int(te.sum() * 0.05)
        order = np.argsort(-sc[te])[:k]
        idx_te = np.where(te)[0]
        top = idx_te[order]
        bins = [(0, 2), (2, 5), (5, 10), (10, 20), (20, 999)]
        rr = []
        for lo, hi in bins:
            m = (dist_po >= lo) & (dist_po < hi)
            rr.append({"dist_to_PO": f"{lo}-{hi}", "test_nodes": int((m & te).sum()),
                       "pos_in_bin": int(y[m & te].sum()),
                       "top5%_in_bin": int(m[top].sum())})
        pd.DataFrame(rr).to_csv(OUT / "D5_失败案例" / "tables" / "top_hits_by_dist_to_po.csv",
                                index=False, encoding="utf-8-sig")
        print("\n== D5 高分落点（按到 PO 距离分桶 ✓）==")
        print(pd.DataFrame(rr).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
