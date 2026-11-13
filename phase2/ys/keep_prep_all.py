# -*- coding: utf-8 -*-
"""
keep_prep_all.py —— 给木马相关网打上 `(* keep *)`，镜像出一个新的 hosts-root。

为什么要镜像：`build_yosys_netlists.py` 的输入是"hosts-root 下的网表"，
所以只要把打完 keep 的网表按同样的目录结构放好，就能直接复用它跑 yosys + CEC，
不用改那个脚本。keep 属性不改变功能，所以拿 keep 版当 CEC 的 golden 同样有效。

前缀从 provenance.json 里读（每个视图注入时都记了 name_prefix）。

用法：
    py phase2/ys/keep_prep_all.py --hosts rs232t1000 --hosts-root generate_trans/hosts_bt \
        --out generate_trans/hosts_bt_keep
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

from phase2 import netlist_lib as NL  # noqa: E402

LIB_DEFAULT = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"


def keep_netlist(src: Path, prefix: str, lib) -> tuple:
    nl = NL.parse_netlist(src, lib)
    pat = re.compile(r"^" + re.escape(prefix))
    nets = set()
    for i in nl.insts:
        for _p, n in i.conns:
            if pat.match(n):
                nets.add(n)
        if pat.match(i.name):
            for _p, n in nl.outs(i):
                nets.add(n)
    for n in list(nl.drivers()):
        if pat.match(n):
            nets.add(n)
    have = {d.split()[-1] for d in nl.port_decls if "wire" in d}
    add = sorted(n for n in nets if n not in have
                 and n not in nl.inputs and n not in nl.outputs)
    for n in add:
        nl.port_decls.append(f"(* keep *) wire {n}")
    return nl, len(nets), len(add)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hosts", type=str, required=True)
    ap.add_argument("--hosts-root", type=Path, default=ROOT / "generate_trans" / "hosts_bt")
    ap.add_argument("--out", type=Path, default=ROOT / "generate_trans" / "hosts_bt_keep")
    ap.add_argument("--lib", type=Path, default=LIB_DEFAULT)
    a = ap.parse_args()
    lib = NL.load_library(a.lib)
    hosts = [h.strip() for h in a.hosts.split(",") if h.strip()]
    tot = n_keep = 0
    for h in hosts:
        hd = a.hosts_root / h
        (a.out / h / "base").mkdir(parents=True, exist_ok=True)
        # 干净基底：没有木马，直接复制
        for f in (hd / "base").glob("*.v"):
            shutil.copy(f, a.out / h / "base" / f.name)
        pref = {}
        pj = hd / "provenance.json"
        if pj.exists():
            for rec in json.loads(pj.read_text(encoding="utf-8")):
                pref[rec.get("view")] = rec.get("prefix")
        for f in sorted(hd.glob("*.v")):
            stem = f.stem
            p = pref.get(stem)
            if p:
                nl, n1, n2 = keep_netlist(f, p, lib)
                (a.out / h / f.name).write_text(NL.emit_netlist(nl), encoding="utf-8")
                n_keep += 1
                tot += n2
            else:
                shutil.copy(f, a.out / h / f.name)
        print(f"[{h}] 视图 {len(list(hd.glob('*.v')))} 个，其中打 keep 的 {len(pref)} 个")
    print(f"[OK] 共 {n_keep} 个网表打了 keep，新增 keep 声明 {tot} 条 → {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
