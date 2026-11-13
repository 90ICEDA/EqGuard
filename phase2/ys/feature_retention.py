# -*- coding: utf-8 -*-
"""feature_retention.py —— 第三步：特征保持率审计（找"对等价变换稳、对木马敏感"的特征）。

背景（由 ys_rt 上界实验确定）：
    纯往返 `flatten`（不优化、CEC 277/277 等价、标签完备、正样本数与原网表相同）就能让
    检测器崩到 best_pos_pct 0.0838，与 abc 重综合的 0.0832 几乎相同 → 说明模型的判据
    建立在"库单元层级"上。本脚本把这个判断量化到**特征级**：

    对 39 个节点特征逐个计算
        d_orig  = AUC(feature | 木马 vs 干净) − 0.5     在原网表上（对木马敏感度，秩口径）
        d_mode  = 同上，在各等价变体视图上（decomp3 / bubble / ys_rt / ys_abc / ys_aig）
        保持率  = d_mode / d_orig
    并用 Cohen's d（标准化均值差）做交叉验证（写在 CSV 里）。

    分级（阈值可调）：
        伪信号      d_orig ≥ 0.10 且 ys_rt 保持率 ≤ 0.30   ← 模型现在依赖的就是这类
        候选真信号  d_orig ≥ 0.10 且 ys_rt 保持率 ≥ 0.70
        中间/无关   其余

用法：
    py phase2/ys/feature_retention.py --fold 10.13/fold_ys5 --out 10.13/feature_retention_g5.csv
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

STRUCT_NAMES = ["log1p_n_input_ports", "log1p_degree", "touches_PI", "touches_PO",
                "dist_to_PI", "dist_to_PO", "log1p_fan_in_2hop", "log1p_fan_out_2hop",
                "dag_dist_to_PI", "dag_dist_to_PO", "log1p_dag_fan_in_2hop",
                "log1p_dag_fan_out_2hop", "in_cycle", "log1p_scc_size"]


def feature_names(fold: Path):
    gl = json.loads((fold / "gatelookup_recommended.json").read_text(encoding="utf-8"))
    order = gl.get("simplified_gate_type_order") or list(gl["gatelookup"].keys())
    gate = [f"gate_{t}" for t in order]
    groups = ["gate_type"] * len(gate) + ["structural"] * 4 + ["topology"] * 4 + ["cycle"] * 6
    names = gate + STRUCT_NAMES
    if len(names) != len(groups):
        raise SystemExit(f"[ERROR] 名字 {len(names)} 与分组 {len(groups)} 数量不符")
    return names, groups


def auc_one(v: np.ndarray, y: np.ndarray) -> float:
    """单特征 AUC（秩公式）。全零列或只有一类 → nan（=该特征已消失）。"""
    n1, n0 = int((y == 1).sum()), int((y == 0).sum())
    if n1 == 0 or n0 == 0 or np.allclose(v, v[0]):
        return float("nan")
    r = rankdata(v)
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def cohen_one(v: np.ndarray, y: np.ndarray) -> float:
    a, b = v[y == 1], v[y == 0]
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    sp = np.sqrt((a.std(ddof=1) ** 2 + b.std(ddof=1) ** 2) / 2.0)
    return float("nan") if sp < 1e-12 else float((a.mean() - b.mean()) / sp)


def mode_of(v: str) -> str:
    m = re.search(r"__(rw[a-z0-9]+)_d\d+_s\d+$", str(v))
    if m:
        return m.group(1)[2:].split("_d")[0]
    m = re.search(r"__(ys_[a-z0-9]+)$", str(v))
    if m:
        return m.group(1)
    return "src"


def retain(auc_mode: float, auc_orig: float) -> float:
    """保持率 = (AUC_mode-0.5)/(AUC_orig-0.5)。特征消失（nan）记 0。"""
    if not np.isfinite(auc_orig) or abs(auc_orig - 0.5) < 1e-6:
        return float("nan")
    if not np.isfinite(auc_mode):
        return 0.0
    return float((auc_mode - 0.5) / (auc_orig - 0.5))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=Path, required=True)
    ap.add_argument("--circuit", default="rs232t1000")
    ap.add_argument("--test-role", default="test")
    ap.add_argument("--tier-sens", type=float, default=0.10, help="判定敏感的最低 AUC-0.5")
    ap.add_argument("--keep-hi", type=float, default=0.70)
    ap.add_argument("--keep-lo", type=float, default=0.30)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    import torch
    ptd = a.fold / "data" / "processed"
    if not (ptd / "orig_graph.pt").exists():
        ptd = a.fold / "processed"     # 分组划分的输出把 pt 直接放在 processed/ 下
    if not (ptd / "orig_graph.pt").exists():
        print(f"[ERROR] 找不到 pt：{ptd}")
        return 1
    orig = torch.load(ptd / "orig_graph.pt", weights_only=False)
    trans = torch.load(ptd / "trans_graph.pt", weights_only=False)
    Xo = orig.x.detach().cpu().numpy().astype(np.float64)
    yo = orig.y.detach().cpu().numpy()
    Xt = trans.x.detach().cpu().numpy().astype(np.float64)
    yt = trans.y.detach().cpu().numpy()
    names, groups = feature_names(a.fold)
    F = min(Xt.shape[1], len(names))
    names, groups = names[:F], groups[:F]

    of = np.asarray(list(orig.file_ids))
    o_auc, o_d, o_cnt = [], [], []
    for stem in sorted(set(of.tolist())):
        if not str(stem).startswith(a.circuit):
            continue
        m = of == stem
        yy = yo[m]
        if int((yy == 1).sum()) == 0:
            continue
        xo = Xo[m]
        o_auc.append([auc_one(xo[:, j], yy) for j in range(F)])
        o_d.append([cohen_one(xo[:, j], yy) for j in range(F)])
        o_cnt.append(int((yy == 1).sum()))
    if not o_auc:
        print(f"[ERROR] 原网表侧没有 {a.circuit} 的正样本视图")
        return 1
    AUC_O = np.nanmean(np.asarray(o_auc), axis=0)
    D_O = np.nanmean(np.asarray(o_d), axis=0)

    tf = np.asarray(list(trans.file_ids))
    role = dict(trans.view_role)
    by_mode = {}
    for v in sorted(set(tf.tolist())):
        if role.get(v) != a.test_role or not str(v).startswith(a.circuit):
            continue
        m = tf == v
        yy = yt[m]
        if int((yy == 1).sum()) == 0:
            continue
        xt = Xt[m]
        by_mode.setdefault(mode_of(v), []).append(
            ([auc_one(xt[:, j], yy) for j in range(F)],
             [cohen_one(xt[:, j], yy) for j in range(F)]))
    if not by_mode:
        print(f"[ERROR] 变换侧没有 role={a.test_role} 且属于 {a.circuit} 的视图")
        return 1

    modes = sorted(by_mode)
    AUC_M = {md: np.nanmean(np.asarray([r[0] for r in rows]), axis=0)
             for md, rows in by_mode.items()}
    D_M = {md: np.nanmean(np.asarray([r[1] for r in rows]), axis=0)
           for md, rows in by_mode.items()}
    ref = "ys_rt" if "ys_rt" in AUC_M else modes[0]

    ok = np.isfinite(D_O) & np.isfinite(AUC_O)
    sp = float(pd.Series(np.abs(D_O[ok])).corr(
        pd.Series(np.abs(AUC_O[ok] - 0.5)), method="spearman"))

    df = pd.DataFrame({"feature": names, "group": groups, "auc_orig": AUC_O,
                       "cohen_orig": D_O, "sens_orig": np.abs(AUC_O - 0.5)})
    for md in modes:
        df[f"auc_{md}"] = AUC_M[md]
        df[f"cohen_{md}"] = D_M[md]
        df[f"retain_{md}"] = [retain(AUC_M[md][j], AUC_O[j]) for j in range(F)]

    def tier(s, r):
        if not np.isfinite(s) or s < a.tier_sens:
            return "无关"
        if np.isfinite(r) and r >= a.keep_hi:
            return "候选真信号"
        if (not np.isfinite(r)) or r <= a.keep_lo:
            return "伪信号"
        return "中间"

    df["tier"] = [tier(df.sens_orig[i], df.loc[i, f"retain_{ref}"]) for i in range(F)]

    print(f"[口径] 电路 {a.circuit}｜原网表视图 {len(o_auc)} 个（正样本/视图均值 "
          f"{np.mean(o_cnt):.1f}）｜变换侧 " +
          " ".join(f"{m}:{len(v)}" for m, v in sorted(by_mode.items())))
    print(f"[交叉验证] |Cohen's d| 与 |AUC-0.5| 的特征排序 Spearman = {sp:.3f}"
          f"（接近 1 说明两个口径一致，结论不依赖具体统计量）")

    pd.set_option("display.width", 250)
    show = ["feature", "group", "auc_orig", "sens_orig"] + \
           [f"auc_{m}" for m in modes] + [f"retain_{m}" for m in modes] + ["tier"]
    print(df.sort_values("sens_orig", ascending=False)[show].round(4).to_string(index=False))
    print("\n=== 分级（判据：原网表 AUC-0.5 ≥ %.2f；%s 保持率 ≥ %.2f → 候选真信号，≤ %.2f → 伪信号）==="
          % (a.tier_sens, ref, a.keep_hi, a.keep_lo))
    print(df.groupby("tier").size().to_string())
    print("\n=== 按组别 × 分级 ===")
    print(df.groupby(["group", "tier"]).size().unstack(fill_value=0).to_string())
    if a.out:
        df.to_csv(a.out, index=False, encoding="utf-8-sig")
        print(f"\n[导出] {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
