# -*- coding: utf-8 -*-
"""
simple_models.py —— 第五块：先跑简单模型（**严格 host-held-out**）。

任务书原文：
  - 至少做：单特征 / Logistic Regression / XGBoost 或类似树模型 / 小 MLP / 现在的 GNN；
  - 全部做严格 host-held-out，**特征筛选只能在训练 host 内完成**，不能看测试 host 再挑特征。

数据：γ fold 的 `orig_graph`（30 个木马源视图 = 5 host × 6 实例，label1=255，39 维节点特征）；
按 **留一 host（LOCO）** 分 5 折 —— 与 GNN 的 LOCO 协议完全一致，可比。

模型：
  1. single_feature            —— 在训练 host 内选"单特征 AP 最高"的那一维（含符号方向）
  2. logreg_all / logreg_topK  —— 全 39 维 / 只用训练 host 内挑出的 top-K 维
  3. hgb_all                   —— sklearn HistGradientBoosting（LightGBM 式提升树；
                                  环境里没有 xgboost/lightgbm，已确认）
  4. mlp_topK                  —— 小 MLP（1 隐藏层 32）
  5. gnn_loco                  —— 复用已有 M0 LOCO 的逐电路 ckpt，在**同一批 orig 节点**上打分

指标：节点级 **AP** / Recall@1% / Recall@5%，逐 host 报 + 宏平均。

用法：
  py phase2/simple_models.py --work-dir generate_trans/folds/hosts_gamma \
      --gnn-glob "results/hosts_gamma_seed*mode4_*loco_M0_gamma*" --amp
"""
from __future__ import annotations

import argparse
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


def parse_args():
    ap = argparse.ArgumentParser(description="第五块：简单模型阶梯（严格 host-held-out）")
    ap.add_argument("--work-dir", type=Path,
                    default=ROOT / "generate_trans" / "folds" / "hosts_gamma")
    ap.add_argument("--gnn-glob", type=str,
                    default="results/hosts_gamma_seed*mode4_*loco_M0_gamma*")
    ap.add_argument("--ks", type=str, default="3,8,16", help="训练 host 内选出的特征数")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--amp", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.10" / "results")
    return ap.parse_args()


def ap_score(score, y) -> float:
    """平均精度（AP），用秩公式，不依赖 sklearn。"""
    score, y = np.asarray(score, float), np.asarray(y, int)
    if y.sum() == 0 or y.sum() == len(y):
        return float("nan")
    order = np.argsort(-score)
    y = y[order]
    tp = np.cumsum(y)
    prec = tp / np.arange(1, len(y) + 1)
    return float((prec * y).sum() / y.sum())


def recall_at(score, y, frac) -> float:
    score, y = np.asarray(score, float), np.asarray(y, int)
    if y.sum() == 0:
        return float("nan")
    k = max(1, int(round(frac * len(y))))
    idx = np.argsort(-score)[:k]
    return float(y[idx].sum() / y.sum())


def load_data(work_dir: Path):
    orig, trans, meta = C.load_fold(work_dir / "data" / "processed")
    X = orig.x.detach().cpu().numpy().astype(np.float32)
    y = orig.y.detach().cpu().numpy().astype(int)
    fid = list(orig.file_ids)
    host = np.array([str(v).split("__")[0] for v in fid])
    return orig, X, y, host


def topk_by_train_ap(Xtr, ytr, k):
    """**只在训练 host 内**按单特征 AP 排序（含符号方向）→ 选 top-k 列。"""
    sc = []
    for j in range(Xtr.shape[1]):
        v = Xtr[:, j]
        a = max(ap_score(v, ytr), ap_score(-v, ytr))
        sc.append(0.0 if np.isnan(a) else a)
    order = list(np.argsort(-np.asarray(sc))[:k])
    return order, sc


def fit_predict(model_name, Xtr, ytr, Xte, k, seed):
    """返回 (测试分数的 array, 备注)。所有标准化/筛选只用训练集。"""
    import sklearn.linear_model as lm
    import sklearn.neural_network as nn
    import sklearn.ensemble as ens
    from sklearn.preprocessing import StandardScaler
    if model_name == "single_feature":
        order, sc = topk_by_train_ap(Xtr, ytr, 1)
        j = order[0]
        sign = 1.0 if ap_score(Xtr[:, j], ytr) >= ap_score(-Xtr[:, j], ytr) else -1.0
        return sign * Xte[:, j].astype(float), f"dim={j} trainAP={max(sc):.4f}"
    if model_name == "logreg_all":
        cols = list(range(Xtr.shape[1]))
    else:
        cols, _ = topk_by_train_ap(Xtr, ytr, k)
    A, B = Xtr[:, cols], Xte[:, cols]
    sc_ = StandardScaler().fit(A)
    A, B = sc_.transform(A), sc_.transform(B)
    if model_name.startswith("logreg"):
        m = lm.LogisticRegression(max_iter=400, class_weight="balanced")
        m.fit(A, ytr)
        return m.decision_function(B), f"n_feat={len(cols)}"
    if model_name == "hgb_all":
        m = ens.HistGradientBoostingClassifier(max_iter=200, learning_rate=0.1,
                                              random_state=seed)
        m.fit(A, ytr)
        return m.predict_proba(B)[:, 1], f"n_feat={len(cols)}"
    if model_name.startswith("mlp"):
        m = nn.MLPClassifier(hidden_layer_sizes=(32,), max_iter=300,
                             random_state=seed, early_stopping=True, n_iter_no_change=15)
        m.fit(A, ytr)
        return m.predict_proba(B)[:, 1], f"n_feat={len(cols)}"
    raise ValueError(model_name)


def gnn_scores(orig, ckpt, amp):
    """复用已有 M0 LOCO 的逐电路 ckpt，在 orig 节点上打分（与简单模型同一批节点）。"""
    import torch
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    model, _blob = C.load_ckpt(ckpt, device)
    x = orig.x.to(device)
    ei = orig.edge_index.to(device)
    with C.Embedder(model) as emb:
        _, lo = emb.forward(x, ei, amp=amp)
    return torch.softmax(lo.float(), 1)[:, 1].detach().cpu().numpy()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    orig, X, y, host = load_data(args.work_dir)
    hosts = sorted(set(host.tolist()))
    print(f"[INFO] orig 节点={len(y)} label1={int(y.sum())} hosts={hosts} dims={X.shape[1]}")

    ks = [int(x) for x in args.ks.split(",")]
    models = ["single_feature", "logreg_all", "logreg_top%d" % ks[0], "hgb_all",
              "mlp_top%d" % ks[-1]]
    models += ["logreg_top%d" % k for k in ks[1:-1]]

    gnn = {}
    cks = {}
    for d in C.ROOT.glob(args.gnn_glob):
        for p in d.glob("best_model_*.pt"):
            cks[p.stem.replace("best_model_", "")] = p
    if cks:
        try:
            for h, p in cks.items():
                gnn[h] = gnn_scores(orig, p, args.amp)
            print(f"[INFO] GNN ckpt 复用 {len(gnn)} 个：{sorted(gnn)}")
        except Exception as e:                                    # noqa: BLE001
            print(f"[WARN] GNN 复算失败，跳过 GNN 行：{e}")

    rows = []
    for h in hosts:
        te, tr = (host == h), (host != h)
        if y[te].sum() == 0:
            continue
        for mn in models:
            k = int(mn.split("top")[-1]) if "top" in mn else 16
            try:
                s, note = fit_predict(mn, X[tr], y[tr], X[te], k, args.seed)
            except Exception as e:                                # noqa: BLE001
                print(f"[WARN] {mn} @ {h} 失败：{e}")
                continue
            rows.append({"model": mn, "host": h, "n_test": int(te.sum()),
                         "n_pos": int(y[te].sum()), "AP": ap_score(s, y[te]),
                         "Recall@1%": recall_at(s, y[te], 0.01),
                         "Recall@5%": recall_at(s, y[te], 0.05), "note": note})
        if h in gnn:
            s = np.asarray(gnn[h])[te]          # GNN 分数是全图长度，要按 host 掩码切
            rows.append({"model": "gnn_loco(M0)", "host": h, "n_test": int(te.sum()),
                         "n_pos": int(y[te].sum()), "AP": ap_score(s, y[te]),
                         "Recall@1%": recall_at(s, y[te], 0.01),
                         "Recall@5%": recall_at(s, y[te], 0.05), "note": "复用 ckpt"})
    if not rows:
        print("[ERROR] 没有任何结果")
        return 1
    d = pd.DataFrame(rows)
    d.to_csv(args.out_dir / "simple_models_by_host.csv", index=False, encoding="utf-8-sig")
    mac = d.groupby("model")[["AP", "Recall@1%", "Recall@5%"]].mean().round(4)
    mac["AP_std"] = d.groupby("model")["AP"].std().round(4)
    mac = mac.sort_values("AP", ascending=False)
    mac.to_csv(args.out_dir / "simple_models_macro.csv", encoding="utf-8-sig")
    print("\n=== 第五块：严格 host-held-out（留一 host）宏平均 ===")
    print(mac.to_string())

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    mac["AP"].plot(kind="bar", yerr=mac["AP_std"], capsize=3, ax=ax, rot=20)
    ax.set_ylabel("AP (macro over 5 held-out hosts)")
    ax.set_title("Block 5: simple-model ladder vs GNN (strict host-held-out)", fontsize=10)
    ax.grid(axis="y", alpha=.3)
    plt.tight_layout()
    plt.savefig(args.out_dir / "fig_simple_models.png", dpi=170)
    plt.close()
    print(f"\n[导出] {args.out_dir}/simple_models_by_host.csv / simple_models_macro.csv"
          f" / fig_simple_models.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
