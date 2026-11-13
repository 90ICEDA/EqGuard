#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
negative_control.py — 负对照 + 旧数据复核的 CEC 记录器

两类检查（都用与 cec/matrix_cec.py 相同的 state-boundary CEC 配方）：

  1) neg_mutant   ：<vali>/trans/*tr<seed>u<N>.v（TrojanSAINT-main/non_equiv_mutate.py 造的非等价变异体）
                    vs <vali>/orig/<stem>.v            → 期望 FAIL（证明 CEC 不会假 PASS）
  2) legacy_equiv ：<graph-root>/data/verilog_data/trans/*.v（旧 pipeline 生成的训练视图）
                    vs <graph-root>/orig/<stem>.v       → 期望 PASS（证明现有训练数据等价）

输出：<out>（逐对一行，含未证明的比较点网名）+ <log-dir>/*.log（默认 ~/cec_logs/negctl）

用法：
  python3 negative_control.py --vali-dir /path/to/vali --graph-root /path/to/GIN_train/generate_trans \
      --out matrix/cec/negative_control_results.csv --jobs 4
"""

import argparse
import csv
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matrix_cec import read_module_name  # noqa: E402

STEM_RE = re.compile(r"^(?P<stem>.+?)tr\d+u?\d*$")
RE_EQUIV_FOUND = re.compile(r"Found (\d+) \$equiv cells")
RE_STATUS = re.compile(r"Of those cells (\d+) are proven and (\d+) are unproven")
RE_PROVEN_OK = re.compile(r"Equivalence successfully proven")
RE_UNPROVEN = re.compile(r"Unproven \$equiv [^:]+:\s+\\?(\S+)\s+\\?(\S+)")

FIELDS = ["pair_id", "kind", "golden", "candidate", "golden_module", "candidate_module",
          "status", "total_equiv", "proven", "unproven", "unproven_points",
          "runtime_sec", "log_path", "note"]


def stem_of(name: str) -> Optional[str]:
    m = STEM_RE.match(name)
    return m.group("stem") if m else None


def collect_pairs(vali_dir: Path, legacy_trans_dir: Optional[Path],
                  legacy_orig_dir: Optional[Path]) -> List[Dict[str, str]]:
    pairs: List[Dict[str, str]] = []
    for cand in sorted((vali_dir / "trans").glob("*tr*u*.v")):
        stem = stem_of(cand.stem)
        g = vali_dir / "orig" / f"{stem}.v" if stem else None
        if g and g.exists():
            pairs.append({"pair_id": f"neg_{cand.stem}", "kind": "neg_mutant",
                          "golden": str(g), "candidate": str(cand)})
    if legacy_trans_dir and legacy_orig_dir:
        for cand in sorted(legacy_trans_dir.glob("*.v")):
            stem = stem_of(cand.stem)
            g = legacy_orig_dir / f"{stem}.v" if stem else None
            if g and g.exists():
                pairs.append({"pair_id": f"legacy_{cand.stem}", "kind": "legacy_equiv",
                              "golden": str(g), "candidate": str(cand)})
    return pairs


def run_pair(pair: Dict[str, str], *, vali_dir: Path, log_dir: Path,
             timeout: int) -> Dict[str, object]:
    t0 = time.time()
    golden = Path(pair["golden"])
    candidate = Path(pair["candidate"])
    gm = read_module_name(golden)
    cm = read_module_name(candidate)
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"{pair['pair_id']}.log"

    row: Dict[str, object] = {k: "" for k in FIELDS}
    row.update({"pair_id": pair["pair_id"], "kind": pair["kind"],
                "golden": golden.name, "candidate": candidate.name,
                "golden_module": gm, "candidate_module": cm,
                "unproven_points": "", "log_path": str(log)})

    cmd = ["yosys", "-q",
           "-p", f"read_verilog -sv {vali_dir / 'verilog_lib.v'}",
           "-p", f"read_verilog -sv {golden}",
           "-p", f"read_verilog -sv {candidate}",
           "-p", f"equiv_make {gm} {cm} miter",
           "-p", "hierarchy -top miter",
           "-p", "proc", "-p", "flatten", "-p", "opt",
           "-p", f"techmap -map {vali_dir / 'sdff_formal_map.v'} -autoproc",
           "-p", "clk2fflogic", "-p", "opt",
           "-p", "equiv_simple", "-p", "equiv_induct",
           "-p", "equiv_status -assert",
           "-l", str(log)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        row.update({"status": "TIMEOUT", "runtime_sec": round(time.time() - t0, 2),
                    "note": f">{timeout}s"})
        return row
    except FileNotFoundError:
        row.update({"status": "NO_YOSYS", "note": "请在 Linux/WSL 里运行"})
        return row

    text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    found = RE_EQUIV_FOUND.findall(text)
    st = RE_STATUS.findall(text)
    row["total_equiv"] = int(found[-1]) if found else ""
    if st:
        row["proven"], row["unproven"] = int(st[-1][0]), int(st[-1][1])
    pts = sorted({f"{a} vs {b}" for a, b in RE_UNPROVEN.findall(text)})
    row["unproven_points"] = "; ".join(pts[:6])
    ok = bool(RE_PROVEN_OK.search(text)) and rc == 0
    row["status"] = "PASS" if ok else "FAIL"
    row["runtime_sec"] = round(time.time() - t0, 2)
    row["note"] = "" if ok else (pts[0] if pts else f"rc={rc}")
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description="负对照/旧数据 CEC 记录器")
    ap.add_argument("--vali-dir", type=Path, required=True,
                    help="含 trans/*tr*u*.v 与 orig/ 的 vali 目录（负对照来自这里）")
    ap.add_argument("--legacy-trans-dir", type=Path, default=None,
                    help="旧 pipeline 生成的训练视图目录（如 data/verilog_data/trans）")
    ap.add_argument("--legacy-orig-dir", type=Path, default=None,
                    help="旧训练视图对应的 orig 目录（如 generate_trans/orig）")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--log-dir", type=Path, default=Path.home() / "cec_logs" / "negctl")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    pairs = collect_pairs(args.vali_dir.resolve(),
                          args.legacy_trans_dir.resolve() if args.legacy_trans_dir else None,
                          args.legacy_orig_dir.resolve() if args.legacy_orig_dir else None)
    if args.limit:
        pairs = pairs[:args.limit]
    print(f"[INFO] 待检查 {len(pairs)} 对："
          f"{sum(1 for p in pairs if p['kind'] == 'neg_mutant')} 负对照 / "
          f"{sum(1 for p in pairs if p['kind'] == 'legacy_equiv')} 旧训练视图")

    rows: List[Dict[str, object]] = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
        futs = {ex.submit(run_pair, p, vali_dir=args.vali_dir.resolve(),
                          log_dir=args.log_dir.expanduser().resolve(),
                          timeout=args.timeout): p for p in pairs}
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            rows.append(r)
            print(f"[{i}/{len(futs)}] {r['pair_id']}: {r['status']} "
                  f"proven={r.get('proven', '')} unproven={r.get('unproven', '')} "
                  f"{r.get('runtime_sec', '')}s  {str(r.get('unproven_points', ''))[:60]}")

    rows.sort(key=lambda r: (str(r["kind"]), str(r["pair_id"])))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    neg = [r for r in rows if r["kind"] == "neg_mutant"]
    leg = [r for r in rows if r["kind"] == "legacy_equiv"]
    neg_fail = sum(1 for r in neg if r["status"] == "FAIL")
    leg_pass = sum(1 for r in leg if r["status"] == "PASS")
    print(f"\n[RESULT] 负对照 FAIL {neg_fail}/{len(neg)}（期望全部 FAIL）；"
          f"旧训练视图 PASS {leg_pass}/{len(leg)}（期望全部 PASS）")
    print(f"[OK] {args.out}  用时 {time.time() - t0:.1f}s")
    ok = (neg_fail == len(neg)) and (leg_pass == len(leg))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())

