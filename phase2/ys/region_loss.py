"""region_loss.py —— C6/P1：锥级区域监督（DFF 锥 / PO 锥 ✓）的最小实现。

三件事：
  `build_regions`  区域 id（按视图隔离 ✓），两种定义：
                     dff = DFF 边界锥（种子 = DFF ∪ 无输入门，正向遇 DFF 停 ✓）—— v3.1 覆盖最好 ✓
                     po  = PO 反向锥（种子 = touches_PO ✓，反向遇 DFF 停 ✓）
  `region_bce`     区域 BCE：区域 logit = **区域内节点正类 logit 的 max** ✓，标签 = 是否含正 ✓
  `region_stats`   区域规模统计（防"全是单点"✗：v3.1 上 PO 锥 93.9% 是单点 ✗）

设计约束 ✓：只在 `--region-loss > 0` 时被调用 ✓ → 现有实验完全不受影响 ✓。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F


def _gate_info(x: np.ndarray, gatelookup: Path):
    """返回（门 id 数组 ✓，DFF 布尔掩码 ✓）。ng 从 gatelookup 长度推出 ✓（不受追加特征干扰 ✓）。"""
    raw = json.loads(Path(gatelookup).read_text(encoding="utf-8"))
    raw = raw.get("gatelookup", raw)
    names = [k for k, _ in sorted(raw.items(), key=lambda kv: int(kv[1]))]
    ng = len(names)
    if ng > x.shape[1]:
        raise SystemExit(f"[ERROR] gatelookup {ng} 列 > 特征 {x.shape[1]} 列 ✗")
    gid = np.where(x[:, :ng].sum(1) > 0, x[:, :ng].argmax(1), -1)
    is_dff = np.zeros(len(x), bool)
    for i, nm in enumerate(names):
        if "DFF" in nm.upper():
            is_dff |= (gid == i)
    return gid, is_dff, ng


def build_regions(x: np.ndarray, edge_index: np.ndarray, view_ids: np.ndarray,
                  gatelookup: Path, mode: str = "dff") -> np.ndarray:
    """区域 id（含视图偏移 ✓，避免跨视图合并 ✗）。"""
    _, is_dff, ng = _gate_info(x, gatelookup)
    src, dst = edge_index[0], edge_index[1]
    lab = np.full(len(x), -1, np.int64)
    if mode == "po":
        seeds = np.where(x[:, min(28, x.shape[1] - 1)] > 0.5)[0]   # f28 = touches_PO ✓
        keep = ~is_dff[src]
        s, t = src[keep], dst[keep]
    else:
        has_in = np.zeros(len(x), bool)
        has_in[dst] = True
        seeds = np.where(is_dff | (~has_in))[0]
        keep = ~is_dff[dst]
        s, t = src[keep], dst[keep]
    lab[seeds] = seeds
    for _ in range(256):
        if mode == "po":
            m = (lab[s] < 0) & (lab[t] >= 0)
            pair = (s[m], lab[t][m])
        else:
            m = (lab[t] < 0) & (lab[s] >= 0)
            pair = (t[m], lab[s][m])
        if not m.any():
            break
        ss, tt = pair
        _, first = np.unique(ss, return_index=True)
        lab[ss[first]] = tt[first]
    left = np.where(lab < 0)[0]
    if left.size:
        lab[left] = left
    return lab + view_ids.astype(np.int64) * (len(x) + 1)


def region_stats(region: np.ndarray) -> dict:
    uq, cnt = np.unique(region, return_counts=True)
    return dict(regions=int(len(uq)), mean_size=float(cnt.mean()),
                median_size=float(np.median(cnt)),
                frac_singleton=float((cnt <= 2).mean()))


def region_bce(logit_pos: torch.Tensor, region: torch.Tensor, y: torch.Tensor,
               mask: torch.Tensor, pos_weight: float = 30.0) -> torch.Tensor:
    """区域 BCE（区域分数 = 区内节点 logit 的 max ✓）。

    ⚠️ 这个版本**每步**都做 `torch.unique` ✗ → v3.1（34 万区域 / 1.5M 训练节点）实测
       **step 从 7–13 s 涨到 28 s** ✗。正式训练请用 `region_bce_indexed` ✓（索引只算一次 ✓）。
    """
    if not bool(mask.any()):
        return torch.zeros((), device=logit_pos.device)
    logit_pos = logit_pos.float()          # autocast 下可能是 bf16 ✗ → 统一 float32 ✓
    r = region[mask]
    uq, inv = torch.unique(r, return_inverse=True)
    rmax = torch.full((len(uq),), -30.0, device=logit_pos.device)
    rmax.scatter_reduce_(0, inv, logit_pos[mask], reduce="amax", include_self=True)
    rpos = torch.zeros(len(uq), device=logit_pos.device)
    rpos.scatter_add_(0, inv, y[mask].float())
    pw = torch.tensor(float(pos_weight), device=logit_pos.device)
    return F.binary_cross_entropy_with_logits(rmax, (rpos > 0).float(), pos_weight=pw)


def regions_to_index(region: np.ndarray) -> tuple[np.ndarray, int]:
    """把区域 id 压成稠密下标 ✓（只做一次 ✓，然后缓存到磁盘 ✓）。"""
    uq, inv = np.unique(region, return_inverse=True)
    return inv.astype(np.int32), int(len(uq))


def region_bce_indexed(logit_pos: torch.Tensor, inv: torch.Tensor, n_reg: int,
                       y: torch.Tensor, mask: torch.Tensor,
                       pos_weight: float = 30.0) -> torch.Tensor:
    """索引版区域 BCE ✓（无 `unique` ✗ → v3.1 上 step 回到 ~8–12 s ✓）。"""
    if not bool(mask.any()):
        return torch.zeros((), device=logit_pos.device)
    logit_pos = logit_pos.float()
    inv_m = inv[mask]
    rmax = torch.full((n_reg,), -30.0, device=logit_pos.device)
    rmax.scatter_reduce_(0, inv_m, logit_pos[mask], reduce="amax", include_self=True)
    rpos = torch.zeros(n_reg, device=logit_pos.device)
    rpos.scatter_add_(0, inv_m, y[mask].float())
    pw = torch.tensor(float(pos_weight), device=logit_pos.device)
    return F.binary_cross_entropy_with_logits(rmax, (rpos > 0).float(), pos_weight=pw)
