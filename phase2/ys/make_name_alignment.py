# -*- coding: utf-8 -*-
"""
make_name_alignment.py —— 给带 keep 的 yosys 变体建"按名字的节点对齐"。

背景：改写视图的正样本标签是靠 `node_alignment`（orig 实例名 → [trans 实例名]）传过去的。
yosys 重写后节点名全变，所以之前只能留空、标签传不过去。
给木马/对照相关网打了 `(* keep *)` 之后，这些单元的实例名两侧都在，
于是可以只对**名字能对上的那些节点**建对齐 —— 对标签传递来说这就够了（正样本本来只在木马那几个单元上）。

做法：解析源网表与转换后的变体，各取实例名集合，取交集，
写成 `{名字: [同名]}` 塞进 `rw_mappings/<view>.json`（其余字段照填）。

用法：
    py phase2/ys/make_name_alignment.py --hosts-root generate_trans/hosts_bt \
        --yslib generate_trans/yslib_keep --manifest generate_trans/yslib_keep/convert_manifest.csv
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

from phase2 import netlist_lib as NL  # noqa: E402

LIB_DEFAULT = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"


def names_of(path: Path, lib: dict) -> set:
    return {i.name for i in NL.parse_netlist(path, lib).insts}


def net2inst(path: Path, lib: dict) -> dict:
    """网名 → 驱动它的实例名。对齐要靠这个。

    两个坑：
    1) 被 keep 保住的是**网名**（TrojanA_p0 之类），实例名在重建后变成了新的匿名名；
    2) 转换器会给每个改写保留一条别名 assign（`assign TrojanA_p0 = TrojanA_p0__g213;`），
       所以这类网在 drivers() 里显示是 'assign' 驱动的 —— 必须**跟着别名追到底**，
       否则整条木马链都漏掉（这正是第一版对齐只抓到触发器、木马为 0 的原因）。
    """
    nl = NL.parse_netlist(path, lib)
    m = {}
    for i in nl.insts:
        for _p, n in nl.outs(i):
            m.setdefault(n, i.name)
    alias = {l: r.strip() for l, r in nl.assigns
             if re.fullmatch(r"[\w\\/$\[\]:.]+", r.strip())}
    out = dict(m)
    for l, r in alias.items():                 # 顺着别名走，最多追 4 跳防环
        cur, k = r, 0
        while cur in alias and k < 4:
            cur, k = alias[cur], k + 1
        if l not in out and cur in out:
            out[l] = out[cur]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hosts-root", type=Path, default=ROOT / "generate_trans" / "hosts_bt")
    ap.add_argument("--yslib", type=Path, default=ROOT / "generate_trans" / "yslib_keep")
    ap.add_argument("--manifest", type=Path,
                    default=ROOT / "generate_trans" / "yslib_keep" / "convert_manifest.csv")
    ap.add_argument("--lib", type=Path, default=LIB_DEFAULT)
    a = ap.parse_args()
    lib = NL.load_library(a.lib)
    H = a.hosts_root.resolve()
    d = pd.read_csv(a.manifest)
    d = d[~d.file.astype(str).str.startswith("ERROR")]

    rows = []
    for r in d.itertuples():
        host, stem, recipe = str(r.host), str(r.stem), str(r.recipe)
        src = H / host / f"{stem}.v"
        cand = Path(str(r.file))
        if not src.exists() or not cand.exists():
            continue
        no, nt = net2inst(src, lib), net2inst(cand, lib)
        align = {}
        # 一边是按**输出网名**对齐（keep 保住了木马/对照的网名）
        for net in set(no) & set(nt):
            align.setdefault(no[net], []).append(nt[net])
        # 另一侧是按**实例名**对齐（yosys 反而把触发器这类实例名留住了）
        io = {i.name for i in NL.parse_netlist(src, lib).insts}
        it = {i.name for i in NL.parse_netlist(cand, lib).insts}
        for nm in io & it:
            align.setdefault(nm, []).append(nm)
        rw_view = f"{stem}__ys_{recipe}"
        mp = H / host / "rw_mappings"
        mp.mkdir(parents=True, exist_ok=True)
        special = sorted(k for k in align if k.startswith(("Trojan", "Ctl", "Ctrl")))
        obj = {"src_verilog": f"{stem}.v", "operator_family": f"ys_{recipe}",
               "src_view": stem, "node_alignment": align,
               "n_rewritten": max(0, len(set(nt)) - len(align)),
               "n_split_objects": 0, "skipped": {},
               "note": "yosys 变体：按**输出网名**对齐（keep 保住了网名，实例名没保住）"}
        (mp / f"{rw_view}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
        rows.append({"host": host, "stem": stem, "recipe": recipe, "rw_view": rw_view,
                     "对齐节点": len(align), "其中木马或对照": len(special),
                     "样例": " ".join(special[:5])})
    t = pd.DataFrame(rows)
    print(t.to_string(index=False))
    print(f"\n[OK] 写了 {len(t)} 个 mapping；对齐节点合计 {int(t.对齐节点.sum())}，"
          f"其中木马/对照 {int(t['其中木马或对照'].sum())} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
