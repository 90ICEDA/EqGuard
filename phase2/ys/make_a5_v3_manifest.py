#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
make_a5_v3_manifest.py — A5 的 **fold v3 版**统一 manifest（一行 = 一个训练视图）。

与 A5 旧版（`tables/manifest.csv`，443 行，基于 v2 时代产物、fold 列指向
`10.13/group_fold_v2*`）的区别：
  · 只登记 **当前 fold v3**（`generate_trans/folds/hosts_bt3`）里真实存在的视图；
  · `fold_view` = 视图名；`fold_split` = train/val/test（来自 `views.json`，按 host 切分）；
  · CEC 取**统一驱动**结果 `cec/cec_results.csv`（不是抄 `cec_benign`）；
  · 注入字段取 `hosts_bt2|hosts_a4/<host>/provenance.json`；
  · `n_src_inst` / `n_conv_gates` 与 fold 构建同一套实例数口径。

用法：
    python phase2/ys/make_a5_v3_manifest.py [--coverage <a2 a2_coverage.csv>]
"""

import argparse
import csv
import json
import platform
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent.parent
FOLD_DEFAULT = ROOT / "generate_trans" / "folds" / "hosts_bt3"
OUT_DEFAULT = ROOT / "10.15" / "01_数据与标签" / "A5_统一manifest" / "tables"

SRC_ROOT_OF_BATCH = {
    "yslib_test": "hosts_bt2",
    "keepab": "hosts_bt2",
    "a4": "hosts_a4",
    "a4b": "hosts_a4",
}
KEEP_RE = re.compile(r"__(keep\w+?)(?:__|$)")
RECIPE_OF_OP = {
    "ys_id": "id", "ys_rt": "rt", "ys_opt": "opt", "ys_abc": "abc",
    "ys_aig": "aig", "ys_nand": "nand",
}


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def count_gates(path: Path, lib: dict) -> int:
    """实例数口径：与 fold 构建同一套（make_inst_alignment.src_facts），失败退回正则。"""
    try:
        import make_inst_alignment as MIA  # noqa: WPS433
        return len(MIA.src_facts(path, lib)["gates"])
    except Exception:
        pass
    txt = path.read_text(encoding="utf-8", errors="ignore")
    return len(re.findall(r"^\s+[A-Za-z_][\w$]*\s+[\\A-Za-z_][\w$.]*\s*\(", txt, re.M))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=Path, default=FOLD_DEFAULT)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--coverage", type=Path, default=None, help="可选的 A2 v3 覆盖率表")
    args = ap.parse_args()
    fold = args.fold

    with open(fold / "views_meta.csv", "r", encoding="utf-8-sig", newline="") as f:
        meta_rows = [dict(r) for r in csv.DictReader(f)]
    views_json = load_json(fold / "views.json")
    split_of = {}
    for k, tag in (("train_views", "train"), ("val_views", "val"), ("test_views", "test")):
        for v in views_json.get(k, []):
            split_of[str(v)] = tag

    cec = {}
    cec_csv = fold / "cec" / "cec_results.csv"
    if cec_csv.exists():
        with open(cec_csv, "r", encoding="utf-8-sig", newline="") as f:
            cec = {str(r["view_name"]): r for r in csv.DictReader(f)}

    prov = {}
    for r2 in ("hosts_bt2", "hosts_a4"):
        for pj in sorted((ROOT / "generate_trans" / r2).glob("*/provenance.json")):
            for rec in load_json(pj):
                prov[(r2, str(rec.get("view")))] = rec

    dm = load_json(fold / "data" / "processed" / "dataset_meta.json")
    per_view = dm.get("per_view", {})

    cov = {}
    if args.coverage and args.coverage.exists():
        with open(args.coverage, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                key = r.get("view") or r.get("rw_view") or r.get("fold_view") or ""
                if key:
                    cov[str(key)] = r

    try:
        import pandas as pd
        pandas_v = pd.__version__
    except Exception:
        pandas_v = ""

    lib = {}
    try:
        from phase2 import netlist_lib as NL  # noqa: WPS433
        lib = NL.load_library(ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v")
    except Exception:
        lib = {}
    out_rows = []
    for r in meta_rows:
        view = str(r["view"])
        host = str(r.get("host", ""))
        src_view = str(r.get("src_view", ""))
        batch = str(r.get("batch", ""))
        op = str(r.get("op", ""))
        src_root = SRC_ROOT_OF_BATCH.get(batch, "")
        rec = prov.get((src_root, src_view), {})
        c = cec.get(view, {})
        pv = per_view.get(view, {})
        cand = fold / "trans" / f"{view}.v"
        src = fold / "orig" / f"{src_view}.v"
        keep = KEEP_RE.search(view)
        cv = cov.get(view, {})
        stem = re.sub(r"__keep\w+$", "", view)
        stem = re.sub(r"__ys_[A-Za-z]+$", "", stem)
        out_rows.append({
            "sample_id": view,
            "status": c.get("status", "UNKNOWN"),
            "batch": batch,
            "src_root": src_root,
            "host": host,
            "src_view": src_view,
            "stem": stem,
            "src_netlist": str(src.relative_to(ROOT)) if src.exists() else "",
            "n_src_inst": count_gates(src, lib) if src.exists() else "",
            "conv_netlist": str(cand.relative_to(ROOT)) if cand.exists() else "",
            "n_conv_gates": count_gates(cand, lib) if cand.exists() else "",
            "recipe": RECIPE_OF_OP.get(op, op.replace("ys_", "")),
            "keep_scheme": keep.group(1) if keep else "",
            "kind": rec.get("kind", ""),
            "family": rec.get("a4_family") or rec.get("ctl_type") or "",
            "prefix": rec.get("prefix", ""),
            "n_trig": rec.get("n_trig", ""),
            "trig_style": rec.get("trig_style", ""),
            "payload_style": rec.get("payload_style", ""),
            "payload_len": rec.get("payload_len", ""),
            "payload_target": rec.get("payload_target", ""),
            "hijacked_output": rec.get("hijacked_output", ""),
            "n_new_gates": len(rec.get("new_gates") or []),
            "new_gates": ";".join(rec.get("new_gates") or []),
            "n_pos": pv.get("label1", ""),
            "n_unknown": cv.get("n_unknown", cv.get("unknown_total", "")),
            "cov_core": cv.get("cov_core", cv.get("cover_core", "")),
            "cov_region": cv.get("cov_region", cv.get("cover_region", "")),
            "cec_conv": c.get("status", "UNKNOWN"),
            "cec_proven": c.get("proven", ""),
            "cec_unproven": c.get("unproven", ""),
            "cec_benign": rec.get("cec_benign", ""),
            "label_usable": rec.get("label_usable", ""),
            "fold_view": view,
            "fold_split": split_of.get(view, ""),
            "fold_name": fold.name,
            "yosys": "0.51",
            "python": platform.python_version(),
            "pandas": pandas_v,
        })
    args.out.mkdir(parents=True, exist_ok=True)
    man = args.out / "manifest_v3.csv"
    with open(man, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)

    trojan = [r for r in out_rows if r["kind"] == "trojan"]
    checks = [
        ("views_total", len(out_rows), ""),
        ("fold_files_complete", sum(1 for r in out_rows if r["src_netlist"] and r["conv_netlist"]), ""),
        ("missing_injection_record", sum(1 for r in out_rows if not r["kind"]), ""),
        ("cec_not_pass", sum(1 for r in out_rows if r["cec_conv"] != "PASS"), ""),
        ("duplicate_sample_id", len(out_rows) - len({r["sample_id"] for r in out_rows}), ""),
        ("trojan_views", len(trojan), ""),
        ("trojan_views_without_pos", sum(1 for r in trojan if not str(r["n_pos"]).isdigit() or int(r["n_pos"]) == 0), "FLAG"),
    ]
    by_batch = Counter(r["batch"] for r in out_rows)
    by_split = Counter(r["fold_split"] for r in out_rows)
    rep = args.out / "a5_v3_trace_report.csv"
    with open(rep, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item", "value", "flag"])
        for k, v, flag in checks:
            w.writerow([k, v, flag])
        for k, v in sorted(by_batch.items()):
            w.writerow([f"batch:{k}", v, ""])
        for k, v in sorted(by_split.items()):
            w.writerow([f"split:{k}", v, ""])
        w.writerow(["n_pos_total", sum(int(r["n_pos"]) for r in out_rows if str(r["n_pos"]).isdigit()), ""])

    print(f"[OK] {man}  {len(out_rows)} rows x {len(out_rows[0])} cols")
    for k, v, flag in checks:
        print(f"  {k}: {v} {flag}")
    print(f"  batches: {dict(by_batch)}")
    print(f"  splits : {dict(by_split)}")
    print(f"[OK] {rep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
