#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
matrix_cec.py — 对 transformation matrix 的每个视图做 state-boundary CEC（yosys）

每个视图的证明流程（共享 current state + PI，比较全部 PO 与 next-state D）：

    read_verilog -sv <verilog_lib.v>            # 带功能实现的单元库
    read_verilog -sv <golden.v>                 # 原始网表
    read_verilog -sv <candidate.v>              # 视图网表
    equiv_make <golden_mod> <cand_mod> miter    # 共享 PI / 共享内部状态
    hierarchy -top miter
    proc; flatten; opt
    [--emit-json] write_json miter.json         # 导出比较点做分类
    techmap -map sdff_formal_map.v -autoproc    # 让 yosys 识别 SDFF 的 D/Q
    clk2fflogic
    opt
    equiv_simple                                # 结构等价
    equiv_induct                                # 归纳证明（含共享状态）
    equiv_status -assert                        # 未全部证明则非零退出

比较点分类（思路移植自 vali/classify_comparison_points.py）：
    OUTPUT_CHECK / NEXT_STATE_CHECK / SHARE_STATE_CHECK / INTERNAL_CHECK / MERGE_CONSTRAINT

用法（Linux / WSL）：
    python3 matrix_cec.py --matrix-root matrix --orig-dir orig \
        --vali-dir /path/to/vali --jobs 4 --out matrix/cec
    # 断点续跑 --resume ；只跑部分 --view-regex 'decomp_d1' --limit 5
    # 额外导出比较点分类 --emit-json-regex '_d1_'
"""

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

RESULT_FIELDS = [
    "view_name", "circuit", "chain_key", "composition_depth",
    "edit_count", "gate_expansion", "depth_change",
    "golden_module", "candidate_module",
    "status", "proven", "unproven", "total_equiv", "equivalence_proven",
    "runtime_sec", "exit_code",
    "out_check", "next_state_check", "share_state_check", "internal_check", "merge_constraint",
    "log_path", "json_path", "note",
]

MODULE_RE = re.compile(r"^\s*module\s+([A-Za-z_][\w$]*)\s*[\(;]", re.M)
RE_EQUIV_FOUND = re.compile(r"Found (\d+) \$equiv cells")
RE_STATUS = re.compile(r"Of those cells (\d+) are proven and (\d+) are unproven")
RE_PROVEN_OK = re.compile(r"Equivalence successfully proven")
RE_ASSERT_FAIL = re.compile(r"ERROR: Found (\d+) unproven")
DFF_PREFIXES = ("$dff", "$sdff", "$adff", "$dffsr", "$ff", "$ffsr", "$dlatch", "$sr")
FF_CELL_HINTS = ("DFF", "SDFF", "LATCH")


def is_ff_cell(cell_type: str) -> bool:
    """触发器判定：yosys 内部 FF 单元，或尚未 techmap 的设计单元（SDFFSRX1_RS 等）。"""
    t = str(cell_type)
    if t.startswith(DFF_PREFIXES):
        return True
    return any(h in t.upper() for h in FF_CELL_HINTS)


def log(msg: str) -> None:
    print(msg, flush=True)


def read_module_name(path: Path) -> Optional[str]:
    """取网表里第一个 module 名（生成器与 orig 都是单 module 文件）。"""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = MODULE_RE.search(text)
    return m.group(1) if m else None


def build_ys_script(*, lib: Path, golden: Path, candidate: Path,
                    golden_mod: str, cand_mod: str, sdff_map: Path,
                    emit_json: Optional[Path], json_stage: str = "post") -> str:
    """
    json_stage:
      post（默认）在 techmap + clk2fflogic 之后导出 miter.json
        → 此时触发器已是 yosys 内部 FF 单元，能正确识别 D/Q 端点（PO / next-state / shared-state 分类）
      pre  在 flatten/opt 之后导出（旧 vali config.sby 的位置，分类会退化）
    """
    lines = [
        f"read_verilog -sv {lib}",
        f"read_verilog -sv {golden}",
        f"read_verilog -sv {candidate}",
        f"equiv_make {golden_mod} {cand_mod} miter",
        "hierarchy -top miter",
        "proc",
        "flatten",
        "opt",
    ]
    if emit_json is not None and json_stage == "pre":
        lines.append(f"write_json {emit_json}")
    lines.append(f"techmap -map {sdff_map} -autoproc")
    lines.append("clk2fflogic")
    lines.append("opt")
    if emit_json is not None and json_stage == "post":
        lines.append(f"write_json {emit_json}")
    lines += [
        "equiv_simple",
        "equiv_induct",
        "equiv_status -assert",
    ]
    return "\n".join(lines) + "\n"


def _bits(x) -> List[str]:
    if x is None:
        return []
    if not isinstance(x, (list, tuple)):
        x = [x]
    return [str(b) for b in x]


def classify_miter(json_path: Path) -> Dict[str, int]:
    """
    把 miter.json 里的 $equiv/$eqx 按端点角色分类：
      SHARE_STATE_CHECK  A/B 位是触发器输出（Q/Q_N）
      NEXT_STATE_CHECK   A/B 位被触发器数据端（D/D_N）消费，或本身即 D 位
      OUTPUT_CHECK       A/B 位是 miter 输出端口位
      INTERNAL_CHECK     其余
      MERGE_CONSTRAINT   A == B（同线合并约束，等价性证明自动满足）
    注意：equiv_make 的比较点接在它自己生成的内部副本线上，因此除"直接命中"外
    还需要看 A/B 位被哪些单元消费（consumer-based）才能判出 next-state / shared-state。
    """
    try:
        data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    miter = None
    for _, mod in data.get("modules", {}).items():
        if "top" in mod.get("attributes", {}):
            miter = mod
            break
    if miter is None:
        for name, mod in data.get("modules", {}).items():
            if "miter" in name.lower():
                miter = mod
                break
    if miter is None:
        return {}

    out_bits = set()
    for _, pi in miter.get("ports", {}).items():
        if pi.get("direction") == "output":
            out_bits.update(_bits(pi.get("bits")))

    consumers: Dict[str, List[str]] = {}
    dff_q, dff_d = set(), set()
    for _, c in miter.get("cells", {}).items():
        ct = str(c.get("type", ""))
        for port, b in c.get("connections", {}).items():
            for bit in _bits(b):
                consumers.setdefault(bit, []).append(f"{ct}.{port}")
        if is_ff_cell(ct):
            for port, b in c.get("connections", {}).items():
                if port in ("D", "D_N"):
                    dff_d.update(_bits(b))
                elif port in ("Q", "Q_N", "QN"):
                    dff_q.update(_bits(b))

    cats: Counter = Counter()
    for _, c in miter.get("cells", {}).items():
        if c.get("type") not in ("$equiv", "$eqx"):
            continue
        a = _bits(c.get("connections", {}).get("A"))
        b = _bits(c.get("connections", {}).get("B"))
        if sorted(a) == sorted(b):
            cats["merge_constraint"] += 1
            continue
        s = set(a) | set(b)
        cons = [x for bit in s for x in consumers.get(bit, [])]
        if s & dff_q:
            cats["share_state_check"] += 1
        elif s & dff_d:
            cats["next_state_check"] += 1
        elif s & out_bits:
            cats["out_check"] += 1
        elif any((x.endswith(".D") or x.endswith(".D_N")) and is_ff_cell(x.split(".")[0]) for x in cons):
            cats["next_state_check"] += 1
        elif any(is_ff_cell(x.split(".")[0]) and (x.endswith(".Q") or x.endswith(".Q_N")) for x in cons):
            cats["share_state_check"] += 1
        else:
            cats["internal_check"] += 1
    return dict(cats)



# ------------------------------------------------------------
# 单视图 CEC
# ------------------------------------------------------------

def run_one(row: Dict[str, str], *, matrix_root: Path, orig_dir: Path, vali_dir: Path,
            cand_dir: Optional[Path] = None,
            out_dir: Path, timeout: int, emit_json: bool,
            log_dir: Optional[Path] = None, json_stage: str = "post") -> Dict[str, object]:
    t0 = time.time()
    view_file = str(row["view_file"])
    view_name = str(row["view_name"])
    src = str(row["src_verilog"])
    candidate = (cand_dir if cand_dir is not None else (matrix_root / "verilog")) / view_file
    golden = orig_dir / src
    lib = vali_dir / "verilog_lib.v"
    sdff_map = vali_dir / "sdff_formal_map.v"

    ydir = (Path(log_dir) if log_dir else (out_dir / "logs"))
    ydir.mkdir(parents=True, exist_ok=True)
    ylog = ydir / f"{view_name}.log"
    json_path: Optional[Path] = (out_dir / "miter_json" / f"{view_name}.json") if emit_json else None
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)

    res: Dict[str, object] = {k: "" for k in RESULT_FIELDS}
    for k in ("out_check", "next_state_check", "share_state_check", "internal_check", "merge_constraint"):
        res[k] = 0          # 分类计数默认 0，便于 CSV 里直接看
    res.update({
        "view_name": view_name,
        "circuit": row.get("circuit", ""),
        "chain_key": row.get("chain_key", ""),
        "composition_depth": row.get("composition_depth", ""),
        "edit_count": row.get("edit_count", ""),
        "gate_expansion": row.get("gate_expansion", ""),
        "depth_change": row.get("depth_change", ""),
        "log_path": str(ylog),
        "json_path": str(json_path) if json_path else "",
    })

    for p in (candidate, golden, lib, sdff_map):
        if not p.exists():
            res["status"] = "MISSING"
            res["note"] = f"缺少文件 {p}"
            res["runtime_sec"] = round(time.time() - t0, 3)
            return res

    golden_mod = read_module_name(golden)
    cand_mod = read_module_name(candidate)
    res["golden_module"], res["candidate_module"] = golden_mod, cand_mod
    if not golden_mod or not cand_mod:
        res["status"] = "ERROR"
        res["note"] = "无法解析 module 名"
        res["runtime_sec"] = round(time.time() - t0, 3)
        return res

    ys_path = ydir / f"{view_name}.ys"
    ys_path.write_text(build_ys_script(lib=lib, golden=golden, candidate=candidate,
                                       golden_mod=golden_mod, cand_mod=cand_mod,
                                       sdff_map=sdff_map, emit_json=json_path,
                                       json_stage=json_stage),
                       encoding="utf-8")
    cmd = ["yosys", "-q", "-s", str(ys_path), "-l", str(ylog)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        rc = -9
    except FileNotFoundError:
        res["status"] = "NO_YOSYS"
        res["note"] = "找不到 yosys（请在 Linux/WSL 里运行）"
        res["runtime_sec"] = round(time.time() - t0, 3)
        return res

    text = ylog.read_text(encoding="utf-8", errors="ignore") if ylog.exists() else ""
    res["exit_code"] = rc
    found = RE_EQUIV_FOUND.findall(text)
    status = RE_STATUS.findall(text)
    if found:
        res["total_equiv"] = int(found[-1])
    if status:
        res["proven"], res["unproven"] = int(status[-1][0]), int(status[-1][1])
    res["equivalence_proven"] = bool(RE_PROVEN_OK.search(text))
    failed = RE_ASSERT_FAIL.search(text)
    if rc == 0 and res["equivalence_proven"]:
        res["status"] = "PASS"
    elif rc == -9:
        res["status"] = "TIMEOUT"
        res["note"] = f">{timeout}s"
    else:
        res["status"] = "FAIL"
        res["note"] = failed.group(0) if failed else f"rc={rc}"

    if json_path is not None and json_path.exists():
        for k, v in classify_miter(json_path).items():
            res[k] = v

    res["runtime_sec"] = round(time.time() - t0, 3)
    return res


def write_results(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RESULT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (r.get(k) if r.get(k) is not None else "") for k in RESULT_FIELDS})


# ------------------------------------------------------------
# main
# ------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="matrix → yosys state-boundary CEC 批量驱动")
    ap.add_argument("--matrix-root", type=Path, default=Path("matrix"))
    ap.add_argument("--orig-dir", type=Path, default=Path("orig"))
    ap.add_argument("--cand-dir", type=Path, default=None,
                    help="????????? <matrix-root>/verilog?fold ??? trans?")
    ap.add_argument("--vali-dir", type=Path, required=True,
                    help="含 verilog_lib.v(带功能实现) 与 sdff_formal_map.v 的目录")
    ap.add_argument("--out", type=Path, default=Path("matrix/cec"))
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=900, help="单视图 yosys 超时（秒）")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 个视图（调试）")
    ap.add_argument("--view-regex", type=str, default="", help="只跑名字匹配该正则的视图")
    ap.add_argument("--views-list", type=Path, default=None,
                    help="只跑清单里的视图（每行一个 view_name，# 为注释）——避免命令行里的正则/引号问题")
    ap.add_argument("--emit-json", action="store_true",
                    help="为本次所有视图导出 miter.json 并分类比较点（PO / next-state D）")
    ap.add_argument("--emit-json-regex", type=str, default="",
                    help="仅对匹配该正则的视图导出 miter.json 并分类")
    ap.add_argument("--log-dir", type=Path, default=None,
                    help="yosys 原始日志目录（默认 <out>/logs；建议放持久目录，别用 /tmp）")
    ap.add_argument("--json-stage", choices=["post", "pre"], default="post",
                    help="miter.json 导出时机：post=techmap+clk2fflogic 之后（分类正确，默认）；pre=flatten 之后")
    ap.add_argument("--resume", action="store_true", help="跳过已跑出结论的视图")
    ap.add_argument("--force", action="store_true",
                    help="配合 --resume：重跑被选中的视图并用新结果覆盖旧行（其余行保留）")
    args = ap.parse_args()

    matrix_root = Path(args.matrix_root).resolve()
    manifest = matrix_root / "view_manifest.csv"
    if not manifest.exists():
        log(f"[ERROR] 找不到 {manifest}")
        return 1
    with open(manifest, "r", encoding="utf-8-sig", newline="") as f:
        manifest_rows = [dict(r) for r in csv.DictReader(f)]
    manifest_order = [str(r["view_name"]) for r in manifest_rows]
    rows = list(manifest_rows)

    if args.view_regex:
        pat = re.compile(args.view_regex)
        rows = [r for r in rows if pat.search(str(r["view_name"]))]
    if args.views_list:
        wanted = set()
        for line in Path(args.views_list).read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                wanted.add(s)
        rows = [r for r in rows if str(r["view_name"]) in wanted]
        missing = wanted - {str(r["view_name"]) for r in rows}
        if missing:
            log(f"[WARN] 清单里有 {len(missing)} 个视图不在 manifest 中（或已被 --view-regex 过滤）")

    out_dir = Path(args.out).resolve()
    result_path = out_dir / "cec_results.csv"
    results_by_name: Dict[str, Dict[str, object]] = {}
    if args.resume and result_path.exists():
        with open(result_path, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if str(r.get("status")) in ("PASS", "FAIL", "TIMEOUT", "ERROR", "MISSING"):
                    results_by_name[str(r.get("view_name"))] = dict(r)
        if args.force:
            log(f"[INFO] --resume --force: 保留 {len(results_by_name)} 条旧结果，重跑被选中的视图")
        else:
            rows = [r for r in rows if str(r["view_name"]) not in results_by_name]
            log(f"[INFO] --resume: 已有 {len(results_by_name)} 条结果，剩余 {len(rows)} 个视图")
    if args.limit:
        rows = rows[:args.limit]
    if not rows:
        log("[INFO] 没有需要跑的视图")
        return 0

    def snapshot() -> List[Dict[str, object]]:
        return [results_by_name[n] for n in manifest_order if n in results_by_name]

    json_pat = re.compile(args.emit_json_regex) if args.emit_json_regex else None
    log(f"[INFO] 待跑 {len(rows)} 个视图；jobs={args.jobs} timeout={args.timeout}s "
        f"json_stage={args.json_stage}；输出 {out_dir}")

    t0 = time.time()
    jobs = max(1, int(args.jobs))
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = {
            ex.submit(run_one, r,
                      matrix_root=matrix_root,
                      orig_dir=Path(args.orig_dir).resolve(),
                      vali_dir=Path(args.vali_dir).resolve(),
                      cand_dir=(Path(args.cand_dir).resolve() if args.cand_dir else None),
                      out_dir=out_dir, timeout=int(args.timeout),
                      log_dir=Path(args.log_dir).expanduser().resolve() if args.log_dir else None,
                      json_stage=str(args.json_stage),
                      emit_json=bool(args.emit_json
                                     or (json_pat and json_pat.search(str(r["view_name"]))))): r
            for r in rows
        }
        for i, fut in enumerate(as_completed(futs), 1):
            res = fut.result()
            results_by_name[str(res["view_name"])] = res
            write_results(result_path, snapshot())      # 增量落盘，可 --resume
            log(f"[{i}/{len(futs)}] {res['view_name']}: {res['status']} "
                f"proven={res.get('proven', '')} unproven={res.get('unproven', '')} "
                f"{res.get('runtime_sec', '')}s")

    results = snapshot()
    cnt = Counter(str(r.get("status")) for r in results)
    log(f"\n[DONE] 共 {len(results)} 条结果 {dict(cnt)}  用时 {time.time() - t0:.1f}s -> {result_path}")
    bad = cnt.get("FAIL", 0) + cnt.get("ERROR", 0) + cnt.get("TIMEOUT", 0) + cnt.get("MISSING", 0)
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())


