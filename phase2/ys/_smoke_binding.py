# -*- coding: utf-8 -*-
"""_smoke_binding.py —— 冒烟测量：转换后网表的"绑定覆盖率"与"锥覆盖率"。

绑定覆盖率 = 每个单元的输出网名，能不能通过 `<view>.map.json` 的 prov 表或原名本身，
             解析到**原始网表里存在的网名**（这就是"变换后能不能绑回原网表"的直接度量）。
锥覆盖率   = 从 DFF + 主输出出发沿有向扇入 BFS（别名 assign 已展平），
             有多少单元能落到某个以端点命名的锥，且锥名在原始网表里存在。

用法：
    py phase2/ys/_smoke_binding.py --orig <orig.v> --converted-dir <dir> --pattern "*injalpha*"
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from phase2 import netlist_lib as NL                                    # noqa: E402

ALIAS = re.compile(r"assign\s+([^=\s;]+)\s*=\s*([^=\s;]+)\s*;")


def nets_of(nl) -> set:
    s = set(map(str, nl.inputs)) | set(map(str, nl.outputs))
    for i in nl.insts:
        for _p, n in i.conns:
            s.add(str(n))
    return s


def cones(path, lib):
    txt = Path(path).read_text(encoding="utf-8", errors="replace")
    par = {}

    def find(x):
        par.setdefault(x, x)
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    for a, b in ALIAS.findall(txt):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb
    nl = NL.parse_netlist(path, lib)
    drv = {}
    for i in nl.insts:
        for _p, n in nl.outs(i):
            drv.setdefault(find(str(n)), i)
    fanin = {i.name: {drv[find(str(n))].name for _p, n in i.conns
                      if find(str(n)) in drv and drv[find(str(n))].name != i.name}
             for i in nl.insts}
    po = {find(str(p)) for p in nl.outputs}
    seeds = sorted({i.name for i in nl.insts if "DFF" in i.gate.upper()}
                   | {i.name for i in nl.insts
                      if any(find(str(n)) in po for _p, n in nl.outs(i))})
    cone = {s: s for s in seeds}
    fr = list(seeds)
    while fr:
        nxt = []
        for g in fr:
            for p in fanin.get(g, ()):
                if p not in cone:
                    cone[p] = cone[g]
                    nxt.append(p)
        fr = nxt
    return nl, cone, set(seeds)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig", type=Path, required=True)
    ap.add_argument("--converted-dir", type=Path, required=True)
    ap.add_argument("--pattern", type=str, default="*")
    ap.add_argument("--lib", type=Path, default=ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v")
    a = ap.parse_args()
    lib = NL.load_library(a.lib)
    nlo, co, so = cones(a.orig, lib)
    onets = nets_of(nlo)
    so_names = set(so)
    print(f"[orig] 单元 {len(nlo.insts)} | 网名 {len(onets)} | 端点种子 {len(so)}")
    print(f"{'变体':<34}{'单元':>6}{'绑定覆盖率':>12}{'锥覆盖率':>10}{'锥名命中orig':>14}{'别名展平':>10}")
    for f in sorted(glob.glob(str(a.converted_dir / "**" / f"{a.pattern}.v"), recursive=True)):
        p = Path(f)
        mp = p.with_suffix(".map.json")
        prov = json.loads(mp.read_text(encoding="utf-8"))["prov"] if mp.exists() else {}
        nlv, cv, sv = cones(p, lib)
        names = [i.name for i in nlv.insts]
        bind = 0
        for i in nlv.insts:
            outs = [str(n) for _p, n in nlv.outs(i)]
            if any(prov.get(o, o) in onets or o in onets for o in outs):
                bind += 1
        cone_cov = sum(1 for n in names if n in cv)
        cone_hit = sum(1 for n in names if cv.get(n) in so_names)
        nfix = json.loads(mp.read_text(encoding="utf-8"))["n_alias_flattened"] if mp.exists() else -1
        print(f"{p.name[:-2]:<34}{len(names):>6}{100.0*bind/max(1,len(names)):>11.1f}%"
              f"{100.0*cone_cov/max(1,len(names)):>9.1f}%{100.0*cone_hit/max(1,len(names)):>13.1f}%"
              f"{nfix:>10}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
