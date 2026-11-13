# -*- coding: utf-8 -*-
"""
object_stats.py —— 任务2：把 correspondence 做成真正的「对象统计」

不只看 lineage 对不对，而是统计 **Trojan 相关源对象** 经过 rewrite 之后的去向：
    1→1 / 1→N / N→1 / N→M / shared / eliminated / unresolved
每类给数量与占比，并在给了 checkpoint 时分别统计这些类别下 G1/G3/G4 的逐节点 drift。

定义（对某个 trans 视图 v、某个 orig 对象 O）：
    L(O)  = node_alignment[O] ∩ nodes(view v)      （显式血缘；缺键时回落到同名身份映射）
    d_out = |L(O)|
    shared(O) = ∃T∈L(O) 使得 indeg(T) ≥ 2           （T 同时被 ≥2 个 orig 对象映射到）
    category:
        d_out == 0                 -> eliminated
        d_out == 1 and not shared  -> 1to1
        d_out == 1 and shared      -> Nto1     （多个源对象合并到同一个目标 / 目标被共享）
        d_out >  1 and not shared  -> 1toN     （源对象被拆分）
        d_out >  1 and shared      -> NtoM     （既拆又并）
    unresolved  = 既无显式血缘、又无法同名身份映射的源对象
另外单独报告 shared_trans_objects（indeg ≥ 2 的 trans 对象数量）。

用法：
  python phase2/object_stats.py --work-dir generate_trans/folds/single_to_composed_d2
  python phase2/object_stats.py --work-dir ... --ckpt-dir results/<run> --ckpt-glob "best_model_ALL.pt"
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase2 import p2common as C  # noqa: E402
from phase2.name_index import build_name_index  # noqa: E402

CATEGORIES = ["1to1", "1toN", "Nto1", "NtoM", "eliminated", "unresolved", "shared"]


def clean(name: str) -> str:
    return str(name).lstrip("\\")


def is_trojan_name(name: str) -> bool:
    return "trojan" in str(name).lower()


def analyse_view(view: str, map_data: dict, orig_names: dict, trans_names: dict):
    """返回 (每个 orig 对象一行, 视图级汇总)。"""
    info = C.parse_view(view)
    node_align = map_data.get("node_alignment", {}) or {}
    tset = set(trans_names)

    # 1) 显式血缘（只保留在本视图真实存在的 trans 名字）
    L = {}
    for o_name, t_names in node_align.items():
        o = clean(o_name)
        if o not in orig_names:
            continue
        L[o] = [clean(t) for t in (t_names or []) if clean(t) in tset]

    # 2) 身份回落（名字未变动的门）
    identity_objs = set()
    for o in orig_names:
        if o in L:
            continue
        if o in tset:
            L[o] = [o]
            identity_objs.add(o)

    # 3) indeg（目标被多少源对象映射到）
    indeg = Counter()
    for o, tt in L.items():
        for t in tt:
            indeg[t] += 1

    rows, agg = [], Counter()
    for o in orig_names:
        tt = L.get(o)
        shared = bool(tt) and any(indeg[t] >= 2 for t in tt)
        if tt is None:
            cat = "unresolved"
        elif len(tt) == 0:
            cat = "eliminated"
        elif len(tt) == 1:
            cat = "Nto1" if shared else "1to1"
        else:
            cat = "NtoM" if shared else "1toN"
        agg[cat] += 1
        if shared:
            agg["shared"] += 1
        rows.append({
            "view": view, "circuit": info.circuit, "stem": info.stem,
            "operators": info.operators, "depth": info.depth, "seed": info.seed,
            "orig_obj": o, "is_trojan": int(is_trojan_name(o)),
            "n_targets": len(tt) if tt is not None else -1,
            "category": cat, "identity": int(o in identity_objs),
        })
    agg["shared_trans_objects"] = sum(1 for t, d in indeg.items() if d >= 2)
    agg["n_orig_objects"] = len(orig_names)
    agg["n_trans_objects"] = len(trans_names)
    return rows, agg


def _share(dfx: pd.DataFrame, trojan_only: bool, keys=("circuit",)) -> pd.DataFrame:
    """按 keys 分组统计各类别计数/占比。

    注意：`shared` 不是互斥类别（Nto1 / NtoM 都是「目标被 ≥2 个源对象共享」），
    因此这里把它显式定义为 `n_Nto1 + n_NtoM`，不参与 tot 求和。
    """
    d = dfx[dfx["is_trojan"] == 1] if trojan_only else dfx
    keys = list(keys)
    g = d.groupby(keys + ["category"]).size().unstack(fill_value=0)
    for c in CATEGORIES:
        if c not in g.columns:
            g[c] = 0
    g["shared"] = g["Nto1"] + g["NtoM"]
    excl = [c for c in CATEGORIES if c != "shared"]
    tot = g[excl].sum(axis=1)
    out = pd.DataFrame({"n_total": tot})
    for c in CATEGORIES:
        out[f"n_{c}"] = g[c]
        out[f"pct_{c}"] = (g[c] / tot.clip(lower=1)).round(4)
    return out.reset_index()


def main() -> int:
    ap = argparse.ArgumentParser(description="任务2：对象级 correspondence 统计")
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=C.ROOT / "results" / "phase2" / "object_stats")
    ap.add_argument("--circuits", type=str, default="")
    ap.add_argument("--ckpt-dir", type=Path, action="append", default=[],
                    help="可多次；给了就额外算各类别下的逐节点 drift（需 best_model_*.pt）")
    ap.add_argument("--ckpt-glob", type=str, default="best_model_ALL.pt")
    ap.add_argument("--amp", action="store_true")
    args = ap.parse_args()

    work = args.work_dir.resolve()
    pt_dir = work / "data" / "processed"
    idx = build_name_index(work)
    map_dir = work / "mappings"
    keep = tuple(c.strip() for c in args.circuits.split(",") if c.strip())

    rows_all, summ = [], []
    for f in sorted(map_dir.glob("*.json")):
        view = f.stem
        info = C.parse_view(view)
        if keep and info.stem not in keep:
            continue
        md = json.loads(f.read_text(encoding="utf-8"))
        orig_names = idx["orig"].get(info.stem, {})
        trans_names = idx["trans"].get(view, {})
        if not trans_names:
            continue
        rows, agg = analyse_view(view, md, orig_names, trans_names)
        rows_all += rows
        trojan = [r for r in rows if r["is_trojan"] == 1]
        summ.append({
            "view": view, "circuit": info.circuit, "stem": info.stem,
            "operators": info.operators, "depth": info.depth, "seed": info.seed,
            "n_orig_objects": agg["n_orig_objects"], "n_trojan_objects": len(trojan),
            **{f"n_{c}": agg[c] for c in CATEGORIES},
            **{f"trojan_{c}": sum(1 for r in trojan if r["category"] == c)
               for c in CATEGORIES if c != "shared"},
            "n_shared_trans_objects": agg["shared_trans_objects"],
        })

    C.ensure_dir(args.out_dir)
    df_obj = pd.DataFrame(rows_all)
    df = pd.DataFrame(summ)
    tag = work.name
    df_obj.to_csv(args.out_dir / f"{tag}_object_rows.csv", index=False, encoding="utf-8-sig")
    df.to_csv(args.out_dir / f"{tag}_per_view.csv", index=False, encoding="utf-8-sig")

    s_all = _share(df_obj, False); s_all["scope"] = "ALL_OBJECTS"
    s_tro = _share(df_obj, True); s_tro["scope"] = "TROJAN_ONLY"
    summary = pd.concat([s_all, s_tro], ignore_index=True)
    summary.to_csv(args.out_dir / f"{tag}_summary.csv", index=False, encoding="utf-8-sig")

    # 细分：按 (circuit, depth) 与 (circuit, operators) —— 回答「在哪些 split/merge 情况下」
    by_depth = _share(df_obj, True, keys=("circuit", "depth"))
    by_depth["scope"] = "TROJAN_ONLY"
    by_op = _share(df_obj, True, keys=("circuit", "operators"))
    by_op["scope"] = "TROJAN_ONLY"
    detail = pd.concat([by_depth, by_op], ignore_index=True)
    detail.to_csv(args.out_dir / f"{tag}_trojan_by_depth_operator.csv", index=False,
                  encoding="utf-8-sig")

    print(f"\n=== 对象统计（{tag}）===  视图 {len(df)}｜orig 对象行 {len(df_obj)}")
    print("\n[全体对象] 类别计数与占比（按电路）")
    print(summary[summary.scope == "ALL_OBJECTS"].to_string(index=False))
    print("\n[Trojan 对象] 类别计数与占比（按电路）")
    print(summary[summary.scope == "TROJAN_ONLY"].to_string(index=False))
    print(f"\n[导出] {args.out_dir / f'{tag}_summary.csv'}")

    if args.ckpt_dir:
        drift = drift_by_category(work, pt_dir, args.ckpt_dir, args.ckpt_glob, df_obj, idx, args)
        if not drift.empty:
            drift.to_csv(args.out_dir / f"{tag}_drift_by_category.csv", index=False,
                         encoding="utf-8-sig")
            print(f"\n[导出] drift by category -> {args.out_dir / f'{tag}_drift_by_category.csv'}")
            print(drift.to_string(index=False))
    return 0


def drift_by_category(work: Path, pt_dir: Path, ckpt_dir: Path, ckpt_glob: str,
                      df_obj: pd.DataFrame, idx: dict, args) -> pd.DataFrame:
    """对每个 orig 对象，用 (o_idx, t_idx) 配对算 |p_t − p_o|，再按对象类别聚合。"""
    import torch
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    dirs = ckpt_dir if isinstance(ckpt_dir, (list, tuple)) else [ckpt_dir]
    cks = [p for d in dirs for p in sorted(Path(d).glob(ckpt_glob))]
    if not cks:
        print(f"[WARN] 在 {dirs} 里找不到 {ckpt_glob}")
        return pd.DataFrame()
    orig, trans, _meta = C.load_fold(pt_dir)
    for d in (orig, trans):
        d.x = d.x.to(device); d.edge_index = d.edge_index.to(device); d.y = d.y.to(device)
    map_dir = work / "mappings"

    out = []
    for ck in cks:
        model, blob = C.load_ckpt(ck, device)
        thr = float(blob["threshold"])
        with C.Embedder(model) as emb:
            _, lo = emb.forward(orig.x, orig.edge_index, amp=args.amp)
            _, lt = emb.forward(trans.x, trans.edge_index, amp=args.amp)
        po = torch.softmax(lo, 1)[:, 1].cpu().numpy()
        pt = torch.softmax(lt, 1)[:, 1].cpu().numpy()
        for f in sorted(map_dir.glob("*.json")):
            view = f.stem
            info = C.parse_view(view)
            orig_names = idx["orig"].get(info.stem, {})
            trans_names = idx["trans"].get(view, {})
            if not trans_names:
                continue
            md = json.loads(f.read_text(encoding="utf-8"))
            sub = df_obj[df_obj["view"] == view]
            cat_of = dict(zip(sub["orig_obj"], sub["category"]))
            tset = set(trans_names)
            L = {}
            for o_name, tn in (md.get("node_alignment", {}) or {}).items():
                o = clean(o_name)
                if o in orig_names:
                    L[o] = [clean(t) for t in (tn or []) if clean(t) in tset]
            for o in orig_names:
                if o not in L and o in tset:
                    L[o] = [o]
            for o, tt in L.items():
                if not tt:
                    continue
                oi = orig_names[o]
                for t in tt:
                    ti = trans_names[t]
                    out.append({"ckpt": ck.parent.name, "view": view, "circuit": info.circuit,
                                "depth": info.depth, "orig_obj": o,
                                "is_trojan": int(is_trojan_name(o)),
                                "category": cat_of.get(o, "NA"),
                                "abs_drift": float(abs(pt[ti] - po[oi])),
                                "flip": int((po[oi] >= thr) != (pt[ti] >= thr))})
    d = pd.DataFrame(out)
    if d.empty:
        return d
    g = d.groupby(["ckpt", "category"]).agg(
        n_pairs=("abs_drift", "size"), mean_abs_drift=("abs_drift", "mean"),
        mean_flip=("flip", "mean")).reset_index()
    gt = d[d.is_trojan == 1].groupby(["ckpt", "category"]).agg(
        n_trojan_pairs=("abs_drift", "size"),
        trojan_mean_abs_drift=("abs_drift", "mean")).reset_index()
    return g.merge(gt, on=["ckpt", "category"], how="left").round(4)


if __name__ == "__main__":
    raise SystemExit(main())
