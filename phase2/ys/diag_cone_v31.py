"""diag_cone_v31.py —— 在 v3.1 上复核"锥密度"前提（TP vs 头部 FP ✓）+ oracle 上界 ⚠️。

为什么要做：P2 在 v3.1 上 val 选中 λ=0 ✗，且 PO 锥中位数只有 1 门（dev4 是 32）✗。
本脚本回答三件事：
  1. v3.1 的 PO 锥规模分布到底多小 ✓（为何密度加成几乎恒定 ✗）；
  2. 在 v3.1 上，`cone_size / cone_high / nbr_mean` 对 TP vs 头部 FP 还有没有区分力 ✓（AUC）；
  3. **oracle 上界** ⚠️：若直接在 test 上挑 λ，最多能涨多少 ✓（仅诊断 ✗，不可作为结果 ✗）。
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
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed/trans_graph.pt"
DST = ROOT / "10.15" / "03_特征与模型" / "C6_区域级监督"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path, default=PT)
    ap.add_argument("--npz", type=Path, nargs="+", required=True)
    ap.add_argument("--out-dir", type=Path, default=DST / "tables")
    a = ap.parse_args()
    work = a.pt.parents[2]
    d = torch.load(a.pt, map_location="cpu", weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    y = np.asarray(d.y, np.int8).astype(np.int64)
    ei = d.edge_index.numpy()
    fids = np.asarray(json.loads((work / "data/for_train/metadata_trans.json")
                                 .read_text(encoding="utf-8"))["file_ids"])
    meta = json.loads((work / "views.json").read_text(encoding="utf-8"))
    te_views = list(meta["test_views"])

    ng = X.shape[1] - 14
    raw = json.loads((work / "gatelookup_recommended.json").read_text(encoding="utf-8"))
    raw = raw.get("gatelookup", raw)
    names = [k for k, _ in sorted(raw.items(), key=lambda kv: int(kv[1]))][:ng]
    gid = np.where(X[:, :ng].sum(1) > 0, X[:, :ng].argmax(1), -1)
    is_dff = np.zeros(len(X), bool)
    for i, nm in enumerate(names):
        if "DFF" in nm.upper():
            is_dff |= (gid == i)
    src, dst = ei[0], ei[1]
    lab = np.full(len(X), -1, np.int64)
    po = np.where(X[:, 28] > 0.5)[0]
    lab[po] = po
    keep = ~is_dff[src]
    s_, t_ = src[keep], dst[keep]
    for _ in range(256):
        m = (lab[s_] < 0) & (lab[t_] >= 0)
        if not m.any():
            break
        ss, tt = s_[m], lab[t_][m]
        _, first = np.unique(ss, return_index=True)
        lab[ss[first]] = tt[first]
    left = np.where(lab < 0)[0]
    lab[left] = left
    # 视图隔离 ✓
    vm = {}
    for i, v in enumerate(fids):
        vm.setdefault(str(v), []).append(i)
    view_id = np.zeros(len(y), np.int64)
    for k, v in enumerate(sorted(vm)):
        view_id[np.array(vm[str(v)])] = k
    region = lab + view_id * (len(y) + 1)
    uq, inv = np.unique(region, return_inverse=True)
    sizes = np.bincount(inv, minlength=len(uq))
    print(f"[cone] regions={len(uq)} mean={sizes.mean():.1f} median={np.median(sizes):.0f} "
          f"p90={np.percentile(sizes, 90):.0f} max={sizes.max()} "
          f"frac(size<=2)={float((sizes <= 2).mean()):.3f}")
    print(f"[po] PO nodes={len(po)} ({len(po)/len(y)*100:.2f}%)")

    rows = []
    for f in a.npz:
        g = np.load(f)
        s0 = np.full(len(y), -1.0, np.float32)
        s0[g["idx"].astype(np.int64)] = g["score"].astype(np.float32)
        chigh = np.zeros(len(uq), np.float32)
        np.add.at(chigh, inv, (s0 > 0.6).astype(np.float32))
        tp_i, fp_i = [], []
        for v in te_views:
            m = fids == v
            yy, ss = y[m], s0[m]
            if not (0 < yy.sum() < len(yy)):
                continue
            bi = np.where(m)[0]
            best = ss[yy == 1].max()
            fpm = (yy == 0) & (ss > best)
            if fpm.sum() == 0:
                continue
            tp_i += list(bi[yy == 1])
            fp_i += list(bi[fpm][:5])
        tp_i, fp_i = np.array(tp_i), np.array(fp_i)
        if len(tp_i) == 0 or len(fp_i) == 0:
            continue
        for c, arr in (("cone_size", sizes[inv]), ("cone_high", chigh[inv])):
            auc = roc_auc_score(np.r_[np.ones(len(tp_i)), np.zeros(len(fp_i))],
                                np.r_[arr[tp_i], arr[fp_i]])
            print(f"[{f.name}] {c:<10s} TP={arr[tp_i].mean():8.2f} FP={arr[fp_i].mean():8.2f} "
                  f"AUC={auc:+.3f}")
            rows.append(dict(npz=f.name, metric=c, tp=float(arr[tp_i].mean()),
                             fp=float(arr[fp_i].mean()), auc=float(auc)))
        # oracle 上界 ⚠️（直接在 test 上选 λ，仅诊断 ✗）
        best = (0.0, -1.0)
        for thr in (0.5, 0.6, 0.7):
            ch = np.zeros(len(uq), np.float32)
            np.add.at(ch, inv, (s0 > thr).astype(np.float32))
            for lam in (0.0, 0.05, 0.1, 0.2, 0.3, 0.5):
                s1 = s0 + lam * np.log1p(ch[inv])
                aps = [average_precision_score(y[fids == v], s1[fids == v])
                       for v in te_views if 0 < y[fids == v].sum() < (fids == v).sum()]
                ap_ = float(np.mean(aps))
                if ap_ > best[1]:
                    best = (lam, ap_)
        rows.append(dict(npz=f.name, metric="oracle_AP", tp=best[1], fp=float("nan"),
                         auc=float(best[0])))
        print(f"[{f.name}] oracle best λ={best[0]:g} → test AP={best[1]:.4f} ⚠️(仅诊断)")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    out = pd.DataFrame(rows)
    out.to_csv(a.out_dir / "p2_diag_v31.csv", index=False, encoding="utf-8-sig")
    print(f"\n[out] {a.out_dir / 'p2_diag_v31.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
