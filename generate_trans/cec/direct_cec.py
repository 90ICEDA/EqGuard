#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
direct_cec.py — 对任意两个网表直接做 yosys state-boundary CEC（不经 sby，不依赖 shell 行尾）

流程与 cec/matrix_cec.py 完全一致：
  equiv_make（共享 PI + 共享内部状态）→ proc/flatten/opt → techmap($sdff) → clk2fflogic → opt
  → equiv_simple → equiv_induct → equiv_status -assert

用法：
  python3 direct_cec.py --golden orig/rs232t1000.v --candidate trans/rs232t1000tr42u38.v \
      --vali-dir /path/to/vali [--emit-json out.json]
退出码：0=全部比较点 proven；非 0=有 unproven/超时
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matrix_cec import classify_miter, read_module_name  # noqa: E402

RE_EQUIV_FOUND = __import__("re").compile(r"Found (\d+) \$equiv cells")
RE_STATUS = __import__("re").compile(r"Of those cells (\d+) are proven and (\d+) are unproven")
RE_PROVEN_OK = __import__("re").compile(r"Equivalence successfully proven")


def main() -> int:
    ap = argparse.ArgumentParser(description="两个网表的 yosys state-boundary CEC")
    ap.add_argument("--golden", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--vali-dir", type=Path, required=True,
                    help="含 verilog_lib.v(带功能实现) 与 sdff_formal_map.v 的目录")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--fast", action="store_true", help="fast CEC: setundef + equiv_simple -undef")
    ap.add_argument("--emit-json", type=Path, default=None, help="导出 miter.json 并分类比较点")
    ap.add_argument("--log", type=Path, default=None, help="yosys 日志路径")
    args = ap.parse_args()

    golden_mod = read_module_name(args.golden)
    cand_mod = read_module_name(args.candidate)
    print(f"[INFO] golden={args.golden.name}({golden_mod})  candidate={args.candidate.name}({cand_mod})")
    if not golden_mod or not cand_mod:
        print("[ERROR] 无法解析 module 名")
        return 1

    lib = args.vali_dir / "verilog_lib.v"
    sdff = args.vali_dir / "sdff_formal_map.v"
    log = args.log or (Path.cwd() / f"direct_cec_{cand_mod}.log")
    cmds = [
        f"read_verilog -sv {lib}",
        f"read_verilog -sv {args.golden}",
        f"read_verilog -sv {args.candidate}",
        f"equiv_make {golden_mod} {cand_mod} miter",
        "hierarchy -top miter",
        "proc", "flatten", "opt",
        f"techmap -map {sdff} -autoproc",
        "clk2fflogic", "opt",
    ]
    if args.emit_json is not None:
        cmds.append(f"write_json {args.emit_json}")
    if args.fast:
        cmds += ["setundef -zero -undriven", "setundef -anyseq", "equiv_simple -undef", "equiv_induct", "equiv_status -assert"]
    else:
        cmds += ["equiv_simple", "equiv_induct", "equiv_status -assert"]

    argv = ["yosys", "-q"]
    for c in cmds:
        argv += ["-p", c]
    argv += ["-l", str(log)]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=args.timeout)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] > {args.timeout}s")
        return 3
    except FileNotFoundError:
        print("[ERROR] 找不到 yosys（请在 Linux/WSL 里运行）")
        return 1

    text = log.read_text(encoding="utf-8", errors="ignore") if log.exists() else ""
    m_found = RE_EQUIV_FOUND.findall(text)
    m_status = RE_STATUS.findall(text)
    total = int(m_found[-1]) if m_found else None
    proven = unproven = None
    if m_status:
        proven, unproven = int(m_status[-1][0]), int(m_status[-1][1])
    ok = bool(RE_PROVEN_OK.search(text)) and rc == 0
    print(f"[CEC] rc={rc} total={total} proven={proven} unproven={unproven} "
          f"{'PASS' if ok else 'FAIL'}")
    if args.emit_json is not None and args.emit_json.exists():
        print(f"[分类] {classify_miter(args.emit_json)}")
    print(f"[log] {log}")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
