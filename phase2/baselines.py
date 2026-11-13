# -*- coding: utf-8 -*-
"""
baselines.py —— 第八块：把现有方法当 baseline。

任务书原话：
  「把简单 structural heuristic、当前 GNN、DART-like domain invariant、DeepGate2 embedding
    之类都放进来。重点不是追求 baseline 数量，而是看**不同方法到底依赖什么证据**，
    特别是**合法低活动逻辑会不会被误判**。」

所以本表不只报 AP，还报一个**阈值无关**的关键指标：

  * `AP_trojan`    ：留出 host 的木马视图（rwbubble）里 label-1 节点的 AP
  * `AUC(T vs Ctl)`：**木马节点 vs 该 host 的合法对照视图节点** 的 AUC（曼-惠特尼）
                     ≈0.5 ⇒ 完全分不开（好）；≫0.5 ⇒ **会把合法低活动逻辑误判**（坏）

方法：
  heur_dag_dist_po / heur_dist_po / heur_low_degree / heur_low_fanout2  结构启发式（只看 1 维）
  logreg_39 / mlp_39                                                     监督学习（39 维）
  dart_like                                                              **DART 式域不变**：MLP + 对 host 的 GRL
  gnn_loco                                                               现有 GNN（复用 M0 LOCO ckpt）
  random                                                                 随机（下界）

DeepGate2：本机**没有**仓库/预训练权重（已全盘搜索确认）⇒ 记为"无法复现"，不硬造。
  替身：第九/十节里的 **9 个精确功能特征**（信号概率 / toggle / CC0-CC1 / CO / 影响度 / 支撑集 / 可达性）
  本身就是一种功能表示，已在 §10 B 组给出结果（48 维 LR = 0.9992）。

用法：
  py phase2/baselines.py --amp
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
from phase2.simple_models import ap_score, recall_at  # noqa: E402

# 39 维里的关键维（见 phase2/feature_audit.py 的布局注释）
DIM = {"dag_dist_to_PO": 34, "dist_to_PO": 30, "degree": 26,
       "fan_out_2hop": 32, "dag_dist_to_PI": 33}


def parse_args():
    ap = argparse.ArgumentParser(description="第八块：baseline 对照（LOCO）")
    ap.add_argument("--work-dir", type=Path,
                    default=ROOT / "generate_trans" / "folds" / "hosts_gamma")
    ap.add_argument("--gnn-glob", type=str,
                    default="results/hosts_gamma_seed*mode4_*loco_M0_gamma*")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--amp", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.10" / "results")
    return ap.parse_args()


def auc(x, y) -> float:
    """曼-惠特尼 AUC：P(x > y) + 0.5·P(x = y)。x=木马分数、y=对照分数。"""
    x, y = np.asarray(x, float), np.asarray(y, float)
    x = x[np.isfinite(x)]
    y = y[np.isfinite(y)]
    if x.size == 0 or y.size == 0:
        return float("nan")
    a = np.concatenate([x, y])
    r = np.argsort(np.argsort(a)) + 1.0
    rxy = r[:x.size].sum()
    return float((rxy - x.size * (x.size + 1) / 2) / (x.size * y.size))


def _grl_cls():
    import torch

    class GRL(torch.autograd.Function):
        @staticmethod
        def forward(ctx, x, lam):
            ctx.lam = lam
            return x.view_as(x)

        @staticmethod
        def backward(ctx, g):
            return -ctx.lam * g, None
    return GRL


def dart_like(Xtr, htr, ytr, Xte, n_dom, seed, epochs=60, lam=1.0):
    """DART 式**域不变**表示：MLP + 对 host（域）的梯度反转层。"""
    import torch
    import torch.nn as nn
    torch.manual_seed(seed)
    dev = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    mu = Xtr.mean(0)
    sd = Xtr.std(0) + 1e-6
    Ztr = torch.tensor((Xtr - mu) / sd, dtype=torch.float32, device=dev)
    Zte = torch.tensor((Xte - mu) / sd, dtype=torch.float32, device=dev)
    ytr_t = torch.tensor(ytr.astype(np.float32), device=dev)
    htr_t = torch.tensor(htr.astype(np.int64), device=dev)
    enc = nn.Sequential(nn.Linear(Xtr.shape[1], 64), nn.ReLU(), nn.Linear(64, 32),
                        nn.ReLU()).to(dev)
    head = nn.Linear(32, 1).to(dev)
    dom = nn.Sequential(nn.Linear(32, 32), nn.ReLU(), nn.Linear(32, n_dom)).to(dev)
    opt = torch.optim.Adam(list(enc.parameters()) + list(head.parameters())
                           + list(dom.parameters()), lr=1e-3)
    grl, bce = _grl_cls(), nn.BCEWithLogitsLoss()
    for ep in range(epochs):
        lam_ep = lam * min(1.0, (ep + 1) / max(1, epochs * 0.3))
        opt.zero_grad()
        z = enc(Ztr)
        loss = bce(head(z).squeeze(1), ytr_t)
        loss = loss + nn.functional.cross_entropy(dom(grl.apply(z, lam_ep)), htr_t)
        loss.backward()
        opt.step()
    with torch.no_grad():
        return head(enc(Zte)).squeeze(1).cpu().numpy()


def mlp_fit_predict(Xtr, ytr, Xte, seed):
    import sklearn.neural_network as nn
    from sklearn.preprocessing import StandardScaler
    sc = StandardScaler().fit(Xtr)
    m = nn.MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=200, random_state=seed,
                         early_stopping=True, n_iter_no_change=10)
    m.fit(sc.transform(Xtr), ytr)
    return m.predict_proba(sc.transform(Xte))[:, 1]


def lr_fit_predict(Xtr, ytr, Xte):
    import sklearn.linear_model as lm
    from sklearn.preprocessing import StandardScaler
    sc = StandardScaler().fit(Xtr)
    m = lm.LogisticRegression(max_iter=400, class_weight="balanced")
    m.fit(sc.transform(Xtr), ytr)
    return m.decision_function(sc.transform(Xte))


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    orig, trans, _meta = C.load_fold(args.work_dir / "data" / "processed")
    X = trans.x.detach().cpu().numpy().astype(np.float32)
    y = trans.y.detach().cpu().numpy().astype(int)
    fid = [str(v) for v in trans.file_ids]
    host = np.array([v.split("__")[0] for v in fid])
    hosts = sorted(set(host.tolist()))
    view = np.array(fid)
    print(f"[INFO] trans 节点={len(y)} label1={int(y.sum())} hosts={hosts} dims={X.shape[1]}")

    gnn = {}
    for dd in C.ROOT.glob(args.gnn_glob):
        for p in dd.glob("best_model_*.pt"):
            gnn[p.stem.replace("best_model_", "")] = p
    gnn_s = {}
    if gnn:
        import torch
        dev = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        xt = torch.tensor(X, device=dev)
        ei = trans.edge_index.to(dev)
        for h, p in gnn.items():
            try:
                model, _b = C.load_ckpt(p, dev)
                with C.Embedder(model) as emb:
                    _, lo = emb.forward(xt, ei, amp=args.amp)
                gnn_s[h] = torch.softmax(lo.float(), 1)[:, 1].detach().cpu().numpy()
            except Exception as e:                                  # noqa: BLE001
                print(f"[WARN] GNN {h} 打分失败：{e}")
        print(f"[INFO] GNN 复算 {len(gnn_s)} 个 ckpt")

    rng = np.random.default_rng(args.seed)
    rand_s = rng.random(len(y))
    rows = []
    tro = np.array([("__inj" in v and "__rw" in v) for v in view])
    for h in hosts:
        tr, te = (host != h), (host == h)
        ctl = np.array([(h + "__ctl") in v and "__rw" in v for v in view])   # 只用**结构匹配的对照改写视图**
        te_tv = te & tro                       # 该 host 的木马测试视图（全体节点）
        if y[te_tv].sum() == 0 or ctl.sum() == 0:
            continue
        tr_tv = tr & tro                       # 训练 host 的木马视图（用于校准方向）
        n_dom = len([x for x in hosts if x != h])
        hmap = {x: i for i, x in enumerate(sorted(set(host[tr].tolist())))}
        htr = np.array([hmap[x] for x in host[tr]])
        heur_dims = {"heur_dag_dist_po": DIM["dag_dist_to_PO"],
                     "heur_dist_po": DIM["dist_to_PO"],
                     "heur_low_degree": DIM["degree"],
                     "heur_low_fanout2": DIM["fan_out_2hop"]}
        for name, j in heur_dims.items():
            v = X[:, j].astype(float)
            ap_pos = ap_score(v[tr_tv], y[tr_tv])
            ap_neg = ap_score(-v[tr_tv], y[tr_tv])
            s = v if np.nan_to_num(ap_pos) >= np.nan_to_num(ap_neg) else -v
            s = s + (1.0 if name == "heur_low_degree" else 0.0)   # 名实相符的小偏移
            rows.append({"method": name, "host": h, "AP_trojan": ap_score(s[te_tv], y[te_tv]),
                         "AUC_T_vs_Ctl": auc(s[te_tv & (y == 1)], s[ctl]),
                         "Recall@5%": recall_at(s[te_tv], y[te_tv], 0.05)})
        rows.append({"method": "random", "host": h,
                     "AP_trojan": ap_score(rand_s[te_tv], y[te_tv]),
                     "AUC_T_vs_Ctl": auc(rand_s[te_tv & (y == 1)], rand_s[ctl]),
                     "Recall@5%": recall_at(rand_s[te_tv], y[te_tv], 0.05)})
        for name, fn in (("logreg_39", lr_fit_predict),
                         ("mlp_39", lambda a, b, c: mlp_fit_predict(a, b, c, args.seed))):
            try:
                s = np.full(len(y), np.nan)
                s[te] = fn(X[tr], y[tr], X[te])
                rows.append({"method": name, "host": h, "AP_trojan": ap_score(s[te_tv], y[te_tv]),
                             "AUC_T_vs_Ctl": auc(s[te_tv & (y == 1)], s[ctl]),
                             "Recall@5%": recall_at(s[te_tv], y[te_tv], 0.05)})
            except Exception as e:                                  # noqa: BLE001
                print(f"[WARN] {name} @ {h} 失败：{e}")
        try:
            s = np.full(len(y), np.nan)
            s[te] = dart_like(X[tr], htr, y[tr], X[te], n_dom, args.seed)
            rows.append({"method": "dart_like", "host": h, "AP_trojan": ap_score(s[te_tv], y[te_tv]),
                         "AUC_T_vs_Ctl": auc(s[te_tv & (y == 1)], s[ctl]),
                         "Recall@5%": recall_at(s[te_tv], y[te_tv], 0.05)})
        except Exception as e:                                      # noqa: BLE001
            print(f"[WARN] dart_like @ {h} 失败：{e}")
        if h in gnn_s:
            s = gnn_s[h]
            rows.append({"method": "gnn_loco(M0)", "host": h,
                         "AP_trojan": ap_score(s[te_tv], y[te_tv]),
                         "AUC_T_vs_Ctl": auc(s[te_tv & (y == 1)], s[ctl]),
                         "Recall@5%": recall_at(s[te_tv], y[te_tv], 0.05)})
    d = pd.DataFrame(rows)
    d.to_csv(args.out_dir / "baselines_by_host.csv", index=False, encoding="utf-8-sig")
    mac = d.groupby("method")[["AP_trojan", "AUC_T_vs_Ctl", "Recall@5%"]].mean().round(4)
    mac["AP_std"] = d.groupby("method")["AP_trojan"].std().round(4)
    mac = mac.sort_values("AUC_T_vs_Ctl")
    mac.to_csv(args.out_dir / "baselines_macro.csv", encoding="utf-8-sig")
    print("\n=== 第八块：baseline 对照（LOCO 5 折宏平均）===")
    print("（AUC_T_vs_Ctl ≈0.5 = 分不开木马与合法对照（好）；越大 = 越会误判合法低活动逻辑）")
    print(mac.to_string())

    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    mac["AUC_T_vs_Ctl"].plot(kind="bar", yerr=None, ax=ax, rot=25, color="#d62728")
    ax.axhline(0.5, color="k", ls="--", lw=1)
    ax.set_ylabel("AUC (Trojan vs legal control)")
    ax.set_title("Block 8: what evidence does each method rely on?", fontsize=10)
    ax.grid(axis="y", alpha=.3)
    plt.tight_layout()
    plt.savefig(args.out_dir / "fig_baselines.png", dpi=170)
    plt.close()
    print(f"\n[导出] {args.out_dir}/baselines_by_host.csv / baselines_macro.csv / fig_baselines.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
