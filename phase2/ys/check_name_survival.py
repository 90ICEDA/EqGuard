# -*- coding: utf-8 -*-
"""check_name_survival.py —— 新配方上实验之前，先做"名字存活检查"。

背景（第九个坑）：
    我们靠**名字对齐**把木马标签从源网表传到 yosys 变体上。但名字能不能活下来是
    **配方相关**的：
      * `abc`（abc 映射到 AND/OR/XOR 库单元）：被 keep 的**网名**活下来了（木马/对照
        锚点 115 个）→ 标签传得过去 → 指标可信；
      * `id`（只做常数传播与清理）：网名与实例名**都换了**（源里 TrojanAHJ/AP0/AP1/AP2/AT1
        五个实例，变体里 0 个）→ 对齐只剩 1 个锚点 → 标签传不过去 →
        **视图正样本变成 0，AP 假性归零**。
    所以任何新配方，先跑这个检查；存活率接近 0 就别拿它做实验（会得到假结论）。

用法：
    py phase2/ys/check_name_survival.py --recipe id --ys-root generate_trans/yskeep_id_rs232
    py phase2/ys/check_name_survival.py --recipe abc --ys-root generate_trans/yskeep
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

from phase2 import netlist_lib as NL  # noqa: E402

LIB_DEFAULT = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"
SPECIAL = ("Trojan", "Ctl", "Ctrl")


def names(path: Path, lib: dict):
    nl = NL.parse_netlist(path, lib)
    insts = {i.name for i in nl.insts}
    nets = {n for i in nl.insts for _p, n in nl.outs(i)}
    return insts, nets


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", default="id")
    ap.add_argument("--host", default="rs232t1000")
    ap.add_argument("--ys-root", type=Path, default=None,
                    help="默认猜 generate_trans/yskeep_<recipe>_<host>")
    ap.add_argument("--hosts-root", type=Path, default=ROOT / "generate_trans" / "hosts_bt")
    ap.add_argument("--lib", type=Path, default=LIB_DEFAULT)
    a = ap.parse_args()
    lib = NL.load_library(a.lib)
    ys = a.ys_root or (ROOT / "generate_trans" / f"yskeep_{a.recipe}_{a.host}")
    cands = sorted(ys.rglob(f"*__ys_{a.recipe}.v"))
    print(f"[配方] {a.recipe}｜[变体目录] {ys}｜找到 {len(cands)} 个")

    rows = []
    for cand in cands:
        stem = cand.name.replace(f"__ys_{a.recipe}.v", "")
        src = a.hosts_root / a.host / f"{stem}.v"
        if not src.exists():
            continue
        io, no = names(src, lib)
        it, nt = names(cand, lib)
        so = {x for x in io if x.startswith(SPECIAL)}
        sn = {x for x in no if x.startswith(SPECIAL)}
        rows.append({"视图": stem, "源实例": len(io), "变体实例": len(it),
                     "源木马实例": len(so), "存活实例": len(so & it),
                     "源木马网": len(sn), "存活网": len(sn & nt),
                     "实例名交集": len(io & it), "网名交集": len(no & nt)})
    t = pd.DataFrame(rows)
    if t.empty:
        print("没找到可检查的视图（检查 --ys-root / --host / 文件名约定）")
        return 1
    print(t.to_string(index=False))
    se, sn = int(t.存活实例.sum()), int(t.源木马实例.sum())
    ne, nn = int(t.存活网.sum()), int(t.源木马网.sum())
    print(f"\n[汇总] 木马/对照实例名存活 {se}/{sn}；网名存活 {ne}/{nn}")
    if se + ne == 0:
        print("[判读] 存活为 0 → 该配方**不能**用名字对齐：标签传不过去，"
              "指标会假性归零，不能拿它下结论。")
    else:
        print("[判读] 有名字存活 → 可以建按名字的对齐，标签可传（再用 mapping 里的"
              "木马锚点数复核一次）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
