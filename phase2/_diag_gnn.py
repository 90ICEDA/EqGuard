# -*- coding: utf-8 -*-
"""_diag_gnn.py —— 把 GNN 调参诊断的各次 run 汇总成一张对照表。"""
import glob
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE = {"M0_beta": "lr 1e-4, 30 轮, 预算 4（原来那套）", "diag_lr1e3": "lr 1e-3, 30 轮, 预算 4",
        "diag_b16": "lr 1e-4, 30 轮, 预算 16", "diag_norm": "lr 1e-4, 30 轮, 预算 4, 特征标准化",
        "diag_all": "lr 1e-3, 300 轮, 预算 16, 特征标准化（全都调一遍）",
        "M0_noedge_beta": "去掉消息传递（原配置）"}


def read(d: Path):
    p = d / "circuit_level_summary.csv"
    if not p.exists():
        return None
    m = pd.read_csv(p)
    m = m[m.Circuit == "MACRO_MEAN"]
    if not len(m):
        return None
    r = m.iloc[0]
    return {"AP_T": float(r.Anchor_AP_Trans), "AP": float(r.AP),
            "Recall@5%": float(r.get("Recall@5%", float("nan"))),
            "Paired_MAE": float(r.Paired_MAE)}


def main() -> int:
    rows = []
    seen = set()
    for d in sorted(glob.glob(str(ROOT / "results" / "hosts_beta_seed42*loco_*"))):
        p = Path(d)
        if "_loco_" not in p.name:
            continue
        key = p.name.split("_loco_")[-1]
        if key in seen:
            continue
        # M0_beta 有两套 view-budget（早期 b2 与正式 b4），只用 b4 那套做基准
        if key == "M0_beta" and "hardb4" not in p.name:
            continue
        seen.add(key)
        r = read(p)
        if r is None:
            continue
        r["运行"] = key
        r["配置"] = BASE.get(key, "")
        rows.append(r)
    if not rows:
        print("没有可读的 run")
        return 1
    d = pd.DataFrame(rows).sort_values("AP_T")
    d = d[["运行", "配置", "AP_T", "AP", "Recall@5%", "Paired_MAE"]]
    print(d.round(4).to_string(index=False))
    print()
    ref = d[d["运行"] == "M0_beta"]["AP_T"]
    if len(ref):
        b = float(ref.iloc[0])
        print(f"参照（lr 1e-4, 30 轮, 预算 4）= {b:.4f}")
        for _i, r in d.iterrows():
            if r["运行"] != "M0_beta":
                print(f"  {r['运行']:16} {r['AP_T']:.4f}  相对参照 {r['AP_T'] / b - 1:+.1%}")
    print()
    print("另：同数据同协议下 Logistic Regression 的 AP 是 0.2956，MLP 是 0.1588（orig 图，单 seed）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
