# -*- coding: utf-8 -*-
"""_diag_align.py —— 定位"按网名对齐"为什么抓不到木马单元。

对同一个视图，把这块逻辑在三个文件里的身份打出来：
  源网表（hosts_bt）、keep 版（hosts_bt_keep）、转换回库单元的变体（yslib_keep）
关注两个问题：木马单元的**输出网名**是什么、这个网在变体里由谁驱动。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from phase2 import netlist_lib as NL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
LIB = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"
HOST, STEM, REC = "rs232t1000", "rs232t1000__injalpha_d1_s42", "abc"
FILES = {
    "源网表": ROOT / "generate_trans" / "hosts_bt" / HOST / f"{STEM}.v",
    "keep版": ROOT / "generate_trans" / "hosts_bt_keep" / HOST / f"{STEM}.v",
    "转换后": ROOT / "generate_trans" / "yslib_keep" / HOST / f"{STEM}__ys_{REC}.v",
}
TARGET = "TrojanA_p0"


def main() -> int:
    lib = NL.load_library(LIB)
    info = {}
    for tag, f in FILES.items():
        if not f.exists():
            print(f"[缺] {tag} {f}")
            continue
        nl = NL.parse_netlist(f, lib)
        drv = nl.drivers()
        out_nets = {}
        for i in nl.insts:
            for _p, n in nl.outs(i):
                out_nets.setdefault(n, i.name)
        tro = sorted({i.name for i in nl.insts if "Trojan" in i.name})
        tro_outs = sorted({n for n, who in out_nets.items() if "Trojan" in n})
        info[tag] = (nl, drv, out_nets)
        print(f"=== {tag} ===")
        print(f"  实例 {len(nl.insts)} 个｜含 Trojan 的实例名 {len(tro)} 个：{tro[:6]}")
        print(f"  输出网里含 Trojan 的 {len(tro_outs)} 个：{tro_outs[:6]}")
        print(f"  {TARGET}：驱动者 = {drv.get(TARGET)!r}｜是不是某个实例的输出网 = "
              f"{out_nets.get(TARGET)!r}")
        print(f"  assign 行数 {len(nl.assigns)}｜wire/port 声明 {len(nl.port_decls)}")
    # 交集诊断
    if len(info) >= 2:
        a, b = info["源网表"], info["转换后"]
        set_no, set_nt = set(a[1]), set(b[1])
        for tg, t in (("源网表", a), ("转换后", b)):
            s = set(t[1])
            print(f"  [{tg}] 含 Trojan 的被驱动网：{sorted(x for x in s if 'Trojan' in x)[:8]}")
        print(f"  两侧被驱动网的 Trojan 交集："
              f"{sorted(x for x in (set_no & set_nt) if 'Trojan' in x)[:8]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
