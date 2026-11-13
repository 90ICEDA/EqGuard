"""train_region_mini.py —— C6 试点：**PO 锥级监督**（小 fold `_mini31` ✓，完全独立 ✓）。

目的（回答"如何压住头部假阳性"✓）：
  节点级损失只看单门 → 良性"孤立高分门"照样得分 ✓；
  这里给**锥级标签**（锥内有正样本=1 ✓）加一项 BCE，锥分数 = **锥内节点 logit 的 max** ✓
  → 直接优化"证据要成团" ✓，预期降低 head_fp ✓。

约束（用户要求 ✓）：
  · **不改** `train_test2.3.py` ✗、**不改**任何已有 fold 数据 ✗（只读 `_mini31` ✓）；
  · 输出全部写到 `_devcfg/region_mini/` ✓（新目录 ✓）。

用法：
  py -X utf8 phase2/ys/train_region_mini.py --lambda-region 0.5 --seed 42 --epochs 60
  py -X utf8 phase2/ys/train_region_mini.py --lambda-region 0.0   # 基线 ✓
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from models.gin_net import GINDual  # noqa: E402

FOLD = ROOT / "generate_trans" / "folds" / "_mini31"
OUT = ROOT / "_devcfg" / "region_mini"


def load_fold(fold: Path):
    pt = fold / "data" / "processed" / "trans_graph.pt"
    d = torch.load(pt, map_location="cpu", weights_only=False, mmap=True)
    fids = json.loads((fold / "data/for_train/metadata_trans.json")
                      .read_text(encoding="utf-8"))["file_ids"]
    meta = json.loads((fold / "views.json").read_text(encoding="utf-8"))
    return d, np.asarray(fids), meta


def dff_mask_of(x: np.ndarray, fold: Path) -> np.ndarray:
    """DFF 节点（门 one-hot 的第一段 ✓，同 region_eval.dff_mask ✓）。"""
    ng = x.shape[1] - 14
    gl = json.loads((fold / "gatelookup_recommended.json").read_text(encoding="utf-8"))
    raw = gl.get("gatelookup", gl)
    names = [k for k, _ in sorted(raw.items(), key=lambda kv: int(kv[1]))][:ng]
    gid = np.where(x[:, :ng].sum(1) > 0, x[:, :ng].argmax(1), -1)
    is_dff = np.zeros(len(x), bool)
    for i, nm in enumerate(names):
        if "DFF" in nm.upper():
            is_dff |= (gid == i)
    return is_dff


def build_po_regions(x: np.ndarray, edge_index: np.ndarray, view_id: np.ndarray,
                     fold: Path) -> np.ndarray:
    """PO 反向锥（遇 DFF 停 ✓），区域 id 按视图隔离 ✓（= region_methods 的 M4 ✓）。"""
    is_dff = dff_mask_of(x, fold)
    src, dst = edge_index[0], edge_index[1]
    lab = np.full(len(x), -1, np.int64)
    po = np.where(x[:, 28] > 0.5)[0]          # f28 = touches_PO ✓
    lab[po] = po
    keep = ~is_dff[src]                        # 反向走：不穿过 DFF ✓
    s, t = src[keep], dst[keep]
    for _ in range(256):
        m = (lab[s] < 0) & (lab[t] >= 0)
        if not m.any():
            break
        ss, tt = s[m], lab[t][m]
        _, first = np.unique(ss, return_index=True)
        lab[ss[first]] = tt[first]
    left = np.where(lab < 0)[0]
    if left.size:
        lab[left] = left
    return lab + view_id.astype(np.int64) * (len(x) + 1)


def asl_loss(logit, y, mask, w_pos=6.0, g_neg=4.0, clip=0.05):
    """不对称焦点损失（与项目 `loss_type=asl` 同形 ✓）。"""
    p = torch.sigmoid(logit[mask])
    yt = y[mask].float()
    loss = (yt * w_pos * torch.log(torch.clamp(p, min=1e-6))
            + (1 - yt) * torch.pow(torch.clamp(1 - p + clip, min=0), g_neg)
            * torch.log(torch.clamp(1 - p, min=1e-6)))
    return -loss.mean()


def region_bce(logit, region, y, mask, pos_weight=30.0):
    """锥级 BCE：区域 logit = 锥内**正类 logit 的 max** ✓；标签 = 锥内是否含正 ✓。"""
    if not bool(mask.any()):
        return torch.zeros((), device=logit.device)
    r = region[mask]
    uq, inv = torch.unique(r, return_inverse=True)
    rmax = torch.full((len(uq),), -30.0, device=logit.device)
    rmax.scatter_reduce_(0, inv, logit[mask], reduce="amax", include_self=True)
    rpos = torch.zeros(len(uq), device=logit.device)
    rpos.scatter_add_(0, inv, y[mask].float())
    return F.binary_cross_entropy_with_logits(
        rmax, (rpos > 0).float(), pos_weight=torch.tensor(pos_weight, device=logit.device))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=Path, default=FOLD)
    ap.add_argument("--lambda-region", type=float, default=0.5)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--split", type=int, default=29)
    ap.add_argument("--tag", default="")
    ap.add_argument("--out-dir", type=Path, default=OUT)
    a = ap.parse_args()
    torch.manual_seed(a.seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"

    d, fids, meta = load_fold(a.fold)
    X = np.asarray(d.x, np.float32)
    X = np.nan_to_num((X - X.mean(0, keepdims=True)) / np.clip(X.std(0, keepdims=True), 1e-6, None),
                      nan=0.0, posinf=0.0, neginf=0.0).clip(-10, 10)
    y = np.asarray(d.y, np.int8).astype(np.int64)
    edge_index = d.edge_index
    fids = fids.astype(str)
    vm = {}
    for i, v in enumerate(fids):
        vm.setdefault(v, []).append(i)
    vnames = sorted(vm)
    view_id = np.zeros(len(y), np.int64)
    for k, v in enumerate(vnames):
        view_id[np.array(vm[v])] = k

    tr_views, va_views, te_views = set(meta["train_views"]), set(meta.get("val_views", [])), set(meta["test_views"])
    m_tr = np.isin(fids, list(tr_views))
    m_va = np.isin(fids, list(va_views))
    m_te = np.isin(fids, list(te_views))
    region = build_po_regions(X, edge_index.numpy(), view_id, a.fold)
    print(f"[data] nodes={len(y)} views={len(vnames)} train/val/test={len(tr_views)}/{len(va_views)}/"
          f"{len(te_views)} regions={len(np.unique(region))} pos={int(y.sum())}")

    x_t, y_t, ei = torch.from_numpy(X).to(dev), torch.from_numpy(y).to(dev), edge_index.to(dev)
    rg, tr_m, va_m = torch.from_numpy(region).to(dev), torch.from_numpy(m_tr).to(dev), torch.from_numpy(m_va).to(dev)

    model = GINDual(in_channels=X.shape[1], hidden_channels=a.hidden, out_channels=2,
                    num_layers=4, split=a.split, fusion="concat").to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=a.lr, weight_decay=1e-3)
    print(f"[cfg] lam_region={a.lambda_region:g} epochs={a.epochs} seed={a.seed} dev={dev}")

    def val_region_ap() -> float:
        model.eval()
        with torch.no_grad():
            p = torch.sigmoid(model(x_t, ei)[:, 1])[va_m].cpu().numpy()
        yv, rv = y[m_va], region[m_va]
        uq, inv = np.unique(rv, return_inverse=True)
        rmax = np.zeros(len(uq), np.float32)
        np.maximum.at(rmax, inv, p)
        rpos = np.zeros(len(uq), np.int32)
        np.add.at(rpos, inv, yv)
        if 0 < (rpos > 0).sum() < len(uq):
            return float(average_precision_score((rpos > 0).astype(int), rmax))
        return 0.0

    t0, best = time.time(), {"ap": -1.0, "state": None}
    for ep in range(a.epochs):
        model.train()
        opt.zero_grad()
        lg = model(x_t, ei)[:, 1]
        loss = asl_loss(lg, y_t, tr_m)
        if a.lambda_region > 0:
            loss = loss + a.lambda_region * region_bce(lg, rg, y_t, tr_m)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if (ep + 1) % 10 == 0 or ep == a.epochs - 1:
            v = val_region_ap()
            print(f"  ep{ep + 1:>3d} loss={float(loss.detach()):.4f} val_region_AP={v:.4f} "
                  f"({time.time() - t0:.0f}s)", flush=True)
            if v > best["ap"]:
                best = {"ap": v, "state": {k: t.detach().clone() for k, t in model.state_dict().items()}}
    if best["state"] is not None:
        model.load_state_dict(best["state"])
    model.eval()
    with torch.no_grad():
        prob = torch.sigmoid(model(x_t, ei)[:, 1]).cpu().numpy()

    rows = []
    for v in sorted(te_views):
        m = (fids == v)
        yy, ss = y[m], prob[m]
        pos = int(yy.sum())
        if pos == 0 or pos == len(yy):
            continue
        order = np.argsort(-ss)
        ranks = np.empty(len(ss), np.int64)
        ranks[order] = np.arange(1, len(ss) + 1)
        rpos = ranks[yy == 1]
        rv = region[m]
        uq, inv = np.unique(rv, return_inverse=True)
        rmax = np.zeros(len(uq), np.float32)
        np.maximum.at(rmax, inv, ss)
        rposa = np.zeros(len(uq), np.int32)
        np.add.at(rposa, inv, yy)
        reg_ap = (average_precision_score((rposa > 0).astype(int), rmax)
                  if 0 < (rposa > 0).sum() < len(uq) else np.nan)
        rows.append(dict(view=v.split("__", 1)[1][:26], pos=pos,
                         node_ap=float(average_precision_score(yy, ss)),
                         node_auc=float(roc_auc_score(yy, ss)),
                         r5=float(yy[order[:max(1, int(len(yy) * 0.05))]].sum() / pos),
                         reg_ap=reg_ap,
                         head_fp=int((ss[yy == 0] > ss[yy == 1].max()).sum()),
                         tail_pos=int((rpos > np.median(ranks[yy == 0])).sum())))
    df = pd.DataFrame(rows)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    name = f"mini_lam{a.lambda_region:g}_s{a.seed}" + (f"_{a.tag}" if a.tag else "")
    df.to_csv(a.out_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
    print("\n" + df.mean(numeric_only=True).round(4).to_string())
    print(f"[out] {a.out_dir / (name + '.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

