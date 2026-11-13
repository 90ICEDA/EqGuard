#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_log_index.py — 给 WSL 里的 CEC 原始日志建一个**索引 CSV**（不复制 1.5 GB 日志本身）

背景：真·等价性 CEC 的原始 yosys 日志留在 WSL `~/cec_logs`（约 1.5 GB，1200+ 文件），
      不随项目冻结。本脚本把「有哪些文件、多大」写成机器可读索引，放进项目内，便于审计与复现。

用法（在 WSL 里跑，路径用 /mnt/c/... 指回 Windows 项目）：
  wsl -d Ubuntu-22.04 python3 generate_trans/cec/build_log_index.py \
      /mnt/c/Users/91344/Desktop/GraphSAINT/GIN_train/generate_trans/matrix/cec/log_index.csv
"""

import csv
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CEC_LOG_DIR", Path.home() / "cec_logs"))


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "log_index.csv")
    if not ROOT.exists():
        print(f"[ERROR] 找不到 {ROOT}")
        return 1
    rows = []
    for dirpath, _dirs, files in os.walk(ROOT):
        for f in files:
            p = Path(dirpath) / f
            try:
                rows.append({"rel_path": str(p.relative_to(ROOT)).replace("\\", "/"),
                             "bytes": p.stat().st_size})
            except OSError:
                pass
    rows.sort(key=lambda r: r["rel_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["rel_path", "bytes"])
        w.writeheader()
        w.writerows(rows)
    tot = sum(r["bytes"] for r in rows)
    print(f"[OK] {len(rows)} 个文件 / {tot / 2**30:.2f} GB -> {out}")
    by_ext = {}
    for r in rows:
        ext = os.path.splitext(r["rel_path"])[1] or "(no-ext)"
        e = by_ext.setdefault(ext, [0, 0])
        e[0] += 1
        e[1] += r["bytes"]
    for ext, (c, b) in sorted(by_ext.items(), key=lambda kv: -kv[1][1])[:6]:
        print(f"     {ext:<8} {c:>5} 个 / {b / 2**20:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
