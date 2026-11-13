# -*- coding: utf-8 -*-
"""make_ctrl_residual.py —— 第三步缺的那一项：**去掉对照后的剩余**。

说明.md 的本意：对每个特征扣掉"合法对照同样会变"的那部分，剩下的才是木马特异的部分。

口径（label-free 代理）：
    参考分布 = 每个 host 的**全部原网表注入视图**的节点级均值/标准差（近似干净基底）。
        为什么不用"对照的原网表"：orig 侧只有 30 个注入来源、**没有单独的对照来源** ✗
        （对照视图只存在于变换侧）——所以用 host 级参考、木马与对照同口径比较 ✓
    drift(f, T, kind) = |mean(f | 该 host 的 kind 类 T 变体视图) − 参考均值| / 参考标准差
    按 host 平均（电路等权）；residual(f, T) = drift(木马) − drift(对照)

用法：
    py phase2/ys/make_ctrl_residual.py --pt 10.13/group_fold_ys5/processed \
        --gl 10.13/group_fold_ys5/gatelookup_recommended.json --out 10.13/control_residual.csv
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

from phase2.ys.feature_retention import feature_names  # noqa: E402

MODES = ["decomp3", "bubble", "ys_rt", "ys_abc", "ys_aig"]


def mode_of(v: str) -> str:
    m = re.search(r"__(rw[a-z0-9]+)_d\d+_s\d+$", str(v))
    if m:
        return m.group(1)[2:].split("_d")[0]
    m = re.search(r"__(ys_[a-z0-9]+)$", str(v))
    return m.group(1) if m else "src"


def host_of(s) -> str:
    return str(s).split("__")[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt", type=Path, required=True)
    ap.add_argument("--gl", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=ROOT / "10.13" / "control_residual.csv")
    a = ap.parse_args()

    orig = torch.load(a.pt / "orig_graph.pt", weights_only=False)
    trans = torch.load(a.pt / "trans_graph.pt", weights_only=False)
    glp = a.gl or (a.pt.parent / "gatelookup_recommended.json")
    if not glp.exists():
        glp = a.pt / "gatelookup_recommended.json"
    names, _ = feature_names(glp.parent)
    Xo = orig.x.detach().cpu().numpy().astype(np.float64)
    Xt = trans.x.detach().cpu().numpy().astype(np.float64)
    F = min(Xt.shape[1], len(names))
    names = names[:F]
    of = np.asarray(list(orig.file_ids))
    tf = np.asarray(list(trans.file_ids))

    h_sum, h_sq, h_cnt = {}, {}, {}
    for stem in sorted(set(of.tolist())):
        m = of == stem
        if m.sum() == 0:
            continue
        h = host_of(stem)
        h_sum[h] = h_sum.get(h, 0) + Xo[m].sum(axis=0)
        h_sq[h] = h_sq.get(h, 0) + (Xo[m] ** 2).sum(axis=0)
        h_cnt[h] = h_cnt.get(h, 0) + int(m.sum())
    ref_mean = {h: h_sum[h] / h_cnt[h] for h in h_sum}
    ref_std = {h: np.sqrt(np.maximum(h_sq[h] / h_cnt[h] - ref_mean[h] ** 2, 1e-12))
               for h in h_sum}

    acc = {}
    for v in sorted(set(tf.tolist())):
        mv = mode_of(v)
        if mv not in MODES:
            continue
        s = str(v)
        h = host_of(s)
        if h not in ref_mean:
            continue
        kind = "trojan" if "__inj" in s else ("control" if "__ctl" in s else None)
        if kind is None:
            continue
        m = tf == v
        d = np.abs(Xt[m].mean(axis=0) - ref_mean[h]) / (ref_std[h] + 1e-9)
        acc.setdefault((h, kind, mv), []).append(d)

    long = []
    for (h, kind, mv), lst in acc.items():
        arr = np.asarray(lst)
        for i, n in enumerate(names):
            long.append({"host": h, "kind": kind, "mode": mv,
                         "feature": n, "drift": round(float(arr[:, i].mean()), 6)})
    L = pd.DataFrame(long)
    print("[覆盖] (kind, mode) → host 数：",
          L.groupby(["kind", "mode"])["host"].nunique().to_dict())
    piv = L.pivot_table(index=["feature", "mode"], columns="kind", values="drift").reset_index()
    for c in ("trojan", "control"):
        if c not in piv.columns:
            print(f"[WARN] 缺 {c} 来源")
            piv[c] = np.nan
    piv = piv.rename(columns={"trojan": "drift_trojan", "control": "drift_control"})
    piv["residual"] = piv["drift_trojan"] - piv["drift_control"]
    piv["group"] = ["gate_type" if i < 25 else "structural/topology" for i in range(len(piv))]
    piv.to_csv(a.out, index=False, encoding="utf-8-sig")

    for mv in MODES:
        sub = piv[piv["mode"] == mv]
        if sub.empty or sub["residual"].isna().all():
            continue
        sub = sub.sort_values("residual", ascending=False)
        print(f"\n=== {mv}：去掉对照后的剩余（越大越木马特异）top6 ===")
        print(sub[["feature", "group", "drift_trojan", "drift_control", "residual"]]
              .head(6).round(3).to_string(index=False))
    print(f"\n[导出] {a.out}（{len(piv)} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
