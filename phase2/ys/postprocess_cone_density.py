"""postprocess_cone_density.py —— P2：**锥内高分密度**后处理重排（λ 只在 val 上选 ✓）。

机制（来自 FP 诊断 ✓）：
  头部假阳性 = **小锥里的孤立高分点** ✗（dev4：FP 锥 32.5 门 / 锥内高分门 10.4）；
  真阳性 = **大锥里成团的高分** ✓（124.5 门 / 26.9 个）；单特征 AUC 0.80/0.78 ✓。
  所以把"锥内高分门数量"当作证据加成 ✓：
      score' = score + λ · log1p(#nodes in same PO-cone with score > thr)
  λ 与 thr 只在 **val 视图**上选 ✓，test 只评一次 ✓（不偷看测试集 ✓）。

用法（v3.1 三个 seed ✓）：
  py -X utf8 phase2/ys/postprocess_cone_density.py \
     --pt generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt \
     --npz _devcfg/gnn_v31_s42.npz _devcfg/gnn_v31_s1.npz _devcfg/gnn_v31_s2.npz
输出：`10.15/03_特征与模型/C6_区域级监督/tables/p2_cone_density_v31.csv` ✓ + 同目录 md ✓
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
DST = ROOT / "10.15" / "03_特征与模型" / "C6_区域级监督"
LAMBDAS = (0.0, 0.05, 0.1, 0.2, 0.3, 0.5)
THRS = (0.5, 0.6, 0.7)


def cone_ids(x: np.ndarray, edge_index: np.ndarray, view_id: np.ndarray,
             gatelookup: Path, mode: str = "po") -> np.ndarray:
    """区域 id（按视图隔离 ✓）。
    mode="po"  ：PO 反向锥（遇 DFF 停 ✓）—— dev4 上有效，但 v3.1 只有 1.36% 节点是 PO，
                 **93.9% 的锥只有 1–2 个门** ✗ → 密度几乎恒定 ✗（P2 第一轮 val 选 λ=0 的原因 ✓）。
    mode="dff" ：DFF 边界锥（种子 = DFF ∪ 无输入门，遇 DFF 停 ✓）—— 覆盖率更高 ✓，用它再试一次 ✓。
    """
    ng = x.shape[1] - 14
    raw = json.loads(gatelookup.read_text(encoding="utf-8"))
    raw = raw.get("gatelookup", raw)
    names = [k for k, _ in sorted(raw.items(), key=lambda kv: int(kv[1]))][:ng]
    gid = np.where(x[:, :ng].sum(1) > 0, x[:, :ng].argmax(1), -1)
    is_dff = np.zeros(len(x), bool)
    for i, nm in enumerate(names):
        if "DFF" in nm.upper():
            is_dff |= (gid == i)
    src, dst = edge_index[0], edge_index[1]
    lab = np.full(len(x), -1, np.int64)
    if mode == "po":
        seeds = np.where(x[:, 28] > 0.5)[0]
        keep = ~is_dff[src]                    # 反向走：不穿过 DFF ✓
        s, t = src[keep], dst[keep]
    else:
        has_in = np.zeros(len(x), bool)
        has_in[dst] = True
        seeds = np.where(is_dff | (~has_in))[0]
        keep = ~is_dff[dst]                    # 正向走：不穿过 DFF ✓
        s, t = src[keep], dst[keep]
    lab[seeds] = seeds
    for _ in range(256):
        if mode == "po":                       # 反向：从后继把 id 传给前驱 ✓
            m = (lab[s] < 0) & (lab[t] >= 0)
            ss, tt = s[m], lab[t][m]
        else:                                  # 正向：从前驱把 id 传给后继 ✓
            m = (lab[t] < 0) & (lab[s] >= 0)
            ss, tt = t[m], lab[s][m]
        if not m.any():
            break
        _, first = np.unique(ss, return_index=True)
        lab[ss[first]] = tt[first]
    left = np.where(lab < 0)[0]
    if left.size:
        lab[left] = left
    return lab + view_id.astype(np.int64) * (len(x) + 1)


def per_view(y: np.ndarray, s: np.ndarray, fids: np.ndarray, views, region: np.ndarray,
             inv: np.ndarray, sizes: np.ndarray) -> dict:
    """逐视图指标（AP/AUC/R@5% + head_fp/tail_pos + 锥级 AP ✓）。"""
    aps, aucs, r5s, hfps, tps, raps = [], [], [], [], [], []
    for v in views:
        m = fids == v
        yy, ss = y[m], s[m]
        pos = int(yy.sum())
        if pos == 0 or pos == len(yy):
            continue
        order = np.argsort(-ss)
        ranks = np.empty(len(ss), np.int64)
        ranks[order] = np.arange(1, len(ss) + 1)
        rpos = ranks[yy == 1]
        aps.append(average_precision_score(yy, ss))
        aucs.append(roc_auc_score(yy, ss))
        r5s.append(float(yy[order[:max(1, int(len(yy) * 0.05))]].sum() / pos))
        hfps.append(int((ss[yy == 0] > ss[yy == 1].max()).sum()))
        tps.append(int((rpos > np.median(ranks[yy == 0])).sum()))
        rv = region[m]
        uq, iv = np.unique(rv, return_inverse=True)
        rmax = np.zeros(len(uq), np.float32)
        np.maximum.at(rmax, iv, ss)
        rposa = np.zeros(len(uq), np.int32)
        np.add.at(rposa, iv, yy)
        if 0 < (rposa > 0).sum() < len(uq):
            raps.append(average_precision_score((rposa > 0).astype(int), rmax))
    return dict(views=len(aps), node_ap=float(np.mean(aps)), node_auc=float(np.mean(aucs)),
                r5=float(np.mean(r5s)), head_fp=float(np.mean(hfps)),
                tail_pos=float(np.mean(tps)), reg_ap=float(np.mean(raps)) if raps else float("nan"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path,
                    default=ROOT / "generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt")
    ap.add_argument("--npz", type=Path, nargs="+", required=True)
    ap.add_argument("--out-dir", type=Path, default=DST)
    ap.add_argument("--region-mode", choices=["po", "dff"], default="po")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    work = a.pt.parents[2]

    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    y = np.asarray(d.y, np.int8).astype(np.int64)
    ei = d.edge_index.numpy()
    fids = np.asarray(json.loads((work / "data/for_train/metadata_trans.json")
                                 .read_text(encoding="utf-8"))["file_ids"])
    meta = json.loads((work / "views.json").read_text(encoding="utf-8"))
    va_views, te_views = list(meta["val_views"]), list(meta["test_views"])

    vm = {}
    for i, v in enumerate(fids):
        vm.setdefault(str(v), []).append(i)
    vnames = sorted(vm)
    view_id = np.zeros(len(y), np.int64)
    for k, v in enumerate(vnames):
        view_id[np.array(vm[v])] = k
    region = cone_ids(X, ei, view_id, work / "gatelookup_recommended.json", a.region_mode)
    uq, inv = np.unique(region, return_inverse=True)
    sizes = np.bincount(inv, minlength=len(uq))
    print(f"[cone:{a.region_mode}] regions={len(uq)}  mean_size={sizes.mean():.1f}  "
          f"median={np.median(sizes):.0f}  p90={np.percentile(sizes, 90):.0f}  "
          f"frac(size<=2)={float((sizes <= 2).mean()):.3f}  nodes={len(y)}", flush=True)

    rows = []
    for f in a.npz:
        g = np.load(f)
        idx = g["idx"].astype(np.int64)
        s0 = np.full(len(y), -1.0, np.float32)
        s0[idx] = g["score"].astype(np.float32)
        best = None
        for thr in THRS:
            hi = (s0 > thr).astype(np.float32)
            chigh = np.zeros(len(uq), np.float32)
            np.add.at(chigh, inv, hi)
            bonus = np.log1p(chigh[inv])
            for lam in LAMBDAS:
                s1 = s0 + lam * bonus
                m_va = per_view(y, s1, fids, va_views, region, inv, sizes)
                if best is None or m_va["node_ap"] > best[0]["node_ap"]:
                    best = (m_va, lam, thr, s1)
        _, lam, thr, s_sel = best
        base = per_view(y, s0, fids, te_views, region, inv, sizes)
        new = per_view(y, s_sel, fids, te_views, region, inv, sizes)
        rows.append(dict(npz=f.name, lam=lam, thr=thr,
                         **{f"base_{k}": v for k, v in base.items()},
                         **{f"new_{k}": v for k, v in new.items()}))
        print(f"[{f.name}] 选中 λ={lam:g} thr={thr:g}（val 选 ✓）｜test: AP {base['node_ap']:.4f}→"
              f"{new['node_ap']:.4f}｜AUC {base['node_auc']:.4f}→{new['node_auc']:.4f}｜"
              f"R@5% {base['r5']:.4f}→{new['r5']:.4f}｜head_fp {base['head_fp']:.0f}→{new['head_fp']:.0f}｜"
              f"region {base['reg_ap']:.4f}→{new['reg_ap']:.4f}", flush=True)

    df = pd.DataFrame(rows)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out_dir / "tables" / f"p2_cone_density_v31_{a.region_mode}{a.tag}.csv",
              index=False, encoding="utf-8-sig")
    keys = ["node_ap", "node_auc", "r5", "head_fp", "tail_pos", "reg_ap"]
    lines = ["# P2 —— 锥内高分密度后处理（v3.1，3 seed ✓，λ/thr 只在 val 上选 ✓）", "",
             "公式 ✓：`score' = score + λ·log1p(#同锥内 score>thr 的门数)`（同锥 = PO 反向锥 ✓，遇 DFF 停 ✓）。", "",
             "| seed(npz) | λ* | thr* | node AP | node AUC | R@5% | head_fp | region AP |",
             "|---|---|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        lines.append(f"| {r['npz']} | {r['lam']:g} | {r['thr']:g} | "
                     f"{r['base_node_ap']:.4f} → **{r['new_node_ap']:.4f}** | "
                     f"{r['base_node_auc']:.4f} → {r['new_node_auc']:.4f} | "
                     f"{r['base_r5']:.4f} → **{r['new_r5']:.4f}** | "
                     f"{r['base_head_fp']:.0f} → **{r['new_head_fp']:.0f}** | "
                     f"{r['base_reg_ap']:.4f} → {r['new_reg_ap']:.4f} |")
    lines += ["", "## 均值（n=3 ✓）", ""]
    summ = {}
    for k in keys:
        b, n = float(df[f"base_{k}"].mean()), float(df[f"new_{k}"].mean())
        summ[k] = (b, n)
        rel = (n / b - 1) * 100 if b else float("nan")
        lines.append(f"- **{k}**: {b:.4f} → {n:.4f}（{rel:+.1f}% ✓）")
    a.out_dir.joinpath(f"p2_cone_density_{a.region_mode}{a.tag}.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[out] {a.out_dir / 'tables' / 'p2_cone_density_v31.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
