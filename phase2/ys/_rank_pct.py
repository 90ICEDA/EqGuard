# -*- coding: utf-8 -*-
"""_rank_pct.py —— 定案实验：木马节点的"排名分位"（与正样本数量无关）。

为什么需要它：
    按变换种类的 AP 显示 yosys 变体崩到 0.02（abc）/ 0.002（aig），但 yosys 视图的
    正样本节点数远少于 decomp3（按对齐表推算 abc 约 11 个、aig 约 1 个）。当正样本只有
    1 个时，AP 退化成"那一个节点的排名"，噪声极大 → 不能直接读成"信号被抹掉 99%"。

改用与正样本数量无关的指标：
    best_pos_pct  最好那个木马节点的排名分位（只需 1 个正样本，跨视图可比）
    mean_pos_pct  全部木马节点排名分位的均值
    pos_top1pct   木马节点落在前 1% 的比例
    neg_med_pct   干净节点排名分位的中位数（参照，正常应接近 0.5）

读法：0.01 = 木马几乎排在最前；0.5 = 与瞎猜无异。
另外会与原 variant_level_summary.csv 对表，验证"重跑推理"与原始结果一致。

用法：
    py phase2/ys/_rank_pct.py --pt-dir 10.13/group_fold_ys2/processed \
        --ckpt results/<run>/best_model_rs232t1000.pt --out 10.13/rank_pct_g2.csv
"""
import argparse
import importlib.util
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def load_tt23():
    """按文件路径加载 train_test2.3（模块名含点，不能直接 import）。尾部有 __main__ 保护。"""
    spec = importlib.util.spec_from_file_location("tt23", ROOT / "train_test2.3.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["tt23"] = m
    spec.loader.exec_module(m)
    return m


def mode_of(v: str) -> str:
    m = re.search(r"__(rw[a-z0-9]+)_d\d+_s\d+$", str(v))
    if m:
        return m.group(1)[2:].split("_d")[0]
    m = re.search(r"__(ys_[a-z0-9]+)$", str(v))
    if m:
        return m.group(1)
    return "src"


def ap_local(s: np.ndarray, y: np.ndarray) -> float:
    """平均精度（与 train_test2.3._ap 同义，自己实现以免依赖其内部签名）。"""
    n_pos = int((y == 1).sum())
    if n_pos == 0 or len(s) == 0:
        return float("nan")
    y_ord = y[np.argsort(-s)]
    csum = np.cumsum(y_ord)
    hits = np.flatnonzero(y_ord == 1)
    return float((csum[hits] / (hits + 1.0)).mean())


def recall_budget(s: np.ndarray, y: np.ndarray, frac: float) -> float:
    n_pos = int((y == 1).sum())
    if n_pos == 0 or len(s) == 0:
        return float("nan")
    k = max(1, int(len(s) * frac))
    top = np.argsort(-s)[:k]
    return float(y[top].sum() / n_pos)


def rank_stats(s: np.ndarray, y: np.ndarray):
    pos = np.flatnonzero(y == 1)
    n = len(s)
    if n == 0 or len(pos) == 0:
        return None
    rank_of = np.empty(n, dtype=np.int64)
    rank_of[np.argsort(-s)] = np.arange(1, n + 1)        # 1-based，1 = 最高分
    pct = rank_of / float(n)
    k1 = max(1, int(0.01 * n))
    neg = np.flatnonzero(y == 0)
    return {
        "n": n, "n_pos": int(len(pos)),
        "best_pos_pct": float(pct[pos].min()),
        "mean_pos_pct": float(pct[pos].mean()),
        "pos_top1pct": float((rank_of[pos] <= k1).mean()),
        "neg_med_pct": float(np.median(pct[neg])) if len(neg) else float("nan"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt-dir", type=Path, required=True)
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--config", type=Path, default=ROOT / "config_lr3e3.yaml")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    T = load_tt23()
    cfg = yaml.safe_load(a.config.read_text(encoding="utf-8"))
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    orig, trans, meta = T.load_fold(a.pt_dir)
    for d in (orig, trans):
        d.x, d.edge_index, d.y = d.x.to(device), d.edge_index.to(device), d.y.to(device)
    cfg["model"]["in_channels"] = int(orig.x.size(1))
    model = T.build_model(cfg, orig.x.size(1), device)
    ck = torch.load(a.ckpt, map_location=device, weights_only=False)
    model.load_state_dict(ck["state_dict"])
    model.eval()
    thr = float(ck.get("threshold", 0.5))

    vidx = T.view_index(trans)
    test_views = T.views_of_role(trans, "test")
    with torch.no_grad():
        pt = torch.softmax(model(trans.x, trans.edge_index).float(), dim=1)[:, 1].cpu().numpy()
        po = torch.softmax(model(orig.x, orig.edge_index).float(), dim=1)[:, 1].cpu().numpy()

    rows = []
    for v in test_views:
        idx = vidx[v].numpy()
        y = trans.y[idx].cpu().numpy()
        st = rank_stats(pt[idx], y)
        if st is None:                                    # 无正样本（对照视图）→ 不参与排名统计
            continue
        rows.append({"View": v, "mode": mode_of(v),
                     "kind": "trojan" if "__inj" in str(v) else "control",
                     "AP": ap_local(pt[idx], y),
                     "Recall@5%": recall_budget(pt[idx], y, 0.05),
                     "thr": thr, **st})

    # ORIG 参照：每个源网表一行（keep 之前的"未变换"口径）
    for stem in sorted(set(orig.file_ids)):
        m = np.array([f == stem for f in orig.file_ids])
        y = orig.y[m].cpu().numpy()
        st = rank_stats(po[m], y)
        if st is None:
            continue
        rows.append({"View": f"{stem}_ORIG", "mode": "ORIG", "kind": "trojan",
                     "AP": ap_local(po[m], y),
                     "Recall@5%": recall_budget(po[m], y, 0.05),
                     "thr": thr, **st})

    df = pd.DataFrame(rows)
    if df.empty:
        print("没有可统计的测试视图（检查 --pt-dir 的 view_role 是否含 test）")
        return 1

    csvp = a.ckpt.parent / "variant_level_summary.csv"
    if csvp.exists():                                     # 重跑推理与原表对表
        ref = pd.read_csv(csvp)
        ref = ref[ref["Type"] == "TRANS"][["View", "AP"]].rename(columns={"AP": "AP_原表"})
        df = df.merge(ref, on="View", how="left")
        df["AP差"] = (df["AP"] - df["AP_原表"]).abs()
        print(f"[一致性自检] 重跑 AP 与原表最大差 = {df['AP差'].max():.4f}"
              f"（应接近 0，否则说明重跑推理没对上）\n")

    g = (df.groupby(["mode", "kind"])
           .agg(视图数=("View", "size"), 正样本均数=("n_pos", "mean"),
                AP=("AP", "mean"), Recall5=("Recall@5%", "mean"),
                best_pos_pct=("best_pos_pct", "mean"),
                mean_pos_pct=("mean_pos_pct", "mean"),
                pos_top1pct=("pos_top1pct", "mean"),
                neg_med_pct=("neg_med_pct", "mean"))
           .round(4))
    print("=== 排名分位汇总（越小=木马越靠前；0.5=瞎猜）===")
    print(g.to_string())
    print("\n=== 逐视图 ===")
    cols = ["View", "mode", "kind", "n", "n_pos", "AP", "Recall@5%",
            "best_pos_pct", "mean_pos_pct", "pos_top1pct"]
    print(df[cols].round(4).to_string(index=False))
    if a.out:
        df.to_csv(a.out, index=False, encoding="utf-8-sig")
        print(f"\n[导出] {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
