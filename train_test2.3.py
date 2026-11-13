#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_test2.3.py — fold 感知的训练/评测：合法视图预算策略 + 锚点 AP + 电路级宏平均

相对 train_test2.2.py 的改动（论文级复现所需）：
  1) 数据来自 fold 工作目录的 .pt（process_pt2.py 产物）：**视图级** train/val/test 角色、
     label-free alignment（原始血缘）、provenance-transported 标签、每视图 CEC 状态。
  2) 合法的视图预算：--view-policy {all,random,pred_hard} + --view-budget B。
     候选视图只来自**外层训练视图**；选择以视图为单位（random 每轮重抽），
     测试视图在任何阶段都不进入 train_mask（2.2 中 mode3 ≡ mode4，没有这个机制）。
  3) 指标补齐：AP、Anchor-AP(Orig)、Anchor-AP(Trans)、Recall@1%/2%/5%、
     配对一致性（Paired_MAE / Flip_Rate / Spearman_Corr 及 PerOrig）＋ Precision/Recall/FPR/Macro-F1/ROC-AUC。
  4) 聚合：variant_level_summary.csv（每视图一行）+ circuit_level_summary.csv（每电路一行 + MACRO 宏平均）。
     宏平均 = 先电路内平均，再对各电路取平均（取代 2.2 的 RUNNING_MEAN 行平均，避免大电路主导）。

数值实现（阈值校准/损失/一致性指标）直接复用 train_test2.2.py，保证与基线可比。

用法：
  python train_test2.3.py --work-dir ../generate_trans/_fold_d2_rs232 \
      --fold-json ../generate_trans/matrix/folds/single_to_composed_d2/views.json \
      --circuits rs232 --fold-mode fold --epochs 5 --view-policy random --view-budget 4
"""

import argparse
import hashlib
import importlib.util
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
import yaml

CUR = Path(__file__).resolve().parent
sys.path.append(str(CUR))

from models.gin_net import GINNodeClassifier, GINDual  # noqa: E402


# ---------------------------------------------------------------------------
# 复用 2.2 的数值实现（阈值校准 / siamese 损失 / 配对一致性 / recall@budget ...）
# 注意：train_test2.2.py 模块顶层只有 import 与路径设置，exec_module 无副作用。
# ---------------------------------------------------------------------------
def _load_t22():
    spec = importlib.util.spec_from_file_location("train_test2_2", str(CUR / "train_test2.2.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T22 = _load_t22()


def parse_args():
    ap = argparse.ArgumentParser(description="fold 感知训练/评测（train_test2.3）")
    ap.add_argument("--work-dir", type=Path, required=True, help="fold 工作目录（process_pt2 输出的父目录）")
    ap.add_argument("--fold-json", type=Path, required=True, help="matrix/folds/<fold>/views.json")
    ap.add_argument("--pt-dir", type=Path, default=None, help="默认 <work-dir>/data/processed")
    ap.add_argument("--abl-no-edges", action="store_true",
                    help="消融：edge_index 只留自环 ⇒ GNN 退化成同架构的逐节点 MLP；"
                         "用来判断'GNN 不如 LR'是消息传递的锅还是架构/训练的锅")
    ap.add_argument("--norm-fit", choices=["all", "train"], default="all",
                    help="z-score 统计量用谁拟合：all=全图（默认 ✓）/ train=只用训练角色节点 ✓")
    ap.add_argument("--no-norm-x", action="store_true",
                    help="关闭节点特征 z-score（**默认开启** ✓：关掉会让 GNN 塌到 AUC≈0.52 ✗）")
    ap.add_argument("--config", type=Path, default=CUR / "config.yaml")
    ap.add_argument("--circuits", type=str, default="", help="只评测这些电路（逗号分隔前缀，如 rs232）")
    ap.add_argument("--extra-feats", choices=["none", "cone5", "satrel", "satrel_node"], default="none",
                    help="C1/C3/P2-C：在 39 维后追加额外特征 ✓；"
                         "cone5=`cone_feats.npy` ✓ / satrel=`satrel_view_feats.npy`（SAT 功能关系 ✓，"
                         "视图级广播 ✓）/ satrel_node=`satrel_node_feats_sat.npy` + mask"
                         "（**节点级** SAT 证据 ✓，见 phase2/ys/satrel_node_feats_sat.py）")
    ap.add_argument("--extra-node-file", default="satrel_node_feats_sat.npy",
                    help="节点级 SAT 特征文件名 ✓（默认训练版；**置换对照**用 "
                         "`satrel_node_feats_sat_perm.npy` ✓）")
    ap.add_argument("--extra-dense-prefix", type=int, default=0,
                    help="extra 特征前 N 列是稠密结构特征（如 cone5）：用全图统计归一化，"
                         "且未 covered 行不置零；其余列仍用 covered 统计")
    ap.add_argument("--func-const", action="store_true",
                    help="C2/C4：一致性损失**只加在功能分支** ✓（需 model.type≠single ✓）")
    ap.add_argument("--label-mask", choices=["none", "trust"], default="none",
                    help="B1 可信标签：trust = 只用有血缘的节点算 loss ✓（unknown 不进梯度 ✓）")
    ap.add_argument("--steps-per-epoch", type=int, default=1,
                    help="每个 epoch 内做几次参数更新 ✓（原来 1 epoch = 1 步 ✗，全量 fold 一步 40 s ✗）")
    ap.add_argument("--dump-scores", type=Path, default=None,
                    help="把 test/val 节点的预测概率存成 npz ✓（供 LR/GBDT 融合 ✓）")
    ap.add_argument("--fold-mode", choices=["fold", "loco", "lio", "lro"], default="fold",
                    help="fold=按 fold spec 训练/测试（变换泛化）；loco=按目标电路留一（电路泛化）；"
                         "lio=按木马实例留一（未见 instance，含其匹配对照）；lro=按配方留一（未见综合流程 ✓）")
    ap.add_argument("--lro-splits", default="",
                    help="仅对 --fold-mode lro 生效：逗号分隔的 recipe 子集（如 ys_id,ys_opt），"
                         "用于时间受限时只跑关键 split；空=全部")
    ap.add_argument("--view-policy", choices=["all", "random", "pred_hard", "inspection_hard"],
                    default="all")
    ap.add_argument("--view-budget", type=int, default=1, help="每个电路每轮使用多少个训练视图")
    ap.add_argument("--epochs", type=int, default=0, help="0 = 用 config.yaml 的 epochs")
    ap.add_argument("--seed", type=int, default=0, help="0 = 用 config.yaml 的 seed_id")
    ap.add_argument("--train-mode", type=int, default=0, help="0 = 用 config.yaml 的 train_mode（1=仅 Orig）")
    ap.add_argument("--hard-buffer", type=int, default=3,
                    help="pred_hard 策略：每 N 轮重新评估视图难度（默认 3）")
    ap.add_argument("--val-every", type=int, default=5, help="每 N 轮做一次验证（阈值校准+选模型）")
    ap.add_argument("--out-root", type=Path, default=CUR / "results")
    ap.add_argument("--tag", type=str, default="", help="结果目录后缀（便于区分实验组）")
    ap.add_argument("--verify-calibration", action="store_true",
                    help="只做阈值校准等价性验证（与 train_test2.2.py 逐例比对）后退出")
    ap.add_argument("--amp", action="store_true",
                    help="bf16 autocast（CUDA 下显存约减半、MLP 吞吐更高；大 fold 必需）")
    ap.add_argument("--save-ckpt", action="store_true",
                    help="把每个外层划分的最优 state_dict 存到结果目录（best_model_<split>.pt）——"
                         "供 phase2 的表征 audit / 反事实评测复用，不改变训练本身")
    # C6/P1 ✓：区域级监督（C6 小 fold 试点已证：head_fp −45%、node AP +84% ✓）
    #   默认 0.0 → **不改变任何现有实验** ✓（向后兼容 ✓）
    ap.add_argument("--region-loss", type=float, default=0.0,
                    help="C6：锥级 BCE 的权重 λ（0 = 关闭 ✓；建议 0.5 / 1.0 ✓）")
    ap.add_argument("--region-mode", choices=["dff", "po"], default="dff",
                    help="C6 区域定义：dff=DFF 边界锥（覆盖高 ✓）/ po=PO 反向锥（v3.1 上 94%% 是单点 ✗）")
    # 断点续跑 ✓（2026-10-22 断电丢 2h51m ✗ 后加 ✓）：每完成一个外层 split 立即落盘 ✓，
    #   重跑时 --resume 跳过已完成的 split ✓（产物 = rows_partial.json + done_splits.json ✓）。
    #   默认关闭 ✓ → **不改变任何现有实验** ✓（向后兼容 ✓）
    ap.add_argument("--resume", action="store_true",
                    help="跳过结果目录中 done_splits.json 已记录的 split（断电/中断后接续 ✓）")
    # P2-D/E ✓（FG-HTL 的跨实现一致性 / 结构相似抑制 ✓；默认 0 = 不改变任何现有实验 ✓）
    ap.add_argument("--eq-loss", type=float, default=0.0,
                    help="P2-D：跨实现一致性正则权重 λ_eq ✓（视图级 ✓：SAT 已证的实现对之间"
                         "惩罚平均 logit 差 ✓；0 = 关闭 ✓，需 `satrel_groups.json` ✓）")
    ap.add_argument("--pair-loss", type=float, default=0.0,
                    help="P2-E：结构相似抑制正则权重 λ_pair ✓（A4 三胞胎 ✓："
                         "木马视图 vs 等价对照/死逻辑视图 的 margin 排序 ✓；0 = 关闭 ✓）")
    ap.add_argument("--pair-margin", type=float, default=0.5,
                    help="P2-E 的 margin（logit 差 ✓，默认 0.5 ✓）")
    # P2-D/E **节点级** ✓（SAT 已证节点对 ✓；默认 0 = 不改变任何现有实验 ✓）
    ap.add_argument("--eq-loss-node", type=float, default=0.0,
                    help="P2-D（节点级）：在同一批 SAT 已证**节点对**上惩罚 logit 差 ✓"
                         "（需 `satrel_node_pairs.npz` ✓；0 = 关闭 ✓）")
    ap.add_argument("--eq-pos-scale", type=float, default=1.0,
                    help="D 中正-正 consistency 对的权重（默认 1）")
    ap.add_argument("--eq-neg-scale", type=float, default=1.0,
                    help="D 中负-负 consistency 对的权重（0 = 只用正-正）")
    ap.add_argument("--pair-loss-node", type=float, default=0.0,
                    help="P2-E（节点级）：SAT 已证对里 木马节点 vs 等价/死逻辑对照节点 的 margin ✓"
                         "（a 侧=木马 ✓；0 = 关闭 ✓）")
    ap.add_argument("--node-pair-cap", type=int, default=20000,
                    help="每个 epoch 每类节点对最多抽多少对 ✓（控显存/时间 ✓）")
    ap.add_argument("--node-pairs-file", default="satrel_node_pairs.npz",
                    help="节点对 npz 文件名（默认 satrel_node_pairs.npz；"
                         "修复版可用 satrel_node_pairs_labelclean.npz）")
    ap.add_argument("--norm-extra", choices=["none", "covered", "bounded"], default="covered",
                    help="extra 缩放：none=沿用全图 z-score；covered=覆盖集合 z-score（默认）；"
                         "bounded=已经位于 [0,1] 的节点特征保持原值，不做稀疏列 z-score")
    ap.add_argument("--no-cov-flag", action="store_true",
                    help="把 satrel_node 的最后一维（covered 标记 ✓）置零 ✓ → **敏感性对照** ⚠️"
                         "（该标记在正/负上覆盖率 43.9%% vs 0.27%% ✗，本身近似标签代理 ✗）")
    ap.add_argument("--smoke-val-only", action="store_true",
                    help="有界 smoke：训练和验证后退出，不调用测试评估/不导出测试预测")
    ap.add_argument("--smoke-fixed-rng", action="store_true",
                    help="随机流只由 seed 决定，不受 tag 长度影响")
    ap.add_argument("--smoke-final-ckpt", type=Path, default=None,
                    help="保存最终更新点 state_dict（不是最优 checkpoint）")
    return ap.parse_args()


def tensor_sha(x: torch.Tensor) -> str:
    return hashlib.sha256(np.ascontiguousarray(x.detach().cpu().numpy()).tobytes()).hexdigest()


def seed_everything(seed):
    T22.seed_everything(seed)


# ---------------------------------------------------------------------------
# fold .pt 读取与视图索引
# ---------------------------------------------------------------------------
def load_fold(pt_dir: Path):
    orig = torch.load(pt_dir / "orig_graph.pt", weights_only=False)
    trans = torch.load(pt_dir / "trans_graph.pt", weights_only=False)
    meta = json.loads((pt_dir / "dataset_meta.json").read_text(encoding="utf-8"))
    return orig, trans, meta


def view_index(trans):
    """视图名 -> 该视图的节点索引张量（依据 metadata 的 file_ids）"""
    out = defaultdict(list)
    for i, v in enumerate(trans.file_ids):
        out[v].append(i)
    return {v: torch.tensor(idxs, dtype=torch.long) for v, idxs in out.items()}


def views_of_role(trans, role, drop_circuits=()):
    vs = sorted({v for v, r in trans.view_role.items() if r == role})
    if drop_circuits:
        drop = {v.split("__")[0] for v in drop_circuits}
        vs = [v for v in vs if v.split("__")[0] not in drop]
    return vs


def views_by_circuit(views):
    out = defaultdict(list)
    for v in views:
        out[v.split("__")[0]].append(v)
    return {k: sorted(vs) for k, vs in sorted(out.items())}


def nodes_of(views, vidx):
    if not views:
        return torch.zeros(0, dtype=torch.long)
    return torch.cat([vidx[v] for v in sorted(views) if v in vidx])


def apply_masks(orig, trans, train_views, val_views, test_views, vidx_t):
    """把视图选择写回 .pt 的 mask（T22.siamese_loss 内部读的就是这些 mask）

    orig 侧的两种模式：
      * 旧模式（默认）：orig 文件名 stem 与视图名前缀（`v.split("__")[0]`）相同 → 前缀匹配。
      * **新模式（γ）**：一个电路有**多个 orig**（每个 instance 一份），orig stem 形如
        `<host>__injalpha_d1_s42`，与视图前缀对不上；此时用 `orig.orig_view_map`
        （{orig_stem: [引用它的视图名…]}，由 build 脚本从 mappings 的 src_verilog 汇总）
        按**真实引用关系**打 mask。没有这个表就自动回退旧逻辑。
    """
    for d, n in ((orig, orig.num_nodes), (trans, trans.num_nodes)):
        d.train_mask = torch.zeros(n, dtype=torch.bool, device=d.x.device)
        d.val_mask = torch.zeros(n, dtype=torch.bool, device=d.x.device)
        d.test_mask = torch.zeros(n, dtype=torch.bool, device=d.x.device)

    ovm = getattr(orig, "orig_view_map", None)
    if ovm:
        tv, vv, ev = set(train_views), set(val_views), set(test_views)
        for i, p in enumerate(orig.file_ids):
            refs = ovm.get(p) or []
            if any(r in tv for r in refs):
                orig.train_mask[i] = True
            elif any(r in vv for r in refs):
                orig.val_mask[i] = True
            elif any(r in ev for r in refs):
                orig.test_mask[i] = True
    else:
        train_circ = {v.split("__")[0] for v in train_views}
        val_circ = {v.split("__")[0] for v in val_views}
        test_circ = {v.split("__")[0] for v in test_views}
        for i, p in enumerate(orig.file_ids):
            if p in train_circ:
                orig.train_mask[i] = True
            elif p in val_circ:
                orig.val_mask[i] = True
            elif p in test_circ:
                orig.test_mask[i] = True

    for v in train_views:
        if v in vidx_t:
            trans.train_mask[vidx_t[v]] = True
    for v in val_views:
        if v in vidx_t:
            trans.val_mask[vidx_t[v]] = True
    for v in test_views:
        if v in vidx_t:
            trans.test_mask[vidx_t[v]] = True


# ---------------------------------------------------------------------------
# 视图预算策略（只看外层训练视图）
# ---------------------------------------------------------------------------
def select_train_views(train_views, policy, budget, rng, hardness=None):
    """按电路分组，每组选 budget 个视图；返回 (selected_views, 说明字符串)"""
    if policy == "all":
        return list(train_views), "all"
    by_c = views_by_circuit(train_views)
    picked = []
    for c, vs in by_c.items():
        b = max(1, min(int(budget), len(vs)))
        if policy == "random":
            picked += sorted(rng.sample(vs, b))
        else:  # pred_hard / inspection_hard：按当前模型的视图难度从大到小取（难样本优先）
            order = sorted(vs, key=lambda v: (-float(hardness.get(v, 0.0)), v))
            picked += sorted(order[:b])
    return sorted(set(picked)), f"{policy}(b={budget})"


# ---------------------------------------------------------------------------
# 阈值校准：与 T22.calibrate_threshold 数值等价，但 FPR 扫描向量化
#   2.2 的实现对 precision_recall_curve 返回的每个阈值都调一次 sklearn
#   confusion_matrix（内部 np.unique），在 6 万 val 节点上 ≈ 220 s/次；
#   本实现用「负数分数排序 + searchsorted」一次算出所有阈值的 FP/TN → ~10 ms。
#   分支逻辑与返回点完全照抄 2.2，保证阈值一致。
# ---------------------------------------------------------------------------
def calibrate_threshold_fast(probs, labels, strategy="fpr_first",
                             target_recall=0.85, target_fpr=0.05):
    from sklearn.metrics import precision_recall_curve
    trojan_probs = probs[:, 1].detach().cpu().numpy()
    y_true = labels.detach().cpu().numpy().astype(int)
    _, recalls, thresholds = precision_recall_curve(y_true, trojan_probs)
    if len(thresholds) == 0:            # 所有分数相同（退化情形）
        return float(np.median(trojan_probs))
    neg = np.sort(trojan_probs[y_true == 0])                    # fp(t) = #{neg >= t}
    fp = len(neg) - np.searchsorted(neg, thresholds, side="left")
    tn = len(neg) - fp
    fprs = fp / (fp + tn + 1e-10)
    recalls_trimmed = recalls[:len(thresholds)]
    if strategy == "recall_first":
        valid = np.where(recalls_trimmed > target_recall)[0]
        best_idx = int(np.argmax(recalls_trimmed)) if len(valid) == 0 else \
            int(valid[int(np.argmax(fprs[valid]))])
    elif strategy == "fpr_first":
        valid = np.where(fprs <= target_fpr)[0]
        best_idx = int(np.argmin(fprs)) if len(valid) == 0 else \
            int(valid[int(np.argmax(recalls_trimmed[valid]))])
    else:
        best_idx = len(thresholds) // 2
    return float(thresholds[min(best_idx, len(thresholds) - 1)])


def verify_calibration(n_cases=3, n=4000, seed=0):
    """--verify-calibration：与 2.2 的 calibrate_threshold 逐例比对（慢，仅做一次性验证）"""
    rng = np.random.default_rng(seed)
    strategies = ["fpr_first", "recall_first", "fpr_first"]
    ok = True
    for k in range(n_cases):
        logits = torch.randn(n, 2) * 2.0
        if k % 2 == 0:
            logits[: max(1, n // 50), 1] += torch.randn(1).abs() * 2.5   # 少量木马
        probs = F.softmax(logits, dim=1)
        y = (torch.rand(n) < (0.03 if k % 2 == 0 else 0.3)).long()
        st = strategies[k % len(strategies)]
        a = calibrate_threshold_fast(probs, y, strategy=st, target_recall=0.85, target_fpr=0.05)
        b = float(T22.calibrate_threshold(probs, y, strategy=st, target_recall=0.85, target_fpr=0.05))
        same = abs(a - b) < 1e-12
        ok &= same
        print(f"  [{'OK ' if same else 'BAD'}] case{k} n={n} strategy={st} "
              f"fast={a:.10f} t22={b:.10f} diff={abs(a-b):.2e}")
    print(f"[VERDICT] 阈值校准等价性 {'ALL PASS' if ok else 'FAILED'}")
    return ok


# ---------------------------------------------------------------------------
# 指标：AP / Anchor-AP / Recall@budget / 配对一致性
# ---------------------------------------------------------------------------
def _ap(scores, labels):
    from sklearn.metrics import average_precision_score
    if len(scores) == 0 or labels.sum() == 0 or labels.sum() == len(labels):
        return float("nan")
    return float(average_precision_score(labels, scores))


def orig_circuit_metrics(orig, preds_o, threshold, circuits):
    """每个电路的 **orig 侧**指标（与具体视图无关的常数）：与旧表 `Type=ORIG` 行同一语义。

    旧实现（2.2）里同一电路的所有变体共享同一份 orig 指标（例如 rs232 的 AP_O 对 tr42/43/44 相同），
    这里照此实现：per-circuit 算一次，再被该电路的所有视图行复用。
    """
    out = {}
    fid = list(orig.file_ids)
    for c in sorted(set(circuits)):
        idx = [i for i, p in enumerate(fid) if p == c]
        if not idx:
            continue
        m = torch.tensor(idx, dtype=torch.long, device=preds_o.device)
        probs = F.softmax(preds_o[m], dim=1)
        y = orig.y[m]
        r = T22.calculate_full_metrics(probs, y, threshold)
        scores = probs[:, 1].cpu().numpy()
        y_np = y.cpu().numpy()
        rec = {"AP_O": r["AP"], "ROC-AUC_O": r["ROC-AUC"], "Recall_O": r["Recall"],
               "Precision_O": r["Precision"], "FPR_O": r["FPR"], "Macro-F1_O": r["Macro-F1"]}
        for b in (1, 2, 5):
            rec[f"Recall@{b}%_O"] = T22.recall_at_budget(scores, y_np, b / 100.0)
        rec["N_Nodes_O"] = int(len(idx))
        rec["N_Trojan_O"] = int(y.sum())
        out[c] = rec
    return out


def bootstrap_ci(data, n_boot=1000, seed=0):
    """与 2.2 的 `bootstrap_ci` 同式（1000 次重采样，取 2.5/97.5 分位），但固定随机种子以便复现"""
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    if len(data) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = [rng.choice(data, size=len(data), replace=True).mean() for _ in range(n_boot)]
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def compute_view_metrics(orig, trans, preds_o, preds_t, view, orig_prefix, threshold,
                         vidx_t, labels_t, orig_m=None):
    """单个测试视图的全部指标（节点级 TRANS + 电路级 ORIG + 锚点级 + 配对一致性）

    `orig_m` 是 `orig_circuit_metrics()` 给出的该视图所属电路的 orig 指标；给了就补
    `*_O` / `*_T` 别名列、`PR_Drop = AP_O − AP_T`、`Consistency_Gap = |PR_Drop|`
    （与 train_test2.2 的输出列语义一致，便于旧脚本/旧图表直接消费）。
    """
    rows = {}

    # --- 1) 视图内节点级（transported 标签）---
    idx = vidx_t[view]
    probs_t = F.softmax(preds_t[idx], dim=1)
    y_t = labels_t[idx]
    rows.update(T22.calculate_full_metrics(probs_t, y_t, threshold))
    scores_t = probs_t[:, 1].cpu().numpy()
    y_np = y_t.cpu().numpy()
    for b in (0.01, 0.02, 0.05):
        rows[f"Recall@{int(b*100)}%"] = T22.recall_at_budget(scores_t, y_np, b)

    # --- 1b) TRANS 侧的 `_T` 别名 + 与 ORIG 的差值（旧表列名兼容）---
    rows["AP_T"] = rows["AP"]
    rows["ROC-AUC_T"] = rows["ROC-AUC"]
    rows["Recall_T"] = rows["Recall"]
    rows["FPR_T"] = rows["FPR"]
    for b in (1, 2, 5):
        rows[f"Recall@{b}%_T"] = rows[f"Recall@{b}%"]
    if orig_m:
        rows.update(orig_m)
        rows["PR_Drop"] = rows["AP_O"] - rows["AP_T"]          # 与 2.2 同号：>0 表示变换后 AP 下降
        rows["Consistency_Gap"] = abs(rows["PR_Drop"])

    # --- 2) 锚点（provenance 血缘）上的指标 ---
    a = trans.alignment
    t_in_view = torch.zeros(trans.num_nodes, dtype=torch.bool, device=idx.device)
    t_in_view[idx] = True
    pair_mask = t_in_view[a[1]]
    idx_o, idx_t = a[0][pair_mask], a[1][pair_mask]
    rows["Anchor_Pairs"] = int(len(idx_o))
    rows["Anchor_Coverage"] = (len(idx_o) / max(1, len(idx))) if len(idx) else np.nan
    if len(idx_o) > 0:
        p_o = F.softmax(preds_o[idx_o], dim=1)[:, 1].cpu().numpy()
        p_t = F.softmax(preds_t[idx_t], dim=1)[:, 1].cpu().numpy()
        # Orig 锚点：同一 orig 节点可能被多对引用 → 去重后计算
        uniq_o, inv = np.unique(idx_o.cpu().numpy(), return_inverse=True)
        y_o_anchor = orig.y.cpu().numpy()[uniq_o]
        p_o_anchor = np.array([p_o[inv == k].mean() for k in range(len(uniq_o))])
        rows["Anchor_AP_Orig"] = _ap(p_o_anchor, y_o_anchor)
        rows["Anchor_Recall@5%_Orig"] = T22.recall_at_budget(p_o_anchor, y_o_anchor, 0.05)
        rows["Anchor_AP_Trans"] = _ap(p_t, labels_t[idx_t].cpu().numpy())
        # 锚点上的配对一致性（与 2.2 的 calc_detailed_consistency 同源）
        cm = T22.calc_detailed_consistency(preds_o, preds_t, orig.y, torch.stack([idx_o, idx_t]), threshold)
        rows.update(cm)
    else:
        for k in ("Anchor_AP_Orig", "Anchor_AP_Trans", "Anchor_Recall@5%_Orig",
                  "Paired_MAE", "Paired_MAE_PerOrig", "Flip_Rate", "Flip_Rate_PerOrig",
                  "Spearman_Corr", "Spearman_Corr_PerOrig", "Trojan_Drift", "Benign_Drift",
                  "TopK_Overlap"):
            rows[k] = np.nan
    return rows


# ---------------------------------------------------------------------------
# 训练 + 评测
# ---------------------------------------------------------------------------
def build_model(cfg, in_channels, device):
    m = str(cfg.get("model", {}).get("type", "single"))
    if m != "single":
        fusion = "gate" if "gate" in str(m) else ("attn" if "attn" in str(m) else "concat")
        return GINDual(in_channels=in_channels,
                       hidden_channels=cfg["model"]["hidden_channels"],
                       out_channels=cfg["model"]["out_channels"],
                       num_layers=int(cfg["model"].get("branch_layers", 2)),
                       split=int(cfg["model"].get("split", 29)),
                       fusion=fusion).to(device)
    return GINNodeClassifier(
        in_channels=in_channels,
        hidden_channels=cfg["model"]["hidden_channels"],
        out_channels=cfg["model"]["out_channels"],
        num_layers=cfg["model"]["num_layers"]).to(device)


class _DummyTrans:
    """mode1（不含 trans 项）时的轻量占位：train_mask 全 False + 空 alignment。

    T22.siamese_loss 只在这些地方读 data_t：train_mask（判空）、train_mask 下的 x[:,29]、
    alignment（一致性）。三者都能用占位对象安全满足，从而**完全跳过 trans 前向**。
    """

    def __init__(self, trans, align):
        self.train_mask = torch.zeros(1, dtype=torch.bool, device=trans.x.device)
        self.alignment = align


def view_hardness(model, trans, vidx_t, views, amp=False):
    """每个训练视图的平均 CE 损失（pred_hard 策略用；纯推理，不碰测试视图）"""
    model.eval()
    hard = {}
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
        logits = model(trans.x, trans.edge_index)
        for v in views:
            idx = vidx_t[v]
            if len(idx) == 0:
                hard[v] = 0.0
                continue
            loss = F.cross_entropy(logits[idx].float(), trans.y[idx], reduction="mean")
            hard[v] = float(loss.item())
    model.train()
    return hard


def view_inspection_hardness(model, trans, vidx_t, views, amp=False, budget_ratio=0.05):
    """inspection-hard 难度（Task 5）：不看 CE loss，而是看「有限检查预算下会不会漏掉 Trojan」。

    对每个训练视图 v 计算：
      * first_hit_rank：Trojan 节点里**分数最高者**在视图内的降序名次（1 = 最高分）；
      * recall@budget：预算 budget_ratio（默认 5%）内召回到的 Trojan 占比；
      * miss_budget：first_hit_rank / N（首次命中前要检查多少比例）。
    难度 = 0.4·(1 − recall@budget) + 0.4·miss_budget + 0.2·log2(1+first_hit_rank)/log2(1+N)。
    只使用**训练视图**的标签，测试视图任何阶段都不参与（与 pred_hard 同等合法）。
    """
    model.eval()
    hard = {}
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
        logits = model(trans.x, trans.edge_index)
        probs = F.softmax(logits.float(), dim=1)[:, 1]
        for v in views:
            idx = vidx_t[v]
            if len(idx) == 0:
                hard[v] = 0.0
                continue
            p = probs[idx].detach().cpu().numpy()
            y = trans.y[idx].detach().cpu().numpy().astype(int)
            n = len(p)
            pos = np.where(y == 1)[0]
            if n == 0 or len(pos) == 0:
                hard[v] = 0.0
                continue
            order = np.argsort(-p)                       # 降序名次
            rank_of = np.empty(n, dtype=np.int64)
            rank_of[order] = np.arange(1, n + 1)         # 1-based
            first_hit = int(rank_of[pos].min())
            k = max(1, int(n * budget_ratio))
            topk = order[:k]
            recall = float(y[topk].sum()) / float(len(pos))
            miss_budget = first_hit / float(n)
            hard[v] = float(0.4 * (1.0 - recall) + 0.4 * miss_budget
                            + 0.2 * np.log2(1 + first_hit) / np.log2(1 + n))
    model.train()
    return hard


def run_split(cfg, args, orig, trans, vidx_t, train_views, val_views, test_views,
              rng, tag, amp=False):
    """一次外层划分的训练：返回 (best_state_dict, threshold, train_log)"""
    device = orig.x.device
    model = build_model(cfg, orig.x.size(1), device)
    init_sha = hashlib.sha256(b"".join(
        np.ascontiguousarray(v.detach().cpu().numpy()).tobytes()
        for v in model.state_dict().values())).hexdigest()
    optimizer = torch.optim.Adam(model.parameters(), lr=float(cfg["train"]["lr"]),
                                 weight_decay=float(cfg["train"]["weight_decay"]))
    train_mode = int(cfg["train"]["train_mode"])
    include_trans = train_mode in (2, 3, 4)
    lambda_const = cfg["siamese"]["lambda_const"] if train_mode in (3, 4) else 0.0
    need_trans = include_trans or lambda_const > 0        # mode1：完全跳过 trans 前向（省时）
    epochs = int(cfg["train"]["epochs"])
    if args.steps_per_epoch > 1:
        # 原来 1 epoch = **1 次参数更新** ✗（全量 fold 一步 ~40 s ✗ → 100 轮只有 100 步 ✗ = 欠训练 ✗）
        # 这里把 epoch 拉长成 steps 次更新 ✓（`random` 策略下每次会重采样视图 ✓），val 频率按实际步数折算 ✓
        args.val_every = max(1, args.val_every // args.steps_per_epoch)
        epochs = epochs * args.steps_per_epoch
        print(f"[STEPS] steps-per-epoch={args.steps_per_epoch} → 内层 epoch={epochs}，val_every={args.val_every}")
    log_rows = []
    best = {"score": -1.0, "state": None, "thr": 0.5, "epoch": -1}
    hardness = {}
    n_nan = [0]
    updates = 0
    last_val = {}
    empty_align = torch.zeros((2, 0), dtype=torch.long, device=device)

    for epoch in range(epochs):
        t_ep = time.time()
        # --- 视图选择（合法：只用外层训练视图）---
        if args.view_policy == "pred_hard" and (epoch % max(1, args.hard_buffer) == 0):
            hardness = view_hardness(model, trans, vidx_t, train_views)
        elif args.view_policy == "inspection_hard" and (epoch % max(1, args.hard_buffer) == 0):
            hardness = view_inspection_hardness(model, trans, vidx_t, train_views, amp=amp)
        sel, sel_desc = select_train_views(train_views, args.view_policy,
                                           args.view_budget, rng, hardness)
        apply_masks(orig, trans, sel, val_views, test_views, vidx_t)
        if getattr(args, "trust_t", None) is not None:   # B1 ✓：unknown 节点不进 loss ✓
            trans.train_mask = trans.train_mask & args.trust_t
            if args.trust_o is not None:
                orig.train_mask = orig.train_mask & args.trust_o

        model.train()
        optimizer.zero_grad()
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
            preds_o = model(orig.x, orig.edge_index)
            fn_o = getattr(model, "fn_logits", None)      # C2：功能分支 logits ✓
            if need_trans:
                preds_t = model(trans.x, trans.edge_index)
                fn_t = getattr(model, "fn_logits", None)
                align = trans.alignment
            else:
                preds_t = torch.zeros(2, 2, device=device)
                fn_t = None
                align = empty_align                      # lambda_const=0 时不会被索引
            _lc_main = 0.0 if (args.func_const and fn_o is not None) else lambda_const
            loss_val, smic_o, smac_o, smic_t, smac_t, sdr_o, sdr_t = T22.siamese_loss(
                preds_o, preds_t,
                orig.y[orig.train_mask], trans.y[trans.train_mask] if need_trans
                else trans.y[:1],
                orig, trans if need_trans else _DummyTrans(trans, align),
                lambda_const=_lc_main,
                lambda_det=cfg["siamese"]["lambda_det"],
                lambda_nor=cfg["siamese"]["lambda_nor"],
                lambda_pos=cfg["siamese"]["lambda_pos"],
                trojan_w=cfg["siamese"]["trojan_w"],
                loss_type=cfg["siamese"]["loss_type"],
                use_hnm=False,
                const_mode=cfg["siamese"]["const_mode"],
                include_trans_loss=include_trans)
            if args.func_const and fn_o is not None and fn_t is not None:
                # C2/C4 ✓：一致性**只在功能分支**上算 ✓（结构分支不约束 ✓，保留木马结构细节 ✓）
                _lc_fn = T22.compute_consistency_loss(
                    fn_o, fn_t, trans.alignment, orig.train_mask, trans.train_mask,
                    mode="mse_logit", group_by_orig=True)
                loss_val = loss_val + float(lambda_const) * _lc_fn
            if (need_trans and getattr(args, "region_inv", None) is not None
                    and float(getattr(args, "region_loss", 0.0) or 0.0) > 0.0):
                # C6/P1 ✓：锥级 BCE（区域分数 = 区内节点正类 logit 的 max ✓，标签 = 区内是否含正 ✓）
                #   索引版 ✓：区域下标只算一次并缓存 → 无 `unique` ✗，step 回到 ~8–12 s ✓
                from phase2.ys.region_loss import region_bce_indexed
                loss_val = loss_val + float(args.region_loss) * region_bce_indexed(
                    preds_t[:, 1], args.region_inv, args.region_n, trans.y, trans.train_mask)
            # P2-D ✓：跨实现一致性（视图级 ✓）—— SAT 已证的实现对之间，平均 logit 差要被压小 ✓
            if need_trans and float(args.eq_loss) > 0 and getattr(args, "eq_idx", None):
                _p = preds_t[:, 1].float()
                _d = torch.stack([( _p[a].mean() - _p[b].mean()).abs() for a, b in args.eq_idx])
                loss_val = loss_val + float(args.eq_loss) * _d.mean()
            # P2-E ✓：结构相似抑制（A4 三胞胎 ✓）—— 木马视图分数要高于等价/死逻辑对照 ✓
            if need_trans and float(args.pair_loss) > 0 and getattr(args, "trip_idx", None):
                _p = preds_t[:, 1].float()
                _m = float(args.pair_margin)
                _t = []
                for _ti, _ci, _di in args.trip_idx:
                    _st = _p[_ti].mean()
                    _t.append(torch.relu(_m - (_st - _p[_ci].mean())))
                    _t.append(torch.relu(_m - (_st - _p[_di].mean())))
                if _t:
                    loss_val = loss_val + float(args.pair_loss) * torch.stack(_t).mean()
            # P2-D（**节点级**）✓：SAT 已证节点对上压 logit 差 ✓（抽样 ✓ 控显存 ✓）
            if need_trans and float(args.eq_loss_node) > 0 and getattr(args, "eq_node", None) is not None:
                _p = preds_t[:, 1].float()
                _a, _b, _k = args.eq_node
                _tm = getattr(trans, "train_mask", None)

                def _eq_part(_aa, _bb, _n):
                    if _aa is None or _aa.numel() == 0:
                        return None
                    if _tm is not None:
                        _keep = _tm[_aa] & _tm[_bb]
                        _aa, _bb = _aa[_keep], _bb[_keep]
                    if _aa.numel() == 0:
                        return None
                    _sel = torch.randint(0, _aa.numel(),
                                         (min(int(_n), int(_aa.numel())),),
                                         device=_aa.device)
                    return (_p[_aa[_sel]] - _p[_bb[_sel]]).abs().mean()

                _cap = int(args.node_pair_cap)
                _pos = getattr(args, "eq_node_pos", None)
                _neg = getattr(args, "eq_node_neg", None)
                if _pos is not None or _neg is not None:
                    _half = max(1, _cap // 2)
                    _lp = _eq_part(_pos[0], _pos[1], _half) if _pos is not None else None
                    _ln = _eq_part(_neg[0], _neg[1], _half) if _neg is not None else None
                    _wp = float(getattr(args, "eq_pos_scale", 1.0))
                    _wn = float(getattr(args, "eq_neg_scale", 1.0))
                    _num = 0.0
                    _den = 0.0
                    if _lp is not None and _wp > 0:
                        _num = _num + _wp * _lp
                        _den += _wp
                    if _ln is not None and _wn > 0:
                        _num = _num + _wn * _ln
                        _den += _wn
                    if _den > 0:
                        loss_val = loss_val + float(args.eq_loss_node) * (_num / _den)
                else:
                    # Old npz: no label split available -> old behaviour.
                    if _tm is not None:
                        _keep = _tm[_a] & _tm[_b]
                        _a, _b = _a[_keep], _b[_keep]
                    if _a.numel():
                        _sel = torch.randint(0, _a.numel(), (min(_cap, _a.numel()),),
                                             device=_a.device)
                        loss_val = loss_val + float(args.eq_loss_node) * (
                            _p[_a[_sel]] - _p[_b[_sel]]).abs().mean()
            # P2-E（**节点级**）✓：SAT 已证对里，木马节点要比等价/死逻辑对照节点高 margin ✓
            if need_trans and float(args.pair_loss_node) > 0 and getattr(args, "pair_node", None) is not None:
                _p = preds_t[:, 1].float()
                _a, _b = args.pair_node
                _tm = getattr(trans, "train_mask", None)
                if _tm is not None:
                    _keep = _tm[_a] & _tm[_b]
                    _a, _b = _a[_keep], _b[_keep]
                if _a.numel():
                    _sel = torch.randint(0, _a.numel(), (min(int(args.node_pair_cap), _a.numel()),),
                                         device=_a.device)
                    _gap = _p[_a[_sel]] - _p[_b[_sel]]
                    loss_val = loss_val + float(args.pair_loss_node) * torch.relu(
                        float(args.pair_margin) - _gap).mean()
        loss_val.backward()
        if not torch.isfinite(loss_val):
            # 防御 ✓：非有限损失**不要** step ✗（否则一步就把权重污染成 NaN ✗，之后整轮都学不动 ✗）
            optimizer.zero_grad(set_to_none=True)
            n_nan[0] += 1
            if n_nan[0] % 20 == 1:
                print(f"[WARN] 非有限 loss（{n_nan[0]} 次）→ 跳过该步")
            continue
        grad_norm = float(torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0))
        grad_finite = int(all(bool(torch.isfinite(p.grad).all())
                              for p in model.parameters() if p.grad is not None))
        optimizer.step()
        updates += 1

        # --- 验证（val 视图，用于阈值校准与选模型）---
        cur_ap_o = cur_ap_t = float("nan")
        if (epoch + 1) % max(1, args.val_every) == 0 or epoch == epochs - 1:
            model.eval()
            with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
                lo = model(orig.x, orig.edge_index)
                lt = model(trans.x, trans.edge_index)
                vp_o = F.softmax(lo[orig.val_mask].float(), dim=1)
                vp_t = F.softmax(lt[trans.val_mask].float(), dim=1)
                vl_o, vl_t = orig.y[orig.val_mask], trans.y[trans.val_mask]
                thr = None
                # 优先用 trans 的 val 视图校准（其标签 = provenance 传播标签）；
                # orig 侧按电路划分，可能与训练电路重合而为空，故作为回退。
                for probs, labels in ((vp_t, vl_t), (vp_o, vl_o)):
                    s = int(labels.sum())
                    if len(labels) > 1 and 0 < s < len(labels):
                        thr = calibrate_threshold_fast(
                            probs, labels, strategy=cfg["train"]["thr_strategy"],
                            target_recall=0.85, target_fpr=0.05)
                        break
                if int(vl_t.sum()) > 0 and int(vl_t.sum()) < len(vl_t):
                    cur_ap_t = float(_ap(vp_t[:, 1].cpu().numpy(), vl_t.cpu().numpy()))
                if int(vl_o.sum()) > 0 and int(vl_o.sum()) < len(vl_o):
                    cur_ap_o = float(_ap(vp_o[:, 1].cpu().numpy(), vl_o.cpu().numpy()))
                last_val = dict(epoch=epoch, val_AP_t=cur_ap_t, val_AP_o=cur_ap_o,
                                threshold=(float(thr) if thr is not None else None),
                                n_val_t=int(len(vl_t)), n_val_o=int(len(vl_o)))
            if thr is None:
                print(f"    [WARN] epoch {epoch}: val 视图缺少正/负样本之一，阈值沿用 {best['thr']:.3f}")
                thr = float(best["thr"])
            score = cur_ap_t if not np.isnan(cur_ap_t) else (cur_ap_o if not np.isnan(cur_ap_o) else -1.0)
            if score > best["score"]:
                best.update({"score": score, "epoch": epoch,
                             "state": {k: v.detach().clone() for k, v in model.state_dict().items()},
                             "thr": float(thr)})
        log_rows.append({"split": tag, "epoch": epoch, "loss": float(loss_val.detach().item()),
                         "updates": int(updates), "grad_norm": float(grad_norm),
                         "grad_finite": int(grad_finite), "init_sha": init_sha,
                         "n_sel_views": len(sel), "sel_desc": sel_desc,
                         "epoch_sec": round(time.time() - t_ep, 2),
                         "val_AP_orig": cur_ap_o, "val_AP_trans": cur_ap_t,
                         "best_val_AP": best["score"], "best_epoch": best["epoch"],
                         "f1_micro_o": float(torch.as_tensor(smic_o).detach().item()),
                         "f1_macro_o": float(torch.as_tensor(smac_o).detach().item()),
                         "sdr_o": float(torch.as_tensor(sdr_o).detach().item()),
                         "sdr_t": float(torch.as_tensor(sdr_t).detach().item())})
        # 可观测性 ✓：epoch 内部原本**没有任何打印** ✗ → 长跑时无法判断进度 ✗
        # 现在每个 val 点打一行 ✓（60 epoch × ~69 s 时也能知道走到哪 ✓）
        if (epoch + 1) % max(1, args.val_every) == 0 or epoch == epochs - 1:
            print(f"[EPOCH {epoch + 1}/{epochs}] loss={float(loss_val.detach().item()):.4f} "
                  f"step={time.time() - t_ep:.1f}s val_AP_t={cur_ap_t:.4f} "
                  f"best={best['score']:.4f}@{best['epoch']}", flush=True)
        if (epoch + 1) % 5 == 0 and torch.cuda.is_available():
            # 防碎片累积 ✓：v3.1（3.22 M 节点）曾在 epoch ~45 因碎片 OOM ✗
            torch.cuda.empty_cache()
    if getattr(args, "smoke_final_ckpt", None):
        Path(args.smoke_final_ckpt).parent.mkdir(parents=True, exist_ok=True)
        torch.save({"state_dict": model.state_dict(), "split": str(tag),
                    "updates": int(updates), "threshold": float(best["thr"]),
                    "final_val": last_val, "seed": int(cfg["train"]["seed_id"]),
                    "train_mode": int(cfg["train"]["train_mode"]),
                    "in_channels": int(orig.x.size(1))},
                   Path(args.smoke_final_ckpt))
    if log_rows:
        log_rows[-1].update({"final_val_AP_t": last_val.get("val_AP_t"),
                             "final_val_AP_o": last_val.get("val_AP_o"),
                             "final_threshold": last_val.get("threshold")})
    if best["state"] is not None:
        model.load_state_dict(best["state"])
    model.eval()
    if args.dump_scores:
        # 给"模型融合"用 ✓：把 test / val 节点的概率存下来（idx 是**全图节点索引** ✓）
        with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
            lt = model(trans.x, trans.edge_index)
            p = F.softmax(lt.float(), dim=1)[:, 1]
        m = (trans.test_mask | trans.val_mask)
        idx = m.nonzero(as_tuple=False).view(-1)
        np.savez(args.dump_scores, idx=idx.cpu().numpy(),
                 score=p[idx].cpu().numpy(), test=trans.test_mask[idx].cpu().numpy())
        print(f"[DUMP] scores -> {args.dump_scores}（{len(idx)} 个节点，测试 {int(trans.test_mask.sum())}）")
    return model, best["thr"], log_rows


SUM_METRICS = ["AP", "ROC-AUC", "Precision", "Recall", "FPR", "Macro-F1",
               "Recall@1%", "Recall@2%", "Recall@5%",
               "AP_T", "ROC-AUC_T", "Recall_T", "FPR_T",
               "AP_O", "ROC-AUC_O", "Recall_O", "FPR_O", "Precision_O", "Macro-F1_O",
               "Recall@1%_O", "Recall@2%_O", "Recall@5%_O",
               "Recall@1%_T", "Recall@2%_T", "Recall@5%_T",
               "PR_Drop", "Consistency_Gap",
               "Anchor_AP_Orig", "Anchor_AP_Trans", "Anchor_Recall@5%_Orig", "Anchor_Coverage",
               "Paired_MAE", "Paired_MAE_PerOrig", "Flip_Rate", "Flip_Rate_PerOrig",
               "Spearman_Corr", "Spearman_Corr_PerOrig",
               "Trojan_Drift", "Benign_Drift", "TopK_Overlap"]


def evaluate_split(model, orig, trans, vidx_t, test_views, threshold, meta, split_name,
                   amp=False):
    """对给定测试视图逐个评测 → variant 级行（含 CEC 状态、电路、深度、算子）"""
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.bfloat16, enabled=amp):
        preds_o = model(orig.x, orig.edge_index).float()
        preds_t = model(trans.x, trans.edge_index).float()
    rows = []
    present = [v for v in test_views if v in vidx_t]
    pv = meta["per_view"]
    # 注意：`orig.file_ids` 存的是**网表 stem**（rs232t1000），而 per_view['circuit'] 是短名（rs232）
    # → orig 指标必须按 stem 关联（旧表的 ORIG 行命名也是 <stem>_ORIG）。
    stems = [pv.get(v, {}).get("file_stem", v.split("__")[0]) for v in present]
    fam_of = {}
    for v, st in zip(present, stems):
        fam_of.setdefault(st, pv.get(v, {}).get("circuit", st))
    orig_m_all = orig_circuit_metrics(orig, preds_o, threshold, stems)

    # --- ORIG 行（每电路一行，与旧表 `Type=ORIG` 同语义）---
    for st in sorted(set(stems)):
        om = orig_m_all.get(st, {})
        rows.append({
            "Split": split_name, "View": f"{st}_ORIG", "Test_File": f"{st}_ORIG",
            "Circuit": fam_of.get(st, st), "Operators": "", "Depth": np.nan, "Seed": np.nan,
            "CEC_Status": "", "N_Nodes": om.get("N_Nodes_O", np.nan),
            "N_Trojan": om.get("N_Trojan_O", np.nan),
            "Threshold": threshold, "Type": "ORIG", **om})

    for v, st in zip(present, stems):
        vm = pv.get(v, {})
        circ = vm.get("circuit", v.split("__")[0])
        m = compute_view_metrics(orig, trans, preds_o, preds_t, v, vm.get("file_stem", ""),
                                 threshold, vidx_t, trans.y, orig_m=orig_m_all.get(st))
        idx = vidx_t[v]
        rows.append({
            "Split": split_name, "View": v, "Test_File": v, "Circuit": circ,
            "Operators": vm.get("operators", ""), "Depth": vm.get("depth", 0),
            "Seed": vm.get("seed", -1), "CEC_Status": vm.get("cec_status", "UNKNOWN"),
            "N_Nodes": int(len(idx)), "N_Trojan": int(trans.y[idx].sum()),
            "Threshold": threshold, "Type": "TRANS", **m})
    return rows


def write_loco_summary(rows, out_dir: Path, threshold=None, seed=0):
    """旧形态汇总表（列语义与 2.2 的 `detailed_loco_summary.csv` 一致）：

    * 每电路一行 `Type=ORIG`（`Test_File=<circuit>_ORIG`）：该电路原网表在同一阈值下的指标；
    * 每个测试视图一行 `Type=TRANS`：**两侧并排**（`*_O` / `*_T`）+ `PR_Drop = AP_O − AP_T`
      + `Consistency_Gap = |PR_Drop|` + 全部配对一致性指标；
    * 尾部统计行：`RUNNING_MEAN` / `RUNNING_STD`（对 TRANS 行）与
      `CI_95_LOW` / `CI_95_HIGH` / `WILCOXON_P`（对**电路级**聚合做 bootstrap + 配对 Wilcoxon，与 2.2 同式）。

    fold 模式下 `Split` 只有 "ALL"；loco 模式下 `Split` 是被留出的电路。两种模式都会写该文件。
    """
    df = pd.DataFrame(rows)
    if df.empty:
        return None
    legacy_order = ["Test_File", "Split", "Circuit", "Type", "AP_O", "AP_T", "ROC-AUC_O", "ROC-AUC_T",
                    "Recall_O", "Recall_T", "FPR_O", "FPR_T", "Precision_O", "Macro-F1_O",
                    "Recall@1%_O", "Recall@2%_O", "Recall@5%_O",
                    "Recall@1%_T", "Recall@2%_T", "Recall@5%_T",
                    "Threshold", "PR_Drop", "Consistency_Gap", "N_Nodes", "N_Trojan",
                    "Operators", "Depth", "Seed", "CEC_Status", "Anchor_Pairs", "Anchor_Coverage",
                    "Anchor_AP_Orig", "Anchor_AP_Trans", "Anchor_Recall@5%_Orig",
                    "Paired_MAE", "Paired_MAE_PerOrig", "Trojan_Drift", "Benign_Drift",
                    "Flip_Rate", "Flip_Rate_PerOrig", "Spearman_Corr", "Spearman_Corr_PerOrig",
                    "TopK_Overlap"]
    head = [c for c in legacy_order if c in df.columns]
    tail = [c for c in df.columns if c not in head]
    df = df[head + tail]
    trans = df[df["Type"] == "TRANS"].copy()
    orig = df[df["Type"] == "ORIG"].copy()
    if trans.empty:
        print(f"[导出] loco_summary.csv -> {out_dir / 'loco_summary.csv'}（{len(df)} 行，无 TRANS 行）")
        return df
    num = trans.select_dtypes(include=[np.number]).columns
    stats = [pd.Series({"Test_File": "RUNNING_MEAN", **trans[num].mean()}),
             pd.Series({"Test_File": "RUNNING_STD", **trans[num].std()}),
             pd.Series({"Test_File": "N_VIEWS", "N_Nodes": len(trans)})]

    # 电路级聚合 → bootstrap CI + 配对 Wilcoxon（与 2.2 的 circuit_df 口径一致）
    circ_rows = []
    orig_idx = orig.set_index("Circuit") if "Circuit" in orig.columns else None
    for c, sub in trans.groupby("Circuit"):
        row = {"Test_File": c, "Type": "CIRCUIT_MACRO", "Circuit": c}
        if orig_idx is not None and c in orig_idx.index:
            for k in ("AP_O", "ROC-AUC_O", "Recall_O", "FPR_O", "Threshold",
                      "Recall@1%_O", "Recall@2%_O", "Recall@5%_O"):
                if k in orig_idx.columns:
                    row[k] = orig_idx.loc[c, k]
        for k in num:
            if k not in ("N_Nodes", "N_Trojan") and k in sub.columns:
                row.setdefault(k, float(sub[k].mean()))
        circ_rows.append(row)
    circ_df = pd.DataFrame(circ_rows)
    if len(circ_df) >= 2:
        ci_low, ci_high = {}, {}
        for col in circ_df.select_dtypes(include=[np.number]).columns:
            lo, hi = bootstrap_ci(circ_df[col].values, seed=seed)
            ci_low[col], ci_high[col] = lo, hi
        p_val = 1.0
        try:
            if {"AP_O", "AP_T"}.issubset(circ_df.columns):
                v_o = circ_df["AP_O"].values.astype(float)
                v_t = circ_df["AP_T"].values.astype(float)
                m = ~(np.isnan(v_o) | np.isnan(v_t))
                if m.sum() >= 2 and not np.array_equal(v_o[m], v_t[m]):
                    from scipy.stats import wilcoxon
                    _, p_val = wilcoxon(v_o[m], v_t[m])
        except Exception as e:      # noqa: BLE001
            print(f"[WARN] Wilcoxon 失败: {e}")
        stats += [pd.Series({"Test_File": "CI_95_LOW", **ci_low}),
                  pd.Series({"Test_File": "CI_95_HIGH", **ci_high}),
                  pd.Series({"Test_File": "WILCOXON_P", "AP_O": float(p_val)})]
        stats.append(pd.Series({"Test_File": "N_CIRCUITS", "N_Nodes": len(circ_df)}))
        circ_df.to_csv(out_dir / "loco_circuit_summary.csv", index=False, encoding="utf-8-sig")

    out = pd.concat([df, pd.DataFrame(stats)], ignore_index=True)
    out.to_csv(out_dir / "loco_summary.csv", index=False, encoding="utf-8-sig")
    print(f"[导出] loco_summary: {out_dir / 'loco_summary.csv'}"
          f"（{len(df)} 行 + {len(stats)} 行统计，含 CI/Wilcoxon）")
    return out


def summarize(rows, out_dir: Path, train_log_rows, cfg, args, tag, device="cpu", amp=False):
    """写 variant_level_summary.csv / circuit_level_summary.csv（含 MACRO 宏平均）"""
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    variant_csv = out_dir / "variant_level_summary.csv"
    df.to_csv(variant_csv, index=False, encoding="utf-8-sig")
    print(f"[导出] variant-level: {variant_csv}（{len(df)} 行 = 每个测试视图一行）")

    if df.empty:
        return df, pd.DataFrame()
    num_cols = [c for c in SUM_METRICS if c in df.columns]
    per_circuit = df.groupby("Circuit", sort=True)[num_cols].mean(numeric_only=True)
    per_circuit.insert(0, "N_Views", df.groupby("Circuit").size())
    per_circuit.insert(1, "CEC_All_Pass",
                       df.groupby("Circuit")["CEC_Status"].apply(lambda s: bool((s == "PASS").all())))
    per_circuit = per_circuit.reset_index()

    # 电路级宏平均（先电路内平均，再对电路取平均）—— 取代 2.2 的 RUNNING_MEAN 逐行平均
    macro_mean = per_circuit[num_cols].mean(numeric_only=True)
    macro_std = per_circuit[num_cols].std(numeric_only=True)
    macro_rows = [
        {"Circuit": "MACRO_MEAN", "N_Views": int(per_circuit["N_Views"].sum()),
         "CEC_All_Pass": bool(per_circuit["CEC_All_Pass"].all()), **macro_mean.to_dict()},
        {"Circuit": "MACRO_STD", "N_Views": int(per_circuit["N_Views"].sum()),
         "CEC_All_Pass": bool(per_circuit["CEC_All_Pass"].all()), **macro_std.to_dict()},
    ]
    circuit_df = pd.concat([per_circuit, pd.DataFrame(macro_rows)], ignore_index=True)
    circuit_csv = out_dir / "circuit_level_summary.csv"
    circuit_df.to_csv(circuit_csv, index=False, encoding="utf-8-sig")
    print(f"[导出] circuit-level: {circuit_csv}（{len(per_circuit)} 电路 + MACRO_MEAN/STD）")

    # 训练日志 / 运行配置
    # 训练日志 / 运行配置
    write_loco_summary(rows, out_dir, threshold=None, seed=int(cfg["train"]["seed_id"]))
    if train_log_rows:
        pd.DataFrame(train_log_rows).to_csv(out_dir / "train_log.csv", index=False,
                                            encoding="utf-8-sig")
    (out_dir / "run_config.json").write_text(json.dumps({
        "tag": tag, "work_dir": str(args.work_dir), "fold_json": str(args.fold_json),
        "circuits": args.circuits, "fold_mode": args.fold_mode,
        "view_policy": args.view_policy, "view_budget": args.view_budget,
        "epochs": int(cfg["train"]["epochs"]), "seed": int(cfg["train"]["seed_id"]),
        "train_mode": int(cfg["train"]["train_mode"]),
        "siamese": cfg["siamese"], "in_channels": int(cfg["model"]["in_channels"]),
        "device": str(device),
        "amp": bool(amp),
        "normalization": {"base_fit": args.norm_fit, "extra": args.norm_extra,
                          "extra_node_file": args.extra_node_file,
                          "extra_dense_prefix": args.extra_dense_prefix,
                          "no_cov_flag": args.no_cov_flag},
        "torch_version": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "device_name": (torch.cuda.get_device_name(device)
                        if torch.device(device).type == "cuda" else "cpu"),
        "peak_vram_mb": (round(torch.cuda.max_memory_allocated(device) / 2 ** 20, 1)
                         if torch.device(device).type == "cuda" else None),
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== MACRO（电路级宏平均）===")
    for k in ["AP", "Anchor_AP_Orig", "Anchor_AP_Trans", "Recall@1%", "Recall@5%",
              "Paired_MAE", "Flip_Rate", "Spearman_Corr"]:
        if k in macro_mean.index:
            print(f"  {k:<20} {macro_mean[k]:.4f} ± {macro_std.get(k, float('nan')):.4f}")
    return df, circuit_df


def _jsonable(o):
    """numpy / torch 标量 → 原生 Python（供断点落盘 ✓）"""
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, float) and np.isnan(o):
        return float("nan")
    return str(o)


def save_partial(out_dir: Path, rows, logs, done):
    """每个外层 split 跑完就把**已有行**写盘 ✓（断电只丢当前 split ⚠️，不丢整 run ✗）"""
    try:
        (out_dir / "rows_partial.json").write_text(
            json.dumps(rows, default=_jsonable, ensure_ascii=False), encoding="utf-8")
        (out_dir / "train_log_partial.json").write_text(
            json.dumps(logs, default=_jsonable, ensure_ascii=False), encoding="utf-8")
        (out_dir / "done_splits.json").write_text(
            json.dumps([str(d) for d in done], ensure_ascii=False), encoding="utf-8")
        print(f"    [checkpoint] 已完成 split {len(done)} 个 ✓ -> {out_dir.name}")
    except Exception as e:                     # 落盘失败不影响训练 ✓
        print(f"    [WARN] checkpoint 写入失败: {e}")


def load_partial(out_dir: Path):
    """读断点 ✓：返回 (rows, logs, done set)；没有断点则返回空 ✓"""
    rows, logs, done = [], [], set()
    try:
        dp = out_dir / "done_splits.json"
        if dp.exists():
            done = set(json.loads(dp.read_text(encoding="utf-8")))
        if done and (out_dir / "rows_partial.json").exists():
            rows = json.loads((out_dir / "rows_partial.json").read_text(encoding="utf-8"))
            rows = [r for r in rows if str(r.get("Split")) in done]
        lp = out_dir / "train_log_partial.json"
        if done and lp.exists():
            logs = json.loads(lp.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] 断点读取失败（忽略，从头跑）: {e}")
        return [], [], set()
    return rows, logs, done


def main():
    args = parse_args()
    if args.verify_calibration:
        return 0 if verify_calibration() else 1
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    if args.epochs:
        cfg["train"]["epochs"] = int(args.epochs)
    if args.seed:
        cfg["train"]["seed_id"] = int(args.seed)
    if args.train_mode:
        cfg["train"]["train_mode"] = int(args.train_mode)
    seed_everything(int(cfg["train"]["seed_id"]))

    device = torch.device(cfg["train"]["device"] if torch.cuda.is_available() else "cpu")
    amp = bool(args.amp) and device.type == "cuda"
    pt_dir = (args.pt_dir or (args.work_dir / "data" / "processed")).resolve()
    orig, trans, meta = load_fold(pt_dir)
    # ---- C6/P1 ✓：区域级监督（λ>0 才做 ✓；默认关闭 → 现有实验完全不变 ✓）----
    args.region_t, args.region_np = None, None
    args.region_inv, args.region_inv_np, args.region_n = None, None, 0
    if float(getattr(args, "region_loss", 0.0) or 0.0) > 0.0:
        import time as _time
        from phase2.ys.region_loss import (build_regions, region_stats,
                                           regions_to_index)
        _cache = (CUR.parent / "_devcfg" / "region_cache" /
                  f"{args.work_dir.name}_{args.region_mode}.npz")
        if _cache.exists():                      # 索引缓存 ✓（建一次 ~1 min，之后秒开 ✓）
            _z = np.load(_cache)
            _inv, _nreg = _z["inv"], int(_z["n"])
            print(f"[C6] 复用区域索引缓存 ✓ {_cache.name}（区域 {_nreg}）")
        else:
            _t0 = _time.time()
            _vidx = view_index(trans)
            _view_ids = np.zeros(trans.x.size(0), np.int64)
            for _k, (_v, _ix) in enumerate(sorted(_vidx.items())):
                _view_ids[np.asarray(_ix.cpu() if torch.is_tensor(_ix) else _ix)] = _k
            _reg = build_regions(np.asarray(trans.x, np.float32), trans.edge_index.numpy(),
                                 _view_ids, args.work_dir / "gatelookup_recommended.json",
                                 args.region_mode)
            _st = region_stats(_reg)
            _inv, _nreg = regions_to_index(_reg)
            _cache.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(_cache, inv=_inv, n=np.int64(_nreg))
            print(f"[C6] 区域索引已建并缓存 ✓ {_cache.name}｜区域 {_nreg}｜"
                  f"平均 {_st['mean_size']:.1f} 门/区｜中位 {_st['median_size']:.0f}｜"
                  f"单点占比 {_st['frac_singleton']:.2f}｜{_time.time() - _t0:.0f}s")
            if _st["frac_singleton"] > 0.8:
                print("[WARN] 区域绝大多数是单点 ✗ → 区域损失≈节点损失 ⚠️（请换 --region-mode dff ✓）")
            del _reg
        args.region_inv_np, args.region_n = _inv, int(_nreg)
    for d in (orig, trans):
        d.x = d.x.to(device)
        d.edge_index = d.edge_index.to(device)
        d.y = d.y.to(device)
        if getattr(d, "alignment", None) is not None:
            d.alignment = d.alignment.to(device)   # 一致性损失/锚点指标都按设备对齐
    if getattr(args, "region_inv_np", None) is not None:
        args.region_inv = torch.from_numpy(np.asarray(args.region_inv_np, np.int64)).to(device)
        args.region_inv_np = None
        print(f"[C6] 区域索引已上设备 ✓ n_reg={args.region_n}｜λ={args.region_loss:g}")
    if args.extra_feats in ("cone5", "satrel", "satrel_node"):
        # P2-C ✓：SAT 功能关系（视图级 ✓ / 节点级 ✓）与 C1/C3 的锥特征走同一条注入路径 ✓
        args.extra_slice = None
        if args.extra_feats == "cone5":
            cf, cfo = pt_dir / "cone_feats.npy", pt_dir / "cone_feats_orig.npy"
            hint = "先跑 phase2/ys/cone_feats.py"
        elif args.extra_feats == "satrel":
            cf, cfo = pt_dir / "satrel_view_feats.npy", pt_dir / "satrel_view_feats_orig.npy"
            hint = "先跑 phase2/ys/satrel_view_feats.py（需 node_pairs_sweep.csv ✓）"
        else:
            _nf = str(getattr(args, "extra_node_file", "") or "satrel_node_feats_sat.npy")
            cf, cfo = pt_dir / _nf, None
            hint = "先跑 phase2/ys/satrel_node_feats_sat.py（需 functional_relations.csv ✓）"
        if not cf.exists():
            raise SystemExit(f"[ERROR] 缺 {cf}（{hint}）")
        _base_dim = int(trans.x.size(1))
        C = torch.from_numpy(np.load(cf)).float()          # ⚠️ 留在 **CPU** ✓（GPU 侧 cat 会碎显存 ✗）
        if args.norm_extra == "bounded":
            if args.extra_feats != "satrel_node" or args.extra_dense_prefix:
                raise SystemExit("bounded extra normalization requires satrel_node and dense-prefix=0")
            if not bool(torch.isfinite(C).all()) or float(C.min()) < 0 or float(C.max()) > 1:
                raise SystemExit("bounded extra features must be finite and already in [0,1]")
        mk = None
        if args.extra_feats == "satrel_node":
            # 9 维核心子集 ✓（最后一列 = covered 标记 ✓，已含 mask ✓ 不再追加 ✓）
            args.extra_mask_any = C[:, -1] > 0
            if args.no_cov_flag:
                C = C.clone()
                C[:, -1] = 0.0            # 敏感性对照 ⚠️：去掉"是否有 SAT 证据"这一维 ✓
                print("[ABL] satrel_node：**covered 标记已置零** ⚠️（无掩码敏感性对照 ✓）")
        # CPU 拼接 → 一次性上传 ✓（避免 GPU 侧多次 cat/切片把 8 GB 卡打爆 ✗）
        trans.x = torch.cat([trans.x.cpu(), C], 1).to(trans.x.device)
        if cfo is not None and cfo.exists():
            Co = torch.from_numpy(np.load(cfo)).float()
        else:
            Co = torch.zeros(orig.x.size(0), C.size(1), dtype=C.dtype)
        orig.x = torch.cat([orig.x.cpu(), Co], 1).to(orig.x.device)
        args.extra_slice = (int(_base_dim), int(trans.x.size(1)))
        args.extra_norm_n = C.size(1) - 1 if args.extra_feats == "satrel_node" else C.size(1)
        if args.extra_feats == "satrel_node":
            args.extra_mask_any = args.extra_mask_any.to(trans.x.device)
        print(f"[EXTRA] 追加 {args.extra_feats} 特征 {C.size(1)} 维 ✓（覆盖 "
              f"{int(args.extra_mask_any.sum()) if getattr(args, 'extra_mask_any', None) is not None else 'n/a'}"
              f" 个 trans 节点 ✓）"
              f" → trans {trans.x.size(1)} / orig {orig.x.size(1)} 维")
    # P2-D/E ✓：读视图分组（`satrel_groups.json` ✓，B09 生成 ✓）
    if args.eq_loss > 0 or args.pair_loss > 0:
        gp = pt_dir / "satrel_groups.json"
        if not gp.exists():
            raise SystemExit(f"[ERROR] 缺 {gp}（先跑 phase2/ys/satrel_view_feats.py）")
        _g = json.loads(gp.read_text(encoding="utf-8"))
        args.eq_idx = [((torch.as_tensor(x, dtype=torch.long, device=device)),
                        (torch.as_tensor(y, dtype=torch.long, device=device)))
                       for x, y in _g.get("eq_pairs", [])]
        args.trip_idx = [(torch.as_tensor(t, dtype=torch.long, device=device),
                          torch.as_tensor(c, dtype=torch.long, device=device),
                          torch.as_tensor(dd, dtype=torch.long, device=device))
                         for t, c, dd in _g.get("triplets", [])]
        print(f"[P2] eq_pairs={len(args.eq_idx)}（λ_eq={args.eq_loss:g}）｜"
              f"triplets={len(args.trip_idx)}（λ_pair={args.pair_loss:g}）")
    # P2-D/E（**节点级**）✓：SAT 已证节点对（`satrel_node_pairs.npz` ✓）
    args.eq_node = args.pair_node = None
    if float(args.eq_loss_node) > 0 or float(args.pair_loss_node) > 0:
        npz_p = pt_dir / str(getattr(args, "node_pairs_file", "satrel_node_pairs.npz"))
        if not npz_p.exists():
            raise SystemExit(f"[ERROR] 缺 {npz_p} ✗（先跑 phase2/ys/satrel_node_pairs_npz.py ✓）")
        _z = np.load(npz_p)
        _a, _b, _k = _z["a"], _z["b"], _z["kind"]
        args.eq_node_pos = args.eq_node_neg = None
        if float(args.eq_loss_node) > 0:
            _m0 = _k == 0
            if _m0.any():
                _a0, _b0 = _a[_m0], _b[_m0]
                args.eq_node = (torch.as_tensor(_a0, dtype=torch.long, device=device),
                                torch.as_tensor(_b0, dtype=torch.long, device=device),
                                int(_m0.sum()))
                # 2026-10-24: kind0 is mostly benign-benign; balance positive
                # consistency pairs so D is not just negative smoothing.
                _yy = getattr(trans, "y", None)
                if _yy is not None:
                    _yn = _yy.detach().cpu().numpy() if hasattr(_yy, "detach") else np.asarray(_yy)
                    _pp = (_yn[_a0] == 1) & (_yn[_b0] == 1)
                    if _pp.any():
                        args.eq_node_pos = (torch.as_tensor(_a0[_pp], dtype=torch.long, device=device),
                                            torch.as_tensor(_b0[_pp], dtype=torch.long, device=device))
                    if (~_pp).any():
                        args.eq_node_neg = (torch.as_tensor(_a0[~_pp], dtype=torch.long, device=device),
                                            torch.as_tensor(_b0[~_pp], dtype=torch.long, device=device))
                    print(f"[P2-node] D balance: pos={int(_pp.sum())} neg={int((~_pp).sum())}")
        if float(args.pair_loss_node) > 0:
            _m1 = _k == 1
            if _m1.any():
                args.pair_node = (torch.as_tensor(_a[_m1], dtype=torch.long, device=device),
                                  torch.as_tensor(_b[_m1], dtype=torch.long, device=device))
        print(f"[P2-node] consistency={int((_k == 0).sum())}（λ={args.eq_loss_node:g}）｜"
              f"pair_trojan={int((_k == 1).sum())}（λ={args.pair_loss_node:g}）｜"
              f"pair_other={int((_k == 2).sum())}（不进损失 ✓）")
        if (float(args.eq_loss_node) > 0 and args.eq_node is None):
            print("[WARN] λ_eq_node>0 但没有 consistency 对 ✗（SAT 对不足 ⚠️）→ 该项自动跳过")
        if (float(args.pair_loss_node) > 0 and args.pair_node is None):
            print("[WARN] λ_pair_node>0 但没有 pair_trojan 对 ✗（a4 跨实例对不足 ⚠️）→ 该项自动跳过")
    cfg["model"]["in_channels"] = int(orig.x.size(1))     # 以数据实际维度为准（contract 模式为 39）
    if args.abl_no_edges:                                 # 消融：只留自环 → 逐节点 MLP
        for d in (orig, trans):
            sl = torch.arange(d.x.size(0), device=device)
            d.edge_index = torch.stack([sl, sl])
        print("[ABL] edge_index → 只有自环（GNN 退化为逐节点 MLP）")
    if not args.no_norm_x:                                # **默认**：按列 z-score ✓
        # 实证（2026-10-18，mini fold：rs232 训练 → s15850 测试）：
        #   不标准化            ROC-AUC 0.52 ✗ / AP 0.0012 ✗  （≈随机 ✗）
        #   全图统计标准化       ROC-AUC **0.858** ✓ / AP **0.0241** ✓
        #   仅 train 节点统计    ROC-AUC 0.678 / AP 0.0016 ✗（跨 host 时训练统计不代表测试分布 ✗）
        # → 默认用**全图**统计 ✓（transductive ✓，与节点分类常规一致 ✓）；`--norm-fit train` 可切回严格版 ✓。
        # ⚠️ P2-C 节点级：额外列**稀疏**（覆盖 ~0.1%）✗ → 全图 std 会把 0/1 放大成 ±10 ✗；
        #   `--norm-extra covered`（默认 ✓）用**被覆盖节点**的统计量 ✓，未覆盖行**原地置 0** ✓。
        #   实现要点 ✓：先算**整宽** mu/sd 再一次性 (x-mu)/sd ✓（不切列 ✓ 不二次 cat ✓ 省显存 ✓）。
        _es = getattr(args, "extra_slice", None)
        for nm_, d in (("orig", orig), ("trans", trans)):
            es = _es if (nm_ == "trans" and _es is not None) else None
            n_base = es[0] if es else d.x.size(1)
            base = d.x[:, :n_base]
            if args.norm_fit == "train":
                m_ = getattr(d, "train_mask", None)
                if m_ is not None and bool(m_.any()):
                    base = d.x[m_, :n_base]
            mu = base.mean(0, keepdim=True)
            sd = base.std(0, keepdim=True).clamp_min(1e-6)
            if es:
                n_all = d.x.size(1)
                n_extra = n_all - es[0]
                mu_f = torch.zeros(1, n_all, dtype=d.x.dtype, device=d.x.device)
                sd_f = torch.ones(1, n_all, dtype=d.x.dtype, device=d.x.device)
                mu_f[:, :n_base] = mu
                sd_f[:, :n_base] = sd
                sel = getattr(args, "extra_mask_any", None)
                n_norm = int(getattr(args, "extra_norm_n", n_extra))
                dense = min(int(getattr(args, "extra_dense_prefix", 0)), n_norm)
                if args.norm_extra == "bounded":
                    # All extra inputs were checked on CPU to be in [0,1].
                    # Natural units preserve zeros, ratios and binary flags;
                    # no rare-column standard deviation or clipping collapse.
                    print(f"[NORM] extra bounded: {n_extra} columns retained in [0,1]; no z-score")
                elif args.norm_extra == "covered" and sel is not None and bool(sel.any()):
                    if dense > 0:
                        # 稠密结构前缀（如 cone5）：用全图统计 ✓；不能只用 covered 子集 ✗
                        sub_a = d.x[:, es[0]:es[0] + dense]
                        mu_a = sub_a.mean(0, keepdim=True)
                        sd_a = sub_a.std(0, keepdim=True).clamp_min(1e-6)
                        mu_f[:, es[0]:es[0] + dense] = mu_a
                        sd_f[:, es[0]:es[0] + dense] = sd_a
                    lo = es[0] + dense
                    hi = es[0] + n_norm
                    if hi > lo:
                        sub = d.x[sel, lo:hi]
                        mu2 = sub.mean(0, keepdim=True)
                        sd2 = sub.std(0, keepdim=True).clamp_min(1e-6)
                        mu_f[:, lo:hi] = mu2
                        sd_f[:, lo:hi] = sd2
                    print(f"[NORM] extra：前 {dense} 维（dense/cone5）用**全图**；"
                          f"其余 {n_norm - dense} 维用 **covered**（{int(sel.sum())} 个 ✓）；"
                          f"covered 列原样 ✓")
                else:
                    # 视图级（无 covered 掩码 ✓）→ 回退到**全图**统计 ✓（保持旧口径 ✓）
                    sub = d.x[:, es[0]:es[0] + n_norm]
                    mu2 = sub.mean(0, keepdim=True)
                    sd2 = sub.std(0, keepdim=True).clamp_min(1e-6)
                    mu_f[:, es[0]:es[0] + n_norm] = mu2
                    sd_f[:, es[0]:es[0] + n_norm] = sd2
                    print(f"[NORM] extra 前 {n_norm} 维用**全图**统计量 ✓（无 covered 掩码 ✓）")
                mu, sd = mu_f, sd_f
            # 防御 ✓：裁到 ±10 ✓（bf16 下极端 z-score 可能把后续 BN/softmax 推到非有限值 ✗）
            d.x = torch.nan_to_num((d.x - mu) / sd, nan=0.0, posinf=0.0, neginf=0.0).clamp_(-10.0, 10.0)
            if es:
                sel = getattr(args, "extra_mask_any", None)
                n_norm = int(getattr(args, "extra_norm_n", d.x.size(1) - es[0]))
                if args.norm_extra in ("covered", "bounded") and sel is not None:
                    dense = min(int(getattr(args, "extra_dense_prefix", 0)), n_norm)
                    # 只把 SAT 段未覆盖行置 0 ✓；cone5 段保留 ✓（否则 67% 节点结构特征被抹掉 ✗）
                    d.x[~sel, es[0] + dense:es[0] + n_norm] = 0.0
        print(f"[NORM] 节点特征按列 z-score（fit={args.norm_fit} ✓）")
    vidx_t = {v: idx.to(device) for v, idx in view_index(trans).items()}
    trust_t = trust_o = None
    if args.label_mask == "trust":
        tp = pt_dir / "trust_trans.npy"
        if not tp.exists():
            raise SystemExit(f"[ERROR] 缺 {tp}（先跑 phase2/ys/make_trust_mask.py ✓）")
        trust_t = torch.from_numpy(np.load(tp)).to(device)
        op = pt_dir / "trust_orig.npy"
        if op.exists():
            trust_o = torch.from_numpy(np.load(op)).to(device)
        print(f"[MASK] trust：trans {float(trust_t.float().mean()):.4f} ✓（unknown 不进 loss ✓）")
    args.trust_t, args.trust_o = trust_t, trust_o

    kept = tuple(c.strip() for c in args.circuits.split(",") if c.strip())
    test_views_all = [v for v in views_of_role(trans, "test")
                      if (not kept or v.startswith(kept))]
    if not test_views_all:
        raise SystemExit("[ERROR] 没有测试视图（检查 --circuits 与 fold spec）")
    test_circuits = sorted({v.split("__")[0] for v in test_views_all})

    tag = (f"{meta['fold']}_seed{int(cfg['train']['seed_id'])}mode{int(cfg['train']['train_mode'])}"
           f"_{args.view_policy}b{args.view_budget}_{args.fold_mode}")
    if args.tag:
        tag += f"_{args.tag}"
    out_dir = Path(args.out_root) / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== train_test2.3 ===\n  数据: {pt_dir}")
    print(f"  fold={meta['fold']}｜标签来源: {meta['trans_label_source']}"
          f"｜CEC all PASS: {meta['cec_all_pass']}")
    print(f"  设备={device}｜in_channels={cfg['model']['in_channels']}｜epochs={cfg['train']['epochs']}"
          f"｜train_mode={cfg['train']['train_mode']}｜view_policy={args.view_policy}"
          f"(budget={args.view_budget})｜fold_mode={args.fold_mode}｜amp={amp}")
    print(f"  测试视图 {len(test_views_all)} 个，来自电路 {test_circuits}")
    print(f"  输出: {out_dir}")

    rng = random.Random(int(cfg["train"]["seed_id"]) if args.smoke_fixed_rng
                        else int(cfg["train"]["seed_id"]) + len(tag))
    all_rows, all_logs = [], []
    done_splits = set()
    if args.resume:
        all_rows, all_logs, done_splits = load_partial(out_dir)
        if done_splits:
            print(f"[RESUME] 已跳过 {len(done_splits)} 个已完成 split：{sorted(done_splits)} ✓"
                  f"（已有 {len(all_rows)} 行 ✓）")

    def _inst_of(v: str) -> str:
        """视图名 → 实例名（injalpha / ctlmatcha …）。"""
        p = str(v).split("__")
        return p[1].split("_d1")[0] if len(p) > 1 else ""

    _MATCH_CTL = {"injalpha": "ctlmatcha", "injbeta": "ctlmatchb", "injgamma": "ctlmatchc",
                  "injdelta": "ctlmatchd", "injepsilon": "ctlmatche", "injzeta": "ctlmatchf",
                  "injeta": "ctlmatchg", "injtheta": "ctlmatchh"}
    if args.fold_mode == "fold":
        splits = [("ALL", (), test_views_all)]
    elif args.fold_mode == "loco":            # 未见 host：每个目标电路留一
        splits = [(c, (c,), [v for v in test_views_all if v.startswith(c + "__")])
                  for c in test_circuits]
    elif args.fold_mode == "lro":             # 未见**配方**（综合流程 ✓）：每个 op 留一 ✓
        recs = sorted({str(v).split("__")[-1] for v in test_views_all})
        splits = [(r_, (r_,), [v for v in test_views_all if str(v).endswith("__" + r_)])
                  for r_ in recs]
        _keep = {s.strip() for s in str(getattr(args, "lro_splits", "")).split(",") if s.strip()}
        if _keep:
            splits = [sp for sp in splits if sp[0] in _keep]
            print(f"[LRO] 只跑 {sorted(_keep)}（{len(splits)} splits）")
    else:                                     # lio：**未见 Trojan 实例**（连同它的匹配对照）
        insts = sorted({_inst_of(v) for v in test_views_all if "__inj" in str(v)})
        splits = []
        for it in insts:
            held = (it,) + ((_MATCH_CTL[it],) if it in _MATCH_CTL else ())
            splits.append((it, tuple(sorted(held)),
                           [v for v in test_views_all if _inst_of(v) == it]))

    for name, circs, tviews in splits:
        if str(name) in done_splits:            # 断点续跑 ✓：该 split 已完成 ✓
            print(f"\n--- 外层划分 {name}: 断点命中，跳过 ✓ ---")
            continue
        if args.fold_mode == "fold":          # 变换泛化：所有电路的 train 视图都可用
            tr_v = views_of_role(trans, "train")
            va_v = views_of_role(trans, "val")
        else:
            if args.fold_mode == "loco":
                keyf = lambda v: str(v).split("__")[0]        # 未见 host ✓
            elif args.fold_mode == "lro":
                keyf = lambda v: str(v).split("__")[-1]       # 未见配方 ✓
            else:
                keyf = _inst_of                               # 未见实例 ✓
            bad = set(circs)
            tr_v = [v for v in views_of_role(trans, "train") if keyf(v) not in bad]
            va_v = [v for v in views_of_role(trans, "val") if keyf(v) not in bad]
        if not tr_v:
            print(f"[WARN] 外层划分 {name} 没有训练视图，跳过")
            continue
        print(f"\n--- 外层划分 {name}: train_views={len(tr_v)} val_views={len(va_v)} "
              f"test_views={len(tviews)} ---")
        model, thr, logs = run_split(cfg, args, orig, trans, vidx_t, tr_v, va_v, tviews,
                                     rng, name, amp=amp)
        if args.save_ckpt:
            safe = str(name).replace("/", "_").replace("\\", "_")
            ck = out_dir / f"best_model_{safe}.pt"
            torch.save({"state_dict": model.state_dict(), "threshold": float(thr),
                        "split": str(name), "fold": meta["fold"],
                        "train_mode": int(cfg["train"]["train_mode"]),
                        "view_policy": args.view_policy, "view_budget": int(args.view_budget),
                        "seed": int(cfg["train"]["seed_id"]),
                        "in_channels": int(cfg["model"]["in_channels"]),
                        "best_val_AP": float(max([l["best_val_AP"] for l in logs],
                                                 default=float("nan"))),
                        "n_train_views": len(tr_v), "n_test_views": len(tviews)}, ck)
            print(f"    [ckpt] {ck.name}")
        print(f"    阈值={thr:.4f}｜最优 val AP={max([l['best_val_AP'] for l in logs], default=float('nan')):.4f}")
        all_logs += logs
        if args.smoke_val_only:
            # Explicit val-only exit: no test forward/evaluation, no test predictions.
            pd.DataFrame(logs).to_csv(out_dir / "train_log.csv", index=False,
                                      encoding="utf-8-sig")
            base_dim = 39
            extra = trans.x[:, base_dim:]
            summary = dict(
                tag=tag, split=str(name), mode="val_only_smoke",
                test_evaluated=False, test_predictions_written=False,
                seed=int(cfg["train"]["seed_id"]),
                train_mode=int(cfg["train"]["train_mode"]),
                config=cfg,
                args={k: (v if isinstance(v, (str, int, float, bool, type(None)))
                          else str(v)) for k, v in vars(args).items()},
                device=str(device), cuda_available=bool(torch.cuda.is_available()),
                device_name=(torch.cuda.get_device_name(device)
                             if torch.device(device).type == "cuda" else "cpu"),
                amp=bool(amp),
                updates=int(logs[-1]["updates"]) if logs else 0,
                init_sha=(logs[0].get("init_sha") if logs else None),
                best_val_AP=float(max((l["best_val_AP"] for l in logs), default=float("nan"))),
                final_val_AP_t=logs[-1].get("final_val_AP_t") if logs else None,
                final_val_AP_o=logs[-1].get("final_val_AP_o") if logs else None,
                final_threshold=logs[-1].get("final_threshold") if logs else None,
                n_train_nodes=int(trans.train_mask.sum()),
                n_val_nodes=int(trans.val_mask.sum()),
                extra_dim=int(extra.size(1)),
                extra_mask_any=int((extra[:, -1] > 0).sum()) if extra.size(1) else 0,
                extra_train_support=int(((extra[:, -1] > 0) & trans.train_mask).sum())
                if extra.size(1) else 0,
                extra_val_support=int(((extra[:, -1] > 0) & trans.val_mask).sum())
                if extra.size(1) else 0,
                extra_norm_n=int(getattr(args, "extra_norm_n", 0)),
                base_x_sha=tensor_sha(trans.x[:, :base_dim]),
                extra_sha=tensor_sha(extra),
                train_mask_sha=tensor_sha(trans.train_mask.float()),
                val_mask_sha=tensor_sha(trans.val_mask.float()),
                extra_mask_sha=tensor_sha((extra[:, -1] > 0).float()) if extra.size(1) else "",
                best_checkpoint=(str(out_dir / f"best_model_{name}.pt")
                                 if args.save_ckpt else None),
                final_checkpoint=(str(args.smoke_final_ckpt)
                                  if args.smoke_final_ckpt else None),
                wall_s=float(sum(l.get("epoch_sec", 0.0) for l in logs)),
                peak_vram_mb=(round(torch.cuda.max_memory_allocated(device) / 2 ** 20, 1)
                              if torch.device(device).type == "cuda" else None))
            (out_dir / "smoke_val_summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            (out_dir / "run_config.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({k: summary[k] for k in
                              ("tag", "updates", "best_val_AP", "final_val_AP_t",
                               "final_threshold", "peak_vram_mb")},
                             ensure_ascii=False), flush=True)
            return 0
        all_rows += evaluate_split(model, orig, trans, vidx_t, tviews, thr, meta, name, amp=amp)
        done_splits.add(str(name))              # 逐 split 落盘 ✓（断电只丢当前 split ✓）
        save_partial(out_dir, all_rows, all_logs, done_splits)

    df, circuit_df = summarize(all_rows, out_dir, all_logs, cfg, args, tag, device, amp)

    n_cec = int((df["CEC_Status"] == "PASS").sum()) if not df.empty else 0
    print(f"\n[完成] 评测视图 {len(df)} 个｜CEC PASS {n_cec}/{len(df)}"
          f"｜结果目录 {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
