# -*- coding: utf-8 -*-
"""inject_newfamily.py —— 给指定 host 造"新族"源网表（B 型口径，只调用注入器、不删目录）。

为什么不用 `deadline_ablation.build_b`：它建之前会 `rmtree(bt_dir)`（第 56–57 行），
会把 hosts_bt 下已登记的 `rw/` 与 `rw_mappings/` 一并删掉 ✗。

关键性质：注入的 rng 以**实例名**为 key（`Random(f"{host}-{name_prefix}-{seed}")`），
所以**追加实例不会改变已有实例的结构** → 用 md5 校验来证明（见执行记录）。

用法：
    py phase2/ys/inject_newfamily.py --hosts rs232t1000 --out generate_trans/hosts_bt2 \
        --instances 8 --controls 10 --seed 42
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from phase2 import inject_trojan as IT                       # noqa: E402
from phase2.netlist_lib import load_library                   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="造新族源网表（B 型：劫持真实输出）")
    ap.add_argument("--hosts", type=str, default="rs232t1000")
    ap.add_argument("--out", type=Path, default=IT.ROOT / "generate_trans" / "hosts_bt2")
    ap.add_argument("--instances", type=int, default=8)
    ap.add_argument("--controls", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    lib = load_library(IT.LIB_DEFAULT)
    for s in IT.TROJAN_SPECS:                 # B 型口径（与 hosts_bt 一致）
        s["payload_target"] = "hijack_out"
    rows = []
    for h in [x for x in a.hosts.split(",") if x.strip()]:
        rows += IT.build_host(h, a.out, lib, a.instances, a.controls, a.seed)

    d = pd.DataFrame(rows)
    csv = a.out / "instances.csv"
    if csv.exists():                          # 与已有表合并（不覆盖别的 host 的行）
        old = pd.read_csv(csv)
        d = (pd.concat([old, d], ignore_index=True)
               .drop_duplicates(subset=["view"], keep="last"))
    d.to_csv(csv, index=False, encoding="utf-8-sig")
    print(f"[OK] 新造 {len(rows)} 个视图 → {a.out}（表内合计 {len(d)} 行）")
    print(d.groupby(["host", "kind"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
