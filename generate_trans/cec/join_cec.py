#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
join_cec.py — 把 CEC 结果并回 transformation matrix，并出 CEC 汇总

输入：
    matrix/view_manifest.csv            （冻结的 matrix manifest，不改动）
    matrix/cec/cec_results.csv          （matrix_cec.py 的产出）
输出：
    matrix/view_manifest_cec.csv        （manifest + cec_* 列，任务9 的"CEC PASS"就取这一列）
    matrix/cec/cec_summary.csv          （按 chain × depth 汇总：通过率、比较点分类合计、耗时）
用法：
    python3 join_cec.py --matrix-root matrix [--cec matrix/cec/cec_results.csv]
退出码：0=所有视图 PASS；2=存在非 PASS
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

CEC_COLS = ["status", "proven", "unproven", "total_equiv", "equivalence_proven", "runtime_sec",
            "out_check", "next_state_check", "share_state_check", "internal_check", "merge_constraint",
            "log_path", "note"]


def read_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fields: List[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description="把 CEC 结果并回 matrix manifest 并汇总")
    ap.add_argument("--matrix-root", type=Path, default=Path("matrix"))
    ap.add_argument("--cec", type=Path, default=None, help="默认 <matrix-root>/cec/cec_results.csv")
    args = ap.parse_args()

    root = Path(args.matrix_root)
    manifest = read_csv(root / "view_manifest.csv")
    cec_path = args.cec or (root / "cec" / "cec_results.csv")
    cec = {str(r["view_name"]): r for r in read_csv(cec_path)}
    print(f"[INFO] manifest={len(manifest)} 视图, cec_results={len(cec)} 条")

    joined: List[Dict[str, object]] = []
    missing = 0
    for m in manifest:
        row: Dict[str, object] = dict(m)
        c = cec.get(str(m["view_name"]))
        if c is None:
            missing += 1
            row["cec_status"] = "NOT_RUN"
            for k in CEC_COLS:
                row.setdefault(f"cec_{k}", "")
        else:
            row["cec_status"] = c.get("status", "")
            for k in CEC_COLS:
                v = c.get(k, "")
                if k in ("out_check", "next_state_check", "share_state_check", "internal_check", "merge_constraint"):
                    v = int(_num(v))
                row[f"cec_{k}"] = v
        joined.append(row)
    if missing:
        print(f"[WARN] {missing} 个视图还没有 CEC 结果（cec_status=NOT_RUN）")

    write_csv(root / "view_manifest_cec.csv", joined)

    # ---- 按 chain × depth 汇总 ----
    groups: Dict[tuple, List[Dict[str, object]]] = defaultdict(list)
    for r in joined:
        groups[(str(r["chain_key"]), int(r["composition_depth"]))].append(r)
    summary: List[Dict[str, object]] = []
    hard_fail = 0
    for (chain, dep), rs in sorted(groups.items()):
        n = len(rs)
        n_pass = sum(1 for r in rs if str(r["cec_status"]) == "PASS")
        hard_fail += n - n_pass
        summary.append({
            "chain_key": chain,
            "composition_depth": dep,
            "n_views": n,
            "n_pass": n_pass,
            "n_not_pass": n - n_pass,
            "pass_rate": round(n_pass / n, 4) if n else 0,
            "runtime_mean_s": round(sum(_num(r["cec_runtime_sec"]) for r in rs) / n, 3) if n else 0,
            "proven_sum": int(sum(_num(r["cec_proven"]) for r in rs)),
            "unproven_sum": int(sum(_num(r["cec_unproven"]) for r in rs)),
            "out_check_sum": int(sum(_num(r["cec_out_check"]) for r in rs)),
            "next_state_check_sum": int(sum(_num(r["cec_next_state_check"]) for r in rs)),
            "share_state_check_sum": int(sum(_num(r["cec_share_state_check"]) for r in rs)),
            "internal_check_sum": int(sum(_num(r["cec_internal_check"]) for r in rs)),
            "merge_constraint_sum": int(sum(_num(r["cec_merge_constraint"]) for r in rs)),
        })
    write_csv(root / "cec" / "cec_summary.csv", summary)

    n_pass = sum(1 for r in joined if str(r["cec_status"]) == "PASS")
    print(f"\n[RESULT] CEC PASS {n_pass}/{len(joined)}  (NOT_PASS={len(joined) - n_pass}, NOT_RUN={missing})")
    for s in summary[:12]:
        print(f"  {str(s['chain_key']):<28} d{s['composition_depth']}  "
              f"pass={s['n_pass']}/{s['n_views']}  proven={s['proven_sum']}  "
              f"PO={s['out_check_sum']} nextD={s['next_state_check_sum']}  "
              f"mean={s['runtime_mean_s']}s")
    print(f"[OK] {root / 'view_manifest_cec.csv'} / {root / 'cec' / 'cec_summary.csv'}")
    return 0 if (len(joined) - n_pass) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
