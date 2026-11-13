# -*- coding: utf-8 -*-
"""
make_a1_transform_stats.py —— **A1：统一整理各种等价变换的数据/标签统计**

任务书第一条要求：对 decomp3 / bubble / ys_rt / ys_opt / ys_id / ys_abc / ys_aig / ys_nand
每种变换统计

    原始节点数、变换后节点数、原始木马节点数、成功映射的木马节点数、未知节点数、
    标签覆盖率、结构变化程度、CEC 结果

并且**特别分析 ys_aig 为什么只剩一个正节点**，同时把
「名字保留 / 真实逻辑对应 / 区域归属」三件事分开报告（不能只凭名字判断标签可靠）。

数据来源（全部只读，不产生新数据）：
  · fold 的 `views_meta.csv`      —— 视图清单（view / src_view / op / kind / inst_id）
  · fold 的 `data/processed/dataset_meta.json` 的 `per_view`
        → 每个视图在模型眼里的 `nodes`（节点数）与 `label1`（正节点数）
  · fold 的 `phase2_name_index.json` —— {orig: {view: {node_name: idx}}, trans: {...}}
        → 名字集合交集 = **名字保留率**；`Trojan*` 前缀名 = 原始木马节点名
  · `<hosts-root>/<host>/rw_mappings/<view>.json`
        → `node_alignment`（orig 名 → [trans 名]）与 `n_rewritten`
        → 「成功映射」与「未知节点」这两个量
  · `<hosts-root>/rw_cec_results.csv`（自写算子）与 `generate_trans/yslib*/cec*.csv`、
    `generate_trans/ys*/ys_manifest.csv`（yosys）→ CEC 结果

三个概念分开（任务书明确要求）：
  1) **名字保留**      name_survival = |orig 名字 ∩ trans 名字| / |orig 名字|
  2) **真实逻辑对应**  label_coverage = 变换后视图里的正节点数 / 原始木马节点数
                      （由 fold 的标签传输实际产生，比"名字"更接近真值）
  3) **区域归属**      region_available —— A1 不做（属于 A2：锚点 + 逻辑锥），此处恒为 False

用法：
    py phase2/ys/make_a1_transform_stats.py
    py phase2/ys/make_a1_transform_stats.py --fold-v1 generate_trans/folds/hosts_beta
输出：
    10.15/01_数据与标签/A1_变换统计/tables/a1_views.csv          逐视图
    10.15/01_数据与标签/A1_变换统计/tables/a1_by_op.csv         按变换聚合（v1/v2 对照）
    10.15/01_数据与标签/A1_变换统计/tables/a1_cec.csv           CEC 汇总
    10.15/01_数据与标签/A1_变换统计/tables/a1_aig_diagnosis.csv ys_aig 逐视图诊断
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
OUT_DEFAULT = ROOT / "10.15" / "01_数据与标签" / "A1_变换统计" / "tables"

ANON = re.compile(r"^(g__\d+__\d+|\\\w+|\$.+)$")     # yosys 内部匿名名
TROJAN_PREFIX = ("Trojan", "trojan")


def specs(fold_v1: Path) -> dict:
    """两套数据版本：v2（当前 fold，339 视图）/ v1（10.13 用的 317 视图）。"""
    G = ROOT / "generate_trans"
    return {
        "v2": {"fold": ROOT / "generate_trans/folds/hosts_beta2",
               "hosts": G / "hosts_bt2",
               "cec_rw": G / "hosts_bt2" / "rw_cec_results.csv",
               "cec_glob": "yslib2b_keep", "ys_glob": "yskeep2b"},
        "v1": {"fold": fold_v1, "hosts": G / "hosts_bt",
               "cec_rw": G / "hosts_bt" / "rw_cec_results.csv",
               "cec_glob": "yslib", "ys_glob": "yskeep"},
    }


def load_cec(cfg: dict) -> tuple[dict, dict]:
    """-> ({rw_view: status}, {rw_view: 来源})，PASS 优先于非 PASS。"""
    st, src = {}, {}
    p = Path(cfg["cec_rw"])
    if p.exists():
        d = pd.read_csv(p)
        for r in d.itertuples():
            st[str(r.rw_view)] = str(r.status)
            src[str(r.rw_view)] = p.name
    G = ROOT / "generate_trans"
    # CEC 记录散落在多个 root（yslib_test / yslib_keep* / yskeep* / yslib2b_keep），
    # 统一按 (stem, recipe) → rw_view 汇总，PASS 优先，并记来源文件名以便审计。
    for f in sorted(G.glob("ys*/cec*.csv")):
        d = pd.read_csv(f)
        cols = [c.lower() for c in d.columns]
        cec_col = next((c for c in d.columns if c.lower() == "cec"), None)
        if cec_col is None:
            continue
        for r in d.itertuples(index=False):
            rd = dict(zip(cols, [str(x) for x in r]))
            rv = f"{rd.get('stem','')}__ys_{rd.get('recipe','')}"
            v = rd.get("cec", "")
            s = "PASS" if "PASS" in v else ("FAIL" if "FAIL" in v.upper() else "?")
            if rv not in st or (st[rv] != "PASS" and s == "PASS"):
                st[rv], src[rv] = s, f.name
            src.setdefault(rv, f.name)
    for f in sorted(G.glob("ys*/ys_manifest.csv")):
        d = pd.read_csv(f)
        for r in d.itertuples():
            rv = f"{r.stem}__ys_{r.recipe}"
            v = str(r.cec).upper()
            s = "PASS" if "PASS" in v else ("FAIL" if "FAIL" in v else "?")
            if rv not in st or (st[rv] != "PASS" and s == "PASS"):
                st[rv], src[rv] = s, f.name
            src.setdefault(rv, f.name)
    return st, src


MATCH_OF = {"ctlmatcha": "injalpha", "ctlmatchb": "injbeta", "ctlmatchc": "injgamma",
            "ctlmatchd": "injdelta", "ctlmatche": "injepsilon", "ctlmatchf": "injzeta",
            "ctlmatchg": "injeta", "ctlmatchh": "injtheta",
            "ctlxor": "injalpha", "ctldup": "injalpha"}


def load_transport(cfg: dict) -> dict:
    """{view: [n_nodes, n_covered, n_pos]}。

    `label_transport.json` / `class_map_trans_transported.json` 的键是**全局 trans 节点索引**，
    `metadata_trans.json` 的 `file_ids` 给出节点→视图 → 才能按视图聚合。
    这就是「真实逻辑对应」的口径：标签是不是真的传到了这个视图上。
    """
    FT = Path(cfg["fold"]) / "data" / "for_train"
    p, m = FT / "class_map_trans_transported.json", FT / "metadata_trans.json"
    if not (p.exists() and m.exists()):
        return {}
    cm = json.loads(p.read_text(encoding="utf-8"))
    fid = json.loads(m.read_text(encoding="utf-8"))["file_ids"]
    out: dict = {}
    for i, v in enumerate(fid):
        a = out.setdefault(str(v), [0, 0, 0])
        a[0] += 1
        s = str(i)
        if s in cm:
            a[1] += 1
            if int(cm[s]) == 1:
                a[2] += 1
    return out


def is_gold_name(n: str) -> bool:
    return n.startswith(TROJAN_PREFIX)



def view_rows(cfg: dict, tag: str) -> tuple[list, dict]:
    F, H = Path(cfg["fold"]), Path(cfg["hosts"])
    meta = json.loads((F / "data" / "processed" / "dataset_meta.json").read_text(encoding="utf-8"))
    pv = meta["per_view"]
    ni = json.loads((F / "phase2_name_index.json").read_text(encoding="utf-8"))
    o_idx, t_idx = ni.get("orig", {}), ni.get("trans", {})
    cec, cec_src = load_cec(cfg)
    trans = load_transport(cfg)
    vm = pd.read_csv(F / "views_meta.csv")

    rows, info = [], {"gold_total": 0, "label1_total": 0, "n_missing_src": 0,
                      "nodes_mismatch": 0}
    for r in vm.itertuples():
        view, src, host, kind = str(r.view), str(r.src_view), str(r.host), str(r.kind)
        src_eff, src_note = src, "self"
        if src not in o_idx:      # 对照视图没有自己的基底 → 用「匹配木马基底」（与 fold 血缘一致）
            mi = MATCH_OF.get(src.split("__")[1].split("_")[0])
            cand = f"{host}__{mi}_d1_s42" if mi else ""
            if cand in o_idx:
                src_eff, src_note = cand, "matched_trojan_base"
            else:
                src_note = "missing"
        o_names, t_names = set(o_idx.get(src_eff, {}) or {}), set(t_idx.get(view, {}) or {})
        gold_names = {n for n in o_names if is_gold_name(n)} if kind == "trojan" else set()
        n_orig, n_trans, gold_pos = len(o_names), len(t_names), len(gold_names)
        tinfo = trans.get(view, [0, 0, 0])
        tr_cov, tr_pos = tinfo[1], tinfo[2]
        rec = pv.get(view) or {}
        if not o_names:
            info["n_missing_src"] += 1
        if rec.get("nodes") is not None and int(rec["nodes"]) != n_trans:
            info["nodes_mismatch"] += 1
        label1 = int(rec.get("label1", 0) or 0)
        info["gold_total"] += gold_pos
        info["label1_total"] += label1

        mp_file = H / host / "rw_mappings" / f"{view}.json"
        mp = json.loads(mp_file.read_text(encoding="utf-8")) if mp_file.exists() else None
        na = (mp or {}).get("node_alignment") or {}
        if isinstance(na, list):                      # register_into_fold 写的空列表
            na = {}
        tgt = {t for v in na.values() for t in (v if isinstance(v, list) else [v])}
        apos = {k for k in na if is_gold_name(k)}
        anon = sum(1 for t in tgt if ANON.match(str(t)))
        n_rew = int((mp or {}).get("n_rewritten", 0) or 0)
        n_inter = len(o_names & t_names)
        if not na:
            basis = "none"
        else:
            basis = "net_alias" if anon >= 0.5 * max(1, len(tgt)) else "inst_name"
        rows.append({
            "tag": tag, "host": host, "view": view, "src_view": src, "op": str(r.op),
            "kind": kind, "inst_id": str(r.inst_id),
            "src_effective": src_eff, "src_note": src_note,
            "n_orig_nodes": n_orig, "n_trans_nodes": n_trans,
            "transported_nodes": tr_cov, "transported_pos": tr_pos,
            "transported_cover": (tr_cov / n_trans) if n_trans else float("nan"),
            "gold_pos": gold_pos, "label1_trans": label1,
            "align_keys": len(na), "align_targets": len(tgt),
            "align_pos_keys": len(apos), "gold_names_in_trans": len(gold_names & t_names),
            "label_coverage": (label1 / gold_pos) if gold_pos else float("nan"),
            "unknown_nodes": (n_trans - len(tgt)) if na else float("nan"),
            "unknown_ratio": ((n_trans - len(tgt)) / n_trans) if (na and n_trans) else float("nan"),
            "name_survival": (n_inter / n_orig) if n_orig else float("nan"),
            "name_loss": (1 - n_inter / n_orig) if n_orig else float("nan"),
            "node_ratio": (n_trans / n_orig) if n_orig else float("nan"),
            "n_rewritten_per_node": (n_rew / n_trans) if n_trans else float("nan"),
            "anon_target_ratio": (anon / len(tgt)) if tgt else float("nan"),
            "mapping_basis": basis, "n_rewritten": n_rew,
            "cec": cec.get(view, "n/a" if not na else "?"), "cec_src": cec_src.get(view, ""),
            "region_available": False,       # 区域归属属于 A2
        })
    return rows, info


def agg(rows: list, tag: str) -> pd.DataFrame:
    d = pd.DataFrame(rows)
    out = []
    for op, g in d.groupby("op"):
        tr = g[g["kind"] == "trojan"]
        out.append({
            "tag": tag, "op": op, "n_views": len(g), "n_hosts": g["host"].nunique(),
            "n_trojan_views": len(tr), "n_control_views": int((g["kind"] == "control").sum()),
            "n_with_mapping": int(g["align_keys"].notna().sum()),
            "med_orig_nodes": g["n_orig_nodes"].median(),
            "med_trans_nodes": g["n_trans_nodes"].median(),
            "med_node_ratio": g["node_ratio"].median(),
            "med_name_survival": g["name_survival"].median(),
            "med_label_coverage": tr["label_coverage"].median(),
            "overall_label_coverage": (tr["label1_trans"].sum() / tr["gold_pos"].sum())
            if tr["gold_pos"].sum() else float("nan"),
            "med_transported_cover": g["transported_cover"].median(),
            "sum_transported_pos": int(g["transported_pos"].sum()),
            "n_views_with_pos": int((g["transported_pos"] > 0).sum()),
            "sum_gold_pos": int(g["gold_pos"].sum()),
            "sum_label1_trans": int(g["label1_trans"].sum()),
            "n_views_label1_le1": int((g["label1_trans"] <= 1).sum()),
            "med_align_keys": g["align_keys"].median() if g["align_keys"].notna().any() else float("nan"),
            "med_align_targets": g["align_targets"].median() if g["align_targets"].notna().any() else float("nan"),
            "med_align_pos_keys": tr["align_pos_keys"].median() if len(tr) else float("nan"),
            "med_unknown_ratio": g["unknown_ratio"].median(),
            "med_rewritten_per_node": g["n_rewritten_per_node"].median(),
            "basis_mode": Counter(g["mapping_basis"]).most_common(1)[0][0],
            "cec_pass": int((g["cec"] == "PASS").sum()),
            "cec_fail": int((g["cec"] == "FAIL").sum()),
            "cec_unknown": int((~g["cec"].isin(["PASS", "FAIL"])).sum()),
        })
    return pd.DataFrame(out).sort_values(["tag", "op"])


def aig_diag(rows: list) -> pd.DataFrame:
    d = pd.DataFrame(rows)
    d = d[d["op"] == "ys_aig"].copy()
    if d.empty:
        return d

    def verdict(r):
        if r["gold_pos"] == 0:
            return "非木马视图（无金标准正节点）"
        if r["label1_trans"] >= r["gold_pos"]:
            return "标签完整"
        if r["label1_trans"] == 0:
            return "标签全丢"
        return (f"只保住 {int(r['label1_trans'])}/{int(r['gold_pos'])} 个正节点"
                f"（名字存活 {int(r['gold_names_in_trans'])}，对齐锚点 {int(r['align_keys'])}，"
                f"标签传输覆盖 {100 * r['transported_cover']:.1f}%）")

    d["verdict"] = d.apply(verdict, axis=1)
    cols = ["tag", "host", "inst_id", "op", "view", "gold_pos", "label1_trans", "label_coverage",
            "transported_pos", "transported_cover", "gold_names_in_trans", "align_keys",
            "align_targets", "align_pos_keys", "anon_target_ratio", "n_orig_nodes",
            "n_trans_nodes", "node_ratio", "name_survival", "n_rewritten", "n_rewritten_per_node",
            "mapping_basis", "cec", "verdict"]
    return d[cols].sort_values(["tag", "host", "inst_id"])


def main() -> int:
    ap = argparse.ArgumentParser(description="A1：等价变换的数据/标签/CEC 统一统计")
    ap.add_argument("--fold-v1", type=Path, default=ROOT / "generate_trans/folds/hosts_beta")
    ap.add_argument("--out-dir", type=Path, default=OUT_DEFAULT)
    a = ap.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    for tag, cfg in specs(a.fold_v1).items():
        if not Path(cfg["fold"]).exists() or not Path(cfg["hosts"]).exists():
            print(f"[WARN] {tag} 数据缺：{cfg['fold']} / {cfg['hosts']}")
            continue
        rows, info = view_rows(cfg, tag)
        all_rows += rows
        print(f"\n=== {tag}：{len(rows)} 个视图 | 金标准正节点合计 {info['gold_total']}，"
              f"变换后正节点合计 {info['label1_total']}，缺 src 名字索引 {info['n_missing_src']}，"
              f"节点数与 per_view 不一致 {info['nodes_mismatch']}")

    t = pd.concat([agg([r for r in all_rows if r["tag"] == tg], tg)
                   for tg in sorted({r["tag"] for r in all_rows})], ignore_index=True)
    d = pd.DataFrame(all_rows)
    d.to_csv(a.out_dir / "a1_views.csv", index=False, encoding="utf-8-sig")
    t.to_csv(a.out_dir / "a1_by_op.csv", index=False, encoding="utf-8-sig")
    t.pivot_table(index="op", columns="tag", values=["n_views", "cec_pass", "cec_fail"],
                  aggfunc="sum", fill_value=0).to_csv(a.out_dir / "a1_cec.csv", encoding="utf-8-sig")
    di = aig_diag(all_rows)
    di.to_csv(a.out_dir / "a1_aig_diagnosis.csv", index=False, encoding="utf-8-sig")

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)
    show = t[["tag", "op", "n_views", "med_orig_nodes", "med_trans_nodes", "med_node_ratio",
              "med_name_survival", "med_label_coverage", "sum_gold_pos", "sum_label1_trans",
              "overall_label_coverage", "n_views_label1_le1", "cec_pass", "cec_fail", "cec_unknown"]]
    print("\n=== 按变换聚合（v1 / v2）===")
    print(show.round(4).to_string(index=False))

    lab = t[["tag", "op", "n_views", "n_trojan_views", "med_transported_cover",
             "n_views_with_pos", "sum_transported_pos", "sum_gold_pos",
             "med_label_coverage", "n_views_label1_le1", "med_align_pos_keys"]]
    lab.to_csv(a.out_dir / "a1_labeling.csv", index=False, encoding="utf-8-sig")
    print("\n=== 标签传输覆盖率（真实逻辑对应口径；A1 核心量）===")
    print(lab.round(4).to_string(index=False))
    if not di.empty:
        print("\n=== ys_aig 诊断（逐视图，前 24 行）===")
        print(di[["host", "inst_id", "gold_pos", "label1_trans", "transported_cover",
                  "gold_names_in_trans", "align_keys", "n_trans_nodes", "n_rewritten", "verdict"]]
              .head(24).to_string(index=False))
    print(f"\n[导出] {a.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

