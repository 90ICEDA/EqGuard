# -*- coding: utf-8 -*-
"""
methods.py —— 方法三版本 M1/M2 的模型与损失（M0 = 现有 G4，不在此处）

设计：
  * **encoder** 与 M0 完全相同（4 层 GINConv、hidden=64、no dropout 差异），
    保证「M0 vs M1 vs M2」的比较只差在新增的 head / 损失上；
  * `classifier` 与 M0 **同名同形状**（hidden→2），因此
    `phase2.p2common.Embedder`（hook 在 classifier 上）与所有探针脚本可原样复用；
  * `sec`：security representation（hidden→sec_dim）；
  * `adv_op` / `adv_dep`：从 sec 预测 operator / depth，前面接 **gradient reversal**，
    使 encoder 被推着让 sec **尽量不能**预测 operator/depth（M1 的核心）。
  * **不**对 circuit ID 做对抗（按任务要求：先只压 synthesis 信息）。

M2 在 M1 之上加两项双干预约束（见 train_security.py 的 losses）：
  * 同 Trojan、不同 synthesis → sec 表示拉近（invariance）；
  * matched benign/Trojan（同实现、安全语义翻转）→ sec 表示拉开（margin/contrastive）。
"""
from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F


class _GradReverse(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x, lambd):
        ctx.lambd = lambd
        return x.view_as(x)

    @staticmethod
    def backward(ctx, grad):
        return -ctx.lambd * grad, None


def grad_reverse(x, lambd: float = 1.0):
    return _GradReverse.apply(x, lambd)


def _gin_conv(in_ch, hid):
    from torch_geometric.nn import GINConv
    from torch.nn import Sequential, Linear, BatchNorm1d, ReLU
    return GINConv(Sequential(Linear(in_ch, hid), BatchNorm1d(hid), ReLU(),
                              Linear(hid, hid)))


class SecGIN(nn.Module):
    """M1/M2：共享 encoder + 任务头 + security 表示 + 对抗头。"""

    def __init__(self, in_channels: int, hidden: int = 64, layers: int = 4,
                 sec: int = 32, n_op: int = 4, n_depth: int = 3, out: int = 2,
                 dropout: float = 0.2):
        super().__init__()
        self.hidden = hidden
        self.dropout = dropout
        self.convs = nn.ModuleList([_gin_conv(in_channels, hidden)])
        for _ in range(layers - 1):
            self.convs.append(_gin_conv(hidden, hidden))
        self.classifier = nn.Linear(hidden, out)          # 与 M0 同名（供 Embedder hook）
        self.sec = nn.Linear(hidden, sec)
        self.adv_op = nn.Linear(sec, n_op)
        self.adv_dep = nn.Linear(sec, n_depth)

    def encode(self, x, edge_index):
        for conv in self.convs:
            x = conv(x, edge_index)
            x = F.relu(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
        return x

    def forward(self, x, edge_index):
        """返回 logits，接口与 M0 完全一致（保证下游指标/Embedder 复用）。"""
        return self.classifier(self.encode(x, edge_index))

    def sec_repr(self, x, edge_index):
        return self.sec(self.encode(x, edge_index))

    def adv_logits(self, sec_h, lambd: float):
        z = grad_reverse(sec_h, lambd)
        return self.adv_op(z), self.adv_dep(z)


def adversarial_loss(model, sec_pooled, op_labels, dep_labels, lambd: float):
    """sec（视图级 mean-pool）→ 预测 operator / depth，经 GRL 反向优化 encoder。"""
    lo, ld = model.adv_logits(sec_pooled, lambd)
    return F.cross_entropy(lo, op_labels), F.cross_entropy(ld, dep_labels)


def invariance_loss(sec_pooled_a, sec_pooled_b):
    """同 Trojan、不同 synthesis：把 sec 表示拉近（均方距离）。"""
    return F.mse_loss(sec_pooled_a, sec_pooled_b)


def security_margin_loss(sec_a, sec_b, margin: float = 1.0):
    """matched benign/Trojan：把 sec 表示拉开到至少 margin（hinge on 距离）。"""
    d = (sec_a - sec_b).pow(2).sum(dim=1).clamp_min(1e-9).sqrt()
    return F.relu(margin - d).mean()


# --------------------------------------------------------------------------
# M3：object-aware consistency（verified object only + region pooling）
# --------------------------------------------------------------------------
def make_object_tensors(work_dir, device, include_identity: bool = False):
    """预计算每个视图的 (orig_idx, group_id, target_idx, n_groups)。

    `1→N`（split）的多个目标节点共享同一个 group_id → 用 index_add_ 做 **mean region pooling**，
    不再要求逐门 1:1。只含 **verified object**（mapping 里显式出现的对象）。
    """
    import torch
    from phase2.objects import build_object_groups
    groups = build_object_groups(Path(work_dir), include_identity=include_identity)
    per_view = {}
    for v, items in groups.items():
        o = torch.tensor([it[0] for it in items], dtype=torch.long, device=device)
        gid, tt = [], []
        for i, (_oi, ts) in enumerate(items):
            gid += [i] * len(ts)
            tt += [int(x) for x in ts]
        per_view[v] = (o, torch.tensor(gid, dtype=torch.long, device=device),
                       torch.tensor(tt, dtype=torch.long, device=device), len(items))
    return per_view


def object_consistency_loss(logits_o, logits_t, per_view, views, mask_o, mask_t,
                            mode: str = "mse_logit", T: float = 0.5):
    """对每个 verified object：把它的目标节点集合 mean-pool 成一个向量，再与 orig 侧比较。

    group_by_orig 的语义在这里被「对象」显式取代：每个对象对 loss 贡献相同权重，
    且 split/merge 由 pooling 处理，因此不存在"逐 gate 必须一一对应"的错误假设。
    """
    import torch
    dev = logits_o.device
    # 统一到 float32，避免被 bf16 autocast 影响（一致性损失对精度敏感）
    logits_o = logits_o.float()
    logits_t = logits_t.float()
    tot, n = logits_o.new_zeros(()), 0
    for v in views:
        if v not in per_view:
            continue
        o, gid, tt, ng = per_view[v]
        keep_t = mask_t[tt]
        if not bool(keep_t.any()):
            continue
        num = logits_o.new_zeros((ng, logits_t.size(1)))
        cnt = logits_o.new_zeros((ng,))
        num.index_add_(0, gid[keep_t], logits_t[tt[keep_t]])
        cnt.index_add_(0, gid[keep_t], torch.ones(int(keep_t.sum()), device=dev,
                                                  dtype=cnt.dtype))
        keep_g = (cnt > 0) & mask_o[o]
        if not bool(keep_g.any()):
            continue
        pooled_t = num[keep_g] / cnt[keep_g].unsqueeze(1)
        pooled_o = logits_o[o[keep_g]]
        if mode == "mae_prob":
            tot = tot + F.l1_loss(F.softmax(pooled_o / T, dim=1), F.softmax(pooled_t / T, dim=1))
        else:
            tot = tot + F.mse_loss(pooled_o, pooled_t)
        n += 1
    return tot / max(n, 1)

