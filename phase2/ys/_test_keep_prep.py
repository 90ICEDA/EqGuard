# -*- coding: utf-8 -*-
"""_test_keep_prep.py —— 把木马相关网显式声明成 `(* keep *) wire`，看能否扛过 yosys 重综合。

目的：yosys 重写之后节点名全变，导致改写视图拿不到标签（标签靠节点级对齐传递）。
如果给木马区域的网打上 keep 属性、让 yosys 保留这些名字，就能按名字建对齐。

用法：
    py phase2/ys/_test_keep_prep.py --host rs232t1000 --stem rs232t1000__injalpha_d1_s42 \
        --prefix TrojanA --out generate_trans/ysk_test
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

from phase2 import netlist_lib as NL  # noqa: E402

LIB_DEFAULT = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--stem", required=True)
    ap.add_argument("--prefix", required=True, help="木马实例的前缀，如 TrojanA")
    ap.add_argument("--hosts-root", type=Path, default=ROOT / "generate_trans" / "hosts_bt")
    ap.add_argument("--out", type=Path, default=ROOT / "generate_trans" / "ysk_test")
    ap.add_argument("--lib", type=Path, default=LIB_DEFAULT)
    a = ap.parse_args()

    src = a.hosts_root / a.host / f"{a.stem}.v"
    nl = NL.parse_netlist(src, NL.load_library(a.lib))
    pat = re.compile(r"^" + re.escape(a.prefix))
    nets = set()
    for i in nl.insts:
        for _p, n in i.conns:
            if pat.match(n):
                nets.add(n)
    for n in list(nl.drivers()):
        if pat.match(n):
            nets.add(n)
    # 木马门的输出网也算（可能不带前缀，例如被劫持的输出端口）
    for i in nl.insts:
        if pat.match(i.name):
            for _p, n in nl.outs(i):
                nets.add(n)
    have = {d.split()[-1] for d in nl.port_decls if "wire" in d}
    add = sorted(n for n in nets if n not in have and n not in nl.inputs and n not in nl.outputs)
    for n in add:
        nl.port_decls.append(f"(* keep *) wire {n}")
    dst = a.out / a.host / f"{a.stem}__keep.v"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(NL.emit_netlist(nl), encoding="utf-8")
    print(f"[OK] 木马相关网 {len(nets)} 个，新加 keep 声明 {len(add)} 个 → {dst}")
    print("     样例：", add[:6])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
