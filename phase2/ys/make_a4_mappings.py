"""make_a4_mappings.py —— 给 `_dev_a4` 的 120 个 A4 视图补 **`node_alignment` 映射** ✓。

为什么必须补 ✗→✓：`parser2` 的 orig↔trans 对齐**不靠名字** ✗，而是读
`mappings/<view>.json` 里的 `node_alignment` ✓（见 `parser2.build_alignment_from_mappings` ✓）。
A4 视图当年只产出了网表 ✓、**没产映射** ✗（`generate_trans/mappings` 里 0 个 a4 ✗）→ `alignment.json = []` ✗
→ `process_pt2` 崩 ✗ → 没法建 `.pt` ✗。

做法 ✓（不改任何已有产物 ✗）：
  1) 建临时源根 `TMP/a4src/<host>/<stem>.v` ✓（= `hosts_a4/<host>/base/<host>_clean.v` ✓，注入前网表 ✓）
  2) 建 manifest（`host, stem, recipe, file` ✓）
  3) 调 `phase2/ys/make_inst_alignment.py --out-dir <_dev_a4>/mappings` ✓
  4) 把 `<stem>__ys_<recipe>.json` **复制到真实视图名** ✓（`…__keepcur__ys_abc` / `…__keepnone__ys_abc` ✓）

用法 ✓：python -X utf8 phase2/ys/make_a4_mappings.py [--limit N]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "generate_trans" / "hosts_a4"
FOLD = ROOT / "generate_trans" / "folds" / "_dev_a4"
LIB = ROOT / "generate_trans" / "folds" / "hosts_bt31" / "verilog_lib.v"
TOOL = ROOT / "phase2" / "ys" / "make_inst_alignment.py"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    trans = sorted(FOLD.glob("trans/*.v"))
    if not trans:
        print("[ERR] 先跑 build_a4_fold.py ✗（trans/ 为空 ✓）")
        return 1
    tmp = Path.home() / "AppData" / "Local" / "Temp" / "a4src"
    man = Path.home() / "AppData" / "Local" / "Temp" / "a4_manifest.csv"
    rows = ["host,stem,recipe,file"]
    for f in trans:
        v = f.stem                                   # 完整视图名 ✓（`<host>__<kind>_sK_d1_s42` ✓）
        host = v.split("__")[0]
        clean = SRC / host / "base" / f"{host}_clean.v"
        if not clean.exists():
            print(f"[skip] 缺 clean ✗ {clean}")
            continue
        (tmp / host).mkdir(parents=True, exist_ok=True)
        dst = tmp / host / f"{v}.v"
        if not dst.exists():
            shutil.copy2(clean, dst)
        # ✓ stem 直接用**完整视图名** ✓；recipe 固定 `ys_id` 只作占位 ✓（名字稍后重命名 ✓）
        rows.append(f"{host},{v},ys_id,{f.as_posix()}")
    man.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"[manifest] {len(rows) - 1} 行 ✓ → {man}")

    out = FOLD / "mappings"
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-X", "utf8", str(TOOL),
           "--hosts-root", str(tmp), "--manifest", str(man), "--lib", str(LIB),
           "--out-dir", str(out)]
    if a.limit:
        cmd += ["--limit", str(a.limit)]
    print("[run]", " ".join(cmd[-8:]))
    rc = subprocess.call(cmd, cwd=str(ROOT))
    print(f"[make_inst_alignment] rc={rc}")
    if rc != 0:
        return rc

    # 生成名 = `<view>__ys_ys_id` ✗ → 重命名为 `<view>.json` ✓（parser2 按视图名找 ✓）
    made = {p.name: p for p in out.glob("*.json")}
    n = 0
    for f in trans:
        v = f.stem
        gen = f"{v}__ys_ys_id.json"
        if gen in made:
            tgt = out / f"{v}.json"
            shutil.copy2(made[gen], tgt)
            n += 1
    print(f"[copy] 重命名 {n} 个 ✓ → {out}")
    stale = [p for p in out.glob("*.json") if "__ys_" in p.name]
    for p in stale:
        p.unlink()
    print(f"[clean] 删除占位名 {len(stale)} 个 ✓")
    stats = [(p.stem, len(json.loads(p.read_text(encoding='utf-8')).get('node_alignment') or []))
             for p in sorted(out.glob("*.json"))][:3]
    print("[sample] 对齐条数:", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
