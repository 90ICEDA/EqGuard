# -*- coding: utf-8 -*-
"""
feature_audit.py —— 特征审计（四问的第 1 问：**等价稳定性**）

问题：对每个特征，**同一个对象在等价改写前后，这个特征的排序还稳不稳？**

做法：
  1. 用 `mappings/*.json` 的 `node_alignment` + `phase2/name_index.py` 得到
     每个视图的「对象 → 目标节点集合」（对象 = 原图的一个门）；
  2. 一个视图的特征矩阵 F[v]（n_objects × n_features）= 对象内目标节点特征的**均值**
     （这就是"不要直接一锅平均"的正确版本：**按对象聚合**，而不是整个 region 平均）；
  3. 对同一电路的两个视图 v1/v2，按 **o_idx 对齐**后，对每一维算 **Spearman 排序相关**；
  4. 报三个口径（原始 / 视图内百分位归一化 / 只用 1↔1 对象），
     以及 `orig ↔ view` 的稳定性。

输出：`<out>/feature_stability.csv`（每维一行）+ 可选分布图。

用法：
  python phase2/feature_audit.py --work-dir generate_trans/folds/single_to_composed_d2 \
      --out-dir results/phase2/feature_audit --plots
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.stats import rankdata

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase2 import p2common as C  # noqa: E402
from phase2.name_index import build_name_index  # noqa: E402
from phase2.objects import build_object_groups  # noqa: E402

# 39 维的构成（由 parser2 源码 + 实测确认）：
#   0..24  featsleft  门类型 one-hot（顺序见 gatelookup_recommended.json 的 simplified_gate_type_order）
#   25     featsright log1p(输入端口数)
#   26     featsright log1p(度数)
#   27     featsright 是否接原输入(PI)
#   28     featsright 是否接原输出(PO)
#   29/30  distances  到 PI / 到 PO 的距离
#   31/32  fan        log1p(2-hop 扇入) / log1p(2-hop 扇出)
#   33..38 contract   到 PI_DAG / 到 PO_DAG / DAG 2-hop 扇入 / DAG 2-hop 扇出 / in_cycle / log1p(scc_size)
STRUCT_NAMES = ["log1p_n_input_ports", "log1p_degree", "touches_PI", "touches_PO",
                "dist_to_PI", "dist_to_PO", "log1p_fan_in_2hop", "log1p_fan_out_2hop",
                "dag_dist_to_PI", "dag_dist_to_PO", "log1p_dag_fan_in_2hop",
                "log1p_dag_fan_out_2hop", "in_cycle", "log1p_scc_size"]


def feature_names(work_dir: Path):
    gl = json.loads((work_dir / "gatelookup_recommended.json").read_text(encoding="utf-8"))
    order = gl.get("simplified_gate_type_order") or list(gl["gatelookup"].keys())
    gate = [f"gate_{t}" for t in order]
    names = gate + STRUCT_NAMES
    groups = ["gate_type"] * len(gate) + [
        "structural", "structural", "structural", "structural",
        "topology", "topology", "topology", "topology",
        "cycle", "cycle", "cycle", "cycle", "cycle", "cycle"]
    if len(names) != len(groups):
        raise SystemExit(f"[ERROR] 特征名数量 {len(names)} != 分组数量 {len(groups)}")
    return names, groups


def view_feature_matrix(feat_np: np.ndarray, items, n_feat: int):
    """items = [(o_idx, t_idx_array), ...] → (obj_idx, F, n_targets_per_obj)"""
    o = np.asarray([it[0] for it in items], dtype=np.int64)
    gid, tt = [], []
    for i, (_oi, ts) in enumerate(items):
        gid.append(np.full(len(ts), i, dtype=np.int64))
        tt.append(np.asarray(ts, dtype=np.int64))
    gid = np.concatenate(gid) if gid else np.zeros(0, dtype=np.int64)
    tt = np.concatenate(tt) if tt else np.zeros(0, dtype=np.int64)
    n_obj = len(o)
    S = sp.csr_matrix((np.ones(len(gid), dtype=np.float32), (gid, np.arange(len(gid)))),
                      shape=(n_obj, max(1, len(gid))))
    cnt = np.asarray(S.sum(axis=1)).ravel()
    cnt[cnt == 0] = 1.0
    F = (S @ feat_np[tt]) / cnt[:, None]
    return o, np.asarray(F, dtype=np.float64), cnt


def spearman_cols(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """对每一列算 Spearman（列间独立），返回长度 F 的数组。输入已是对齐后的 m×F。"""
    RA = rankdata(A, axis=0)
    RB = rankdata(B, axis=0)
    RA -= RA.mean(axis=0, keepdims=True)
    RB -= RB.mean(axis=0, keepdims=True)
    num = (RA * RB).sum(axis=0)
    den = np.sqrt((RA ** 2).sum(axis=0) * (RB ** 2).sum(axis=0))
    out = np.full(A.shape[1], np.nan)
    ok = den > 1e-12
    out[ok] = num[ok] / den[ok]
    return out


def percentile_norm(F: np.ndarray) -> np.ndarray:
    """视图内百分位（每个特征列独立），用来实现"按电路归一化"的比较口径。"""
    n = F.shape[0]
    if n <= 1:
        return F.copy()
    R = rankdata(F, axis=0)
    return (R - 0.5) / n


def pair_spearman(va, vb):
    """对齐两个视图的对象后，返回 (raw_spearman, pct_spearman, raw_1to1_spearman, n_common, n_1to1)。"""
    oa, Fa_raw, Fa_pct, cnta = va
    ob, Fb_raw, Fb_pct, cntb = vb
    common, ia, ib = np.intersect1d(oa, ob, return_indices=True)
    if len(common) < 8:
        return None
    ra, rb = Fa_raw[ia], Fb_raw[ib]
    pa, pb = Fa_pct[ia], Fb_pct[ib]
    one = (cnta[ia] == 1) & (cntb[ib] == 1)
    return (spearman_cols(ra, rb), spearman_cols(pa, pb),
            spearman_cols(ra[one], rb[one]) if one.sum() >= 8 else None,
            len(common), int(one.sum()))


def main() -> int:
    ap = argparse.ArgumentParser(description="特征审计：等价稳定性（四问第 1 问）")
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=C.ROOT / "results" / "phase2" / "feature_audit")
    ap.add_argument("--max-pairs", type=int, default=120, help="每个电路最多采样多少对视图")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--plots", action="store_true")
    args = ap.parse_args()

    work = args.work_dir.resolve()
    orig, trans, _meta = C.load_fold(work / "data" / "processed")
    X_t = trans.x.detach().cpu().numpy().astype(np.float32)
    X_o = orig.x.detach().cpu().numpy().astype(np.float32)
    names, groups = feature_names(work)
    F = min(X_t.shape[1], len(names))
    names, groups = names[:F], groups[:F]
    if X_t.shape[1] != len(names):
        print(f"[WARN] 数据维度 {X_t.shape[1]}，特征名按 {F} 维截断")

    grp = build_object_groups(work, include_identity=True)
    print(f"[info] 视图 {len(grp)}｜特征 {F} 维（门类型 {groups.count('gate_type')} / "
          f"结构 {groups.count('structural')} / 拓扑 {groups.count('topology')} / "
          f"环 {groups.count('cycle')}）")

    per_view, by_stem = {}, {}
    for v, items in grp.items():
        o, Fraw, cnt = view_feature_matrix(X_t, items, F)
        per_view[v] = (o, Fraw[:, :F], percentile_norm(Fraw[:, :F]), cnt)
        by_stem.setdefault(C.parse_view(v).stem, []).append(v)
    orig_obj = (np.arange(len(X_o), dtype=np.int64), X_o[:, :F].astype(np.float64),
                percentile_norm(X_o[:, :F].astype(np.float64)), np.ones(len(X_o)))

    rng = np.random.default_rng(args.seed)
    acc = {k: [] for k in ("vv_raw", "vv_pct", "vv_1to1", "ov_raw", "ov_pct")}
    n_pair = 0
    for stem, views in sorted(by_stem.items()):
        views = sorted(views)
        combos = [(a, b) for i, a in enumerate(views) for b in views[i + 1:]]
        if len(combos) > args.max_pairs:
            idx = rng.choice(len(combos), size=args.max_pairs, replace=False)
            combos = [combos[i] for i in sorted(idx)]
        for a, b in combos:
            r = pair_spearman(per_view[a], per_view[b])
            if r is None:
                continue
            acc["vv_raw"].append(r[0]); acc["vv_pct"].append(r[1])
            if r[2] is not None:
                acc["vv_1to1"].append(r[2])
            n_pair += 1
        for v in views[:min(len(views), 8)]:
            r = pair_spearman(orig_obj, per_view[v])
            if r is not None:
                acc["ov_raw"].append(r[0]); acc["ov_pct"].append(r[1])

    def agg(key):
        arr = np.asarray(acc[key])
        if arr.size == 0:
            return np.full(F, np.nan), np.full(F, np.nan)
        return np.nanmedian(arr, axis=0), np.nanmean(arr, axis=0)

    med_vv, mean_vv = agg("vv_raw")
    med_vvp, _ = agg("vv_pct")
    med_11, _ = agg("vv_1to1")
    med_ov, mean_ov = agg("ov_raw")
    med_ovp, _ = agg("ov_pct")
    df = pd.DataFrame({
        "idx": np.arange(F), "feature": names, "group": groups,
        "stab_view_view_median": np.round(med_vv, 4),
        "stab_view_view_mean": np.round(mean_vv, 4),
        "stab_view_view_percentile": np.round(med_vvp, 4),
        "stab_view_view_1to1only": np.round(med_11, 4),
        "stab_orig_view_median": np.round(med_ov, 4),
        "stab_orig_view_mean": np.round(mean_ov, 4),
        "stab_orig_view_percentile": np.round(med_ovp, 4),
    })
    df["split_penalty"] = np.round(df["stab_view_view_1to1only"] - df["stab_view_view_median"], 4)
    df["stable"] = df["stab_view_view_median"] >= 0.9
    C.ensure_dir(args.out_dir)
    tag = work.name
    out = args.out_dir / f"{tag}_feature_stability.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    report(df, groups, F, n_pair, tag, out)
    if args.plots:
        make_plots(df, args.out_dir / "figures", tag)
    return 0


def report(df, groups, F, n_pair, tag, out) -> None:
    print(f"\n=== 等价稳定性（{tag}｜{n_pair} 个视图对）===")
    print("按分组的平均稳定性（1.0 = 换个等价实现后，对象的排序完全不变）：")
    print(df.groupby("group")[["stab_view_view_median", "stab_view_view_percentile",
                               "stab_orig_view_median"]].mean().round(3).to_string())
    print("\n最稳的 10 维：")
    print(df.nlargest(10, "stab_view_view_median")[
        ["feature", "group", "stab_view_view_median", "stab_orig_view_median"]].to_string(index=False))
    print("\n最不稳的 10 维：")
    print(df.nsmallest(10, "stab_view_view_median")[
        ["feature", "group", "stab_view_view_median", "stab_orig_view_median"]].to_string(index=False))
    n_gate = groups.count("gate_type")
    n_stable = int(df["stable"].sum())
    print(f"\n稳定性 ≥0.9 的特征：{n_stable}/{F}"
          f"（门类型 {int(((df.group == 'gate_type') & df.stable).sum())}/{n_gate}；"
          f"非门类型 {int(((df.group != 'gate_type') & df.stable).sum())}/{F - n_gate}）")
    print(f"\n[导出] {out}")


def make_plots(df: pd.DataFrame, fig_dir: Path, tag: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    C.ensure_dir(fig_dir)
    d = df.sort_values("stab_view_view_median")
    colors = {"gate_type": "tab:red", "structural": "tab:blue",
              "topology": "tab:green", "cycle": "tab:orange"}
    fig, ax = plt.subplots(figsize=(7, 9), dpi=140)
    ax.barh(range(len(d)), d["stab_view_view_median"],
            color=[colors.get(g, "gray") for g in d["group"]])
    ax.set_yticks(range(len(d)))
    ax.set_yticklabels(d["feature"], fontsize=5.5)
    ax.axvline(0.9, color="k", ls="--", lw=0.8)
    ax.set_xlabel("等价稳定性（视图间 Spearman 中位数）")
    ax.set_title(f"{tag}: 逐维等价稳定性\n红=门类型 one-hot, 蓝=结构, 绿=拓扑, 橙=环", fontsize=9)
    fig.tight_layout()
    fig.savefig(fig_dir / f"{tag}_feature_stability.png")
    plt.close(fig)
    print(f"[plots] -> {fig_dir / f'{tag}_feature_stability.png'}")


if __name__ == "__main__":
    raise SystemExit(main())

