# -*- coding: utf-8 -*-
"""
feature_groups.py —— 第六块：EqGuard 的特征分组消融（严格 host-held-out）。

任务书第六块要求比较四组特征：
  1. 当前 39 维；
  2. 39 维 + 全部功能特征；
  3. 只按普通监督区分能力筛选的特征；
  4. 按「区分能力 **+** 等价稳定性」筛选的特征。

第 4 组的关键：**等价稳定性就用第三块（§8）在 yosys 等价网表上实测的 EquivDrift**，
按下面的显式映射从小节 8.3 的表搬到 39 维上（这样做的好处是"稳定性"是**测出来的**，不是拍的）。

映射（39 维布局见 phase2/feature_audit.py 注释）：
  dim 0..24  gate-type one-hot → **等价不稳**（换门库就整组变），给惩罚值 GATE_DRIFT
  dim 25 n_input_ports ← n_inputs        dim 26 degree        ← 0.158(fanin/fanout_2hop 均值)
  dim 27 touches_PI    ← 0.03(结构性)     dim 28 touches_PO    ← reach_po 0.187
  dim 29 dist_to_PI    ← depth 0.215      dim 30 dist_to_PO    ← hops_to_po 0.0008
  dim 31 fan_in_2hop   ← 0.138           dim 32 fan_out_2hop   ← 0.177
  dim 33 dag_dist_to_PI← depth 0.215     dim 34 dag_dist_to_PO ← hops_to_po 0.0008
  dim 35/36 dag_fan_*2hop ← 0.138/0.177  dim 37 in_cycle ← 0.05  dim 38 scc_size ← 0.20

"加/不加 consistency"那一轴由 M0–M3 承担（M3 = M2 + object-aware consistency），已在 §6/§7 报过；
本脚本只做**特征分组**这一轴，并额外把 §9 的 GNN 单行并进来对比。

用法：
  py phase2/feature_groups.py --amp
"""
from __future__ import annotations

import argparse
import json
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

from phase2 import p2common as C  # noqa: E402
from phase2.netlist_lib import load_library, parse_netlist  # noqa: E402
from phase2.simple_models import ap_score, fit_predict, recall_at  # noqa: E402
from phase2.ys import netlist_feats as NF  # noqa: E402

VALI_LIB = Path("C:/Users/91344/Desktop/GraphSAINT/GraphSAINT-train/vali/verilog_lib.v")
FUNC9 = ["sp", "toggle_rate", "cc0", "cc1", "co", "influence_in",
         "fanin_support", "reach_po", "reach_dff"]
GATE_DRIFT = 3.0                      # 门类型 one-hot：换门库整组变 → 判为"很不稳"
DIM_DRIFT = {25: 0.140, 26: 0.158, 27: 0.030, 28: 0.187, 29: 0.215, 30: 0.0008,
             31: 0.138, 32: 0.177, 33: 0.215, 34: 0.0008, 35: 0.138, 36: 0.177,
             37: 0.050, 38: 0.200}


def parse_args():
    ap = argparse.ArgumentParser(description="第六块：特征分组消融（LOCO）")
    ap.add_argument("--work-dir", type=Path,
                    default=ROOT / "generate_trans" / "folds" / "hosts_gamma")
    ap.add_argument("--hosts-root", type=Path, default=ROOT / "generate_trans" / "hosts")
    ap.add_argument("--ks", type=str, default="3,8,16")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--amp", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.10" / "results")
    return ap.parse_args()


def _sel_by_criteria(Xtr, ytr, cols, k, drifts):
    """在**训练 host 内**按 (单特征 AP) 或 (AP/(drift+eps)) 选列。"""
    sc = []
    for j in cols:
        v = Xtr[:, j]
        a = max(ap_score(v, ytr), ap_score(-v, ytr))
        sc.append(0.0 if np.isnan(a) else a)
    sc = np.asarray(sc)
    if drifts is not None:
        sc = sc / (np.asarray([drifts.get(j, 1.0) for j in cols]) + 0.05)
    order = np.argsort(-sc)[:k]
    return [cols[i] for i in order], float(sc.max())


def _fit_on_cols(kind, Xtr, ytr, Xte, cols, seed):
    import sklearn.linear_model as lm
    import sklearn.neural_network as nn
    from sklearn.preprocessing import StandardScaler
    sc = StandardScaler().fit(Xtr[:, cols])
    A, B = sc.transform(Xtr[:, cols]), sc.transform(Xte[:, cols])
    if kind == "logreg":
        m = lm.LogisticRegression(max_iter=400, class_weight="balanced").fit(A, ytr)
        return m.decision_function(B)
    m = nn.MLPClassifier(hidden_layer_sizes=(32,), max_iter=300, random_state=seed,
                         early_stopping=True, n_iter_no_change=15).fit(A, ytr)
    return m.predict_proba(B)[:, 1]


def _single_score(Xtr, ytr, Xte, cols, drifts):
    cols2, _ = _sel_by_criteria(Xtr, ytr, cols, 1, drifts)
    j = cols2[0]
    s = 1.0 if ap_score(Xtr[:, j], ytr) >= ap_score(-Xtr[:, j], ytr) else -1.0
    return s * Xte[:, j].astype(float), j


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    orig, _trans, _meta = C.load_fold(args.work_dir / "data" / "processed")
    X = orig.x.detach().cpu().numpy().astype(np.float32)
    y = orig.y.detach().cpu().numpy().astype(int)
    fid = [str(v) for v in orig.file_ids]
    host = np.array([v.split("__")[0] for v in fid])
    hosts = sorted(set(host.tolist()))
    stem2host = {v: v.split("__")[0] for v in fid}
    print(f"[INFO] 节点={len(y)} label1={int(y.sum())} hosts={len(hosts)} dims39={X.shape[1]}")

    F = func_features_per_node(args.work_dir, args.hosts_root, stem2host)
    Xf = np.concatenate([X, F], axis=1)
    D = X.shape[1]
    drift_func = {D + i: v for i, v in enumerate(
        [0.1306, 0.3650, 0.5000, 0.5700, 0.2072, 0.1244, 0.2472, 0.1867, 12.856])}
    drift_all = {**{d: GATE_DRIFT for d in range(25)}, **DIM_DRIFT, **drift_func}
    ks = [int(x) for x in args.ks.split(",")]
    kk = ks[1] if len(ks) > 1 else 8
    all_cols = list(range(D + len(FUNC9)))

    sets = {
        "A_39": (list(range(D)), None, ["single", "logreg", "mlp"]),
        "B_39+func9": (all_cols, None, ["single", "logreg", "mlp"]),
        f"C_sup_top{kk}": (all_cols, None, ["single", "logreg"]),
        f"D_combo_top{kk}": (all_cols, drift_all, ["single", "logreg"]),
    }
    rows = []
    for h in hosts:
        te, tr = (host == h), (host != h)
        if y[te].sum() == 0:
            continue
        for sname, (cols, drifts, mds) in sets.items():
            if sname.startswith("C_"):
                cols_use, _ = _sel_by_criteria(Xf[tr], y[tr], cols, kk, None)
            elif sname.startswith("D_"):
                cols_use, _ = _sel_by_criteria(Xf[tr], y[tr], cols, kk, drifts)
            else:
                cols_use = cols
            for md in mds:
                try:
                    if md == "single":
                        s, note = _single_score(Xf[tr], y[tr], Xf[te], cols_use,
                                                drifts if sname.startswith("D_") else None)
                        note = f"cols={[note]}"
                    else:
                        s = _fit_on_cols(md, Xf[tr], y[tr], Xf[te], cols_use, args.seed)
                        note = f"n_cols={len(cols_use)}"
                except Exception as e:                             # noqa: BLE001
                    print(f"[WARN] {sname}/{md} @ {h} 失败：{e}")
                    continue
                rows.append({"set": sname, "model": md, "host": h, "AP": ap_score(s, y[te]),
                             "Recall@1%": recall_at(s, y[te], 0.01),
                             "Recall@5%": recall_at(s, y[te], 0.05),
                             "n_cols": len(cols_use), "note": note,
                             "cols": ",".join(str(c) for c in cols_use[:24])})
    d = pd.DataFrame(rows)
    d.to_csv(args.out_dir / "feature_groups_by_host.csv", index=False, encoding="utf-8-sig")
    mac = d.groupby(["set", "model"])[["AP", "Recall@1%", "Recall@5%"]].mean().round(4)
    mac["n_cols"] = d.groupby(["set", "model"])["n_cols"].mean().round(1)
    mac = mac.sort_values("AP", ascending=False)
    mac.to_csv(args.out_dir / "feature_groups_macro.csv", encoding="utf-8-sig")
    print("\n=== 第六块：特征分组消融（严格 LOCO 5 折宏平均）===")
    print(mac.to_string())

    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    piv = d.pivot_table(index="model", columns="set", values="AP")
    piv.plot(kind="bar", ax=ax, rot=15)
    ax.set_ylabel("AP (macro over 5 held-out hosts)")
    ax.set_title("Block 6: feature-group ablation (strict host-held-out)", fontsize=10)
    ax.grid(axis="y", alpha=.3)
    plt.tight_layout()
    plt.savefig(args.out_dir / "fig_feature_groups.png", dpi=170)
    plt.close()
    print(f"\n[导出] {args.out_dir}/feature_groups_by_host.csv / feature_groups_macro.csv"
          f" / fig_feature_groups.png")
    return 0


def func_features_per_node(work_dir: Path, hosts_root: Path, stem2host):
    """把 netlist_feats 的功能特征按 **实例名 → 全局节点号** 对到 orig 图上。"""
    lib, sem = load_library(VALI_LIB), NF.load_cell_semantics(VALI_LIB)
    nidx = json.loads((work_dir / "phase2_name_index.json").read_text(encoding="utf-8"))["orig"]
    n = sum(len(m) for m in nidx.values())
    F = np.zeros((n, len(FUNC9)), dtype=np.float32)
    miss = 0
    for stem, m in nidx.items():
        host = stem2host.get(stem)
        f = hosts_root / host / f"{stem}.v" if host else None
        if f is None or not f.exists():
            miss += len(m)
            continue
        gates, rows, _info = NF.circuit_features(parse_netlist(f, lib), sem)
        buckets = {}
        for g, r in zip(gates, rows):
            buckets.setdefault(g.name.split(".")[0], []).append(r)
        for inst, gi in m.items():
            rs = buckets.get(inst)
            if not rs:
                miss += 1
                continue
            for j, k in enumerate(FUNC9):
                v = float(np.mean([r[k] for r in rs]))
                if k in ("fanin_support", "reach_po", "reach_dff", "co"):
                    v = float(np.log1p(min(v, NF.CAP)))
                F[gi, j] = 0.0 if not np.isfinite(v) else v
    print(f"[INFO] 功能特征已对齐：节点 {n}，未命中 {miss}")
    return F



if __name__ == "__main__":
    raise SystemExit(main())
