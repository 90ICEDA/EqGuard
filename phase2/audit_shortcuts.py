# -*- coding: utf-8 -*-
"""
audit_shortcuts.py —— 任务1：representation shortcut audit（不改主模型）

对每个已训练模型（G1/G2/G3/G4/M0…）：
  1) 取出「classifier 之前」的 64 维隐藏表示 h（forward hook，纯推理）；
  2) 对每个 trans 视图做 mean-pooling → 视图级特征；
  3) 训练三个**极简 probe**（logistic regression / 两层 MLP，sklearn）：
       - operator   : 4 类（chain[0] ∈ {decomp,balance,refactor,resub}）
       - depth      : 深度（d1/d2/d3）
       - circuit    : 电路 ID（5 类）
       - strength   : edit_ratio 分箱（4 箱，来自 matrix/view_metadata.csv）
     每个 probe 都报两种评估：
       - random CV（StratifiedKFold）：表示里「有多少」这类信息；
       - circuit-held-out CV（GroupKFold by circuit）：其中有多少是**跨电路可迁移**的，
         而不是单纯记住某个电路。
  4) 再用 check-style 的检查预算指标（AP_T / first-hit rank / Paired_MAE / Flip）做相关：
       每个视图的 probe 置信度 & 是否正确  ↔  该视图的检测指标。

用法：
  python phase2/audit_shortcuts.py --work-dir generate_trans/folds/single_to_composed_d2 \
      --model G1=results/single_to_composed_d2_seed42mode1_allb1_fold_G1_OrigOnly_amp \
      --model G4=results/single_to_composed_d2_seed42mode4_pred_hardb4_fold_G4_PredHard_amp
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase2 import p2common as C  # noqa: E402

PROBES = ["operator", "depth", "circuit", "strength"]
CKPT_DEFAULT = "best_model_ALL.pt"


def view_targets(views, vmeta: pd.DataFrame):
    """给每个视图构造 probe 标签。"""
    rows = []
    for v in views:
        info = C.parse_view(v)
        er = float(vmeta.loc[v, "edit_ratio"]) if v in vmeta.index else np.nan
        rows.append({"view": v, "stem": info.stem, "circuit": info.circuit,
                     "operator": info.first_op, "depth": info.depth,
                     "operators": info.operators, "seed": info.seed,
                     "edit_ratio": er,
                     "gate_expansion_ratio": (float(vmeta.loc[v, "gate_expansion_ratio"])
                                              if v in vmeta.index else np.nan)})
    df = pd.DataFrame(rows)
    df["strength_bin"] = pd.qcut(df["edit_ratio"].rank(method="first"), 4,
                                 labels=False, duplicates="drop")
    return df


def run_probe(X: np.ndarray, y: np.ndarray, groups: np.ndarray, kind: str,
              seed: int = 0, cvs=("random", "circuit_heldout")) -> dict:
    """跑 random CV 与 circuit-held-out CV，返回准确率/macro-F1 与逐样本置信度。"""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, GroupKFold, cross_val_predict
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.metrics import accuracy_score, f1_score

    y = np.asarray(y)
    n_cls = len(np.unique(y))
    if n_cls < 2 or len(y) < 8:
        return {}
    clf = make_pipeline(StandardScaler(),
                        LogisticRegression(max_iter=2000, C=1.0, n_jobs=None))
    _u, _c = np.unique(y, return_counts=True)
    if len(_u) < 2 or _c.min() < 2:
        return {}
    minc = min(int(_c.min()), 5)
    n_splits = int(max(2, min(5, minc)))
    out = {}
    choices = {"random": ("random", StratifiedKFold(n_splits=n_splits, shuffle=True,
                                                    random_state=seed)),
               "circuit_heldout": ("circuit_heldout",
                                   GroupKFold(n_splits=min(5, len(np.unique(groups)))))}
    for tag in cvs:
        _t, cv = choices[tag]
        try:
            proba = cross_val_predict(clf, X, y, cv=cv, groups=groups, method="predict_proba")
        except Exception as exc:                              # noqa: BLE001
            out[tag] = {"acc": np.nan, "macro_f1": np.nan, "err": str(exc)[:160]}
            print(f"    [probe {kind}/{tag}] 失败: {str(exc)[:120]}")
            continue
        pred = proba.argmax(1)
        classes = np.unique(y)
        conf = proba.max(1)
        out[tag] = {"acc": float(accuracy_score(y, pred)),
                    "macro_f1": float(f1_score(y, pred, average="macro")),
                    "pred": np.asarray(classes)[pred], "conf": conf,
                    "n_splits": (n_splits if tag == "random"
                                 else min(5, len(np.unique(groups))))}
    return out


def parse_models(items):
    out = {}
    for it in items:
        name, _, path = it.partition("=")
        if not path:
            raise SystemExit(f"[ERROR] --model 需要 NAME=PATH 形式，收到 {it}")
        out[name.strip()] = Path(path.strip())
    return out


def per_view_metrics(orig, trans, vidx_t, logits_o, logits_t, thr, alignment):
    """每个 trans 视图一行：检查预算指标 + 配对一致性（只保留 t 端落在该视图内的 pair）。"""
    import torch
    dev = logits_o.device
    po = torch.softmax(logits_o, 1)[:, 1]
    pt = torch.softmax(logits_t, 1)[:, 1]
    po_np, pt_np = po.cpu().numpy(), pt.cpu().numpy()
    al_o = alignment[0].cpu().numpy()
    al_t = alignment[1].cpu().numpy()
    rows = []
    for v, idx in vidx_t.items():
        idx_np = idx.cpu().numpy()
        y = trans.y[idx].detach().cpu().numpy().astype(int)
        m = C.view_budget_metrics(pt_np[idx_np], y)
        tm = np.isin(al_t, idx_np)
        ao = torch.tensor(al_o[tm], dtype=torch.long, device=dev)
        at = torch.tensor(al_t[tm], dtype=torch.long, device=dev)
        pc = (C.paired_consistency(logits_o, logits_t, torch.stack([ao, at]), orig.y, thr)
              if len(ao) > 1 else {})
        rows.append({"view": v, **m, **pc})
    return pd.DataFrame(rows)


PROBE_LABELS = {"operator": "operator", "depth": "depth",
                "circuit": "circuit", "strength": "strength_bin"}
CORR_METRICS = ["AP_T", "FirstHitRank_Norm", "InspectionCost", "Recall@5%",
                "Paired_MAE", "Flip_Rate", "Trojan_Drift"]


def main() -> int:
    ap = argparse.ArgumentParser(description="任务1：representation shortcut audit")
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--model", action="append", default=[],
                    help="NAME=<结果目录>，可多次；目录下应有 --ckpt-name")
    ap.add_argument("--ckpt-name", type=str, default=CKPT_DEFAULT)
    ap.add_argument("--matrix-root", type=Path, default=C.ROOT / "generate_trans" / "matrix")
    ap.add_argument("--out-dir", type=Path, default=C.ROOT / "results" / "phase2" / "audit")
    ap.add_argument("--amp", action="store_true")
    ap.add_argument("--plots", action="store_true", help="额外画 probe 置信度/正确性 vs 检查指标的散点图")
    args = ap.parse_args()

    models = parse_models(args.model)
    if not models:
        raise SystemExit("[ERROR] 至少给一个 --model NAME=PATH")

    import torch
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    work = args.work_dir.resolve()
    pt_dir = work / "data" / "processed"
    orig, trans, _meta = C.load_fold(pt_dir)
    for d in (orig, trans):
        d.x = d.x.to(device); d.edge_index = d.edge_index.to(device)
        d.y = d.y.to(device)
    alignment = trans.alignment.to(device)
    vidx_t = {v: ix.to(device) for v, ix in C.view_index(trans).items()}

    vmeta = C.load_view_metadata(args.matrix_root)
    tgt = view_targets(sorted(vidx_t), vmeta)
    views = tgt["view"].tolist()
    groups = tgt["circuit"].to_numpy()
    C.ensure_dir(args.out_dir)

    probe_rows, corr_rows, per_view_all, summary_rows = [], [], [], []
    for name, mdir in models.items():
        ck = mdir / args.ckpt_name
        if not ck.exists():
            print(f"[WARN] 缺少 {ck}，跳过 {name}")
            continue
        model, blob = C.load_ckpt(ck, device)
        thr = float(blob["threshold"])
        with C.Embedder(model) as emb:
            h_o, lo = emb.forward(orig.x, orig.edge_index, amp=args.amp)
            h_t, lt = emb.forward(trans.x, trans.edge_index, amp=args.amp)
        X = np.stack([h_t[vidx_t[v]].mean(0).cpu().numpy() for v in views])
        pv = per_view_metrics(orig, trans, vidx_t, lo, lt, thr, alignment)
        pv = tgt.merge(pv, on="view", how="left")

        for probe in PROBES:
            col = PROBE_LABELS[probe]
            lab = pv[col]
            ok = lab.notna()
            y_raw = lab[ok]
            if y_raw.nunique() < 2:
                continue
            codes, _uniq = pd.factorize(y_raw)          # 字符串/整数标签统一编码为 0..K-1
            y = codes.astype(int)
            # 注意：circuit probe 的 circuit-held-out 在定义上不可分类
            #（训练集必不含被留出的电路类别）→ 只报 random CV。
            cvs = ("random",) if probe == "circuit" else ("random", "circuit_heldout")
            res = run_probe(X[ok.to_numpy()], y, groups[ok.to_numpy()], probe, cvs=cvs)
            if not res:
                continue
            for tag in cvs:
                r = res.get(tag, {})
                probe_rows.append({"model": name, "probe": probe, "cv": tag,
                                   "n": int(len(y)), "n_classes": int(len(np.unique(y))),
                                   "acc": r.get("acc", np.nan),
                                   "macro_f1": r.get("macro_f1", np.nan),
                                   "n_splits": r.get("n_splits", np.nan),
                                   "err": r.get("err", "")})
            rr = res.get("random", {})
            if "pred" in rr:
                pv.loc[ok, f"{probe}_pred"] = rr["pred"]
                pv.loc[ok, f"{probe}_conf"] = rr["conf"]
                pv.loc[ok, f"{probe}_correct"] = (rr["pred"] == y).astype(float)
        pv.insert(0, "model", name)
        per_view_all.append(pv)

        for probe in PROBES:
            if f"{probe}_conf" not in pv.columns:
                continue
            from scipy.stats import spearmanr
            for m in CORR_METRICS:
                if m not in pv.columns:
                    continue
                d = pv[[f"{probe}_conf", f"{probe}_correct", m]].dropna()
                if len(d) < 12:
                    continue
                rc, pc = spearmanr(d[f"{probe}_conf"], d[m])
                ra, pa = spearmanr(d[f"{probe}_correct"], d[m])
                corr_rows.append({"model": name, "probe": probe, "metric": m, "n": len(d),
                                  "rho_conf": round(float(rc), 4), "p_conf": round(float(pc), 4),
                                  "rho_correct": round(float(ra), 4),
                                  "p_correct": round(float(pa), 4)})
        summary_rows.append({
            "model": name, "n_views": int(len(pv)),
            "mean_AP_T": float(pv["AP_T"].mean()),
            "mean_FirstHitRank_Norm": float(pv["FirstHitRank_Norm"].mean()),
            "AnyMiss@5%": float(pv["AnyMiss@5%"].mean()),
            "mean_InspectionCost": float(pv["InspectionCost"].mean()),
            "mean_Paired_MAE": float(pv["Paired_MAE"].mean()),
            "mean_Flip_Rate": float(pv["Flip_Rate"].mean()),
            "mean_Trojan_Drift": float(pv["Trojan_Drift"].mean()),
        })
        print(f"[{name}] 视图 {len(pv)}｜AP_T {pv['AP_T'].mean():.4f}｜"
              f"rank_norm {pv['FirstHitRank_Norm'].mean():.4f}｜"
              f"Paired_MAE {pv['Paired_MAE'].mean():.4f}｜Flip {pv['Flip_Rate'].mean():.4f}")

    pv_all = pd.concat(per_view_all, ignore_index=True) if per_view_all else pd.DataFrame()
    probe_df = pd.DataFrame(probe_rows)
    corr_df = pd.DataFrame(corr_rows)
    summ_df = pd.DataFrame(summary_rows)
    tag = work.name
    pv_all.to_csv(args.out_dir / f"{tag}_per_view.csv", index=False, encoding="utf-8-sig")
    probe_df.to_csv(args.out_dir / f"{tag}_probe_metrics.csv", index=False, encoding="utf-8-sig")
    corr_df.to_csv(args.out_dir / f"{tag}_correlations.csv", index=False, encoding="utf-8-sig")
    summ_df.to_csv(args.out_dir / f"{tag}_model_summary.csv", index=False, encoding="utf-8-sig")

    # ---- 跨模型：shortcut 强度 ↔ 检测指标 ----
    if not probe_df.empty and not summ_df.empty:
        wide = probe_df.pivot_table(index="model", columns=["probe", "cv"], values="acc")
        wide.columns = ["acc_" + "_".join(str(x) for x in c) for c in wide.columns]
        cross = summ_df.set_index("model").join(wide)
        cross.to_csv(args.out_dir / f"{tag}_shortcut_vs_drift.csv", encoding="utf-8-sig")
        print("\n=== shortcut 强度 vs 检测指标（跨模型）===")
        print(cross.round(4).to_string())
        from scipy.stats import spearmanr
        rows = []
        for c in list(wide.columns):
            for m in ["mean_AP_T", "mean_FirstHitRank_Norm", "mean_Paired_MAE",
                      "mean_Flip_Rate", "AnyMiss@5%"]:
                d = cross[[c, m]].dropna()
                if len(d) >= 3:
                    r, p = spearmanr(d[c], d[m])
                    rows.append({"shortcut": c, "metric": m, "n_models": len(d),
                                 "rho": round(float(r), 4), "p": round(float(p), 4)})
        pd.DataFrame(rows).to_csv(args.out_dir / f"{tag}_shortcut_drift_rho.csv",
                                  index=False, encoding="utf-8-sig")

    print("\n=== probe 指标（acc；random CV vs circuit-held-out）===")
    if not probe_df.empty:
        print(probe_df.pivot_table(index=["model", "probe"], columns="cv",
                                   values="acc").round(4).to_string())
    if args.plots and not pv_all.empty:
        make_plots(pv_all, corr_df, args.out_dir / "figures", tag)

    print(f"\n[导出] {args.out_dir}")
    return 0


def make_plots(pv_all: pd.DataFrame, corr: pd.DataFrame, fig_dir: Path, tag: str) -> None:
    """散点图：probe 置信度（x）↔ 检查指标（y），每个 (probe, metric) 一张，按模型着色。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    C.ensure_dir(fig_dir)
    metrics = [m for m in ["AP_T", "FirstHitRank_Norm", "Paired_MAE", "Flip_Rate"]
               if m in pv_all.columns]
    probes = [p for p in ["operator", "depth", "strength", "circuit"]
              if f"{p}_conf" in pv_all.columns]
    models = sorted(pv_all["model"].unique())
    for probe in probes:
        for m in metrics:
            fig, ax = plt.subplots(figsize=(4.2, 3.6), dpi=140)
            rho = None
            for mo in models:
                d = pv_all[(pv_all.model == mo)][[f"{probe}_conf", m]].dropna()
                if d.empty:
                    continue
                ax.scatter(d[f"{probe}_conf"], d[m], s=8, alpha=0.6, label=mo)
            sub = corr[(corr.probe == probe) & (corr.metric == m)]
            if not sub.empty:
                rho = ", ".join(f"{r.model}:ρ={r.rho_conf:.2f}" for r in sub.itertuples())
            ax.set_xlabel(f"{probe} probe confidence")
            ax.set_ylabel(m)
            ax.set_title(f"{probe} vs {m}" + (f"\n{rho}" if rho else ""), fontsize=8)
            ax.legend(fontsize=6, loc="best")
            fig.tight_layout()
            fig.savefig(fig_dir / f"{tag}_{probe}_vs_{m}.png")
            plt.close(fig)
    print(f"[plots] 散点图 -> {fig_dir}")


if __name__ == "__main__":
    raise SystemExit(main())

