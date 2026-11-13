# -*- coding: utf-8 -*-
"""
make_manifest.py —— 为 10.5/ 打包目录生成文件清单（相对路径 / 字节数 / sha1）。

用法：
  python phase2/make_manifest.py --pkg-dir 10.5
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent
SKIP_EXT = {".pt", ".pyc"}


def sha1(p: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 10.5/ 的文件清单")
    ap.add_argument("--pkg-dir", type=Path, default=ROOT / "10.5")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    pkg = args.pkg_dir.resolve()
    out = args.out or (pkg / "manifest.csv")
    rows = []
    for p in sorted(pkg.rglob("*")):
        if not p.is_file() or p.name == out.name:
            continue
        if p.suffix.lower() in SKIP_EXT:
            continue
        rows.append((p.relative_to(pkg).as_posix(), p.stat().st_size, sha1(p)))
    lines = ["path,bytes,sha1"] + [f"{a},{b},{c}" for a, b, c in rows]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    total = sum(b for _, b, _ in rows)
    print(f"[OK] {len(rows)} 个文件 / {total/1024:.1f} KiB -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
