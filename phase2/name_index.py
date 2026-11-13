# -*- coding: utf-8 -*-
"""
name_index.py —— 复用 parser2 的解析器，只抽取「实例名 → 全局节点索引」，不计算任何特征。

为什么需要它：
  `mappings/<view>.json` 的 node_alignment 是 **实例名** 级的对象对应（orig 名 → [trans 名...]），
  而模型评分是 **全局节点索引** 级的。要做「对象类别 × 逐节点 drift」的统计，必须把两边对齐。

  parser2.main / process_domain 会顺带算 39 维特征（对 96 万节点的 trans 图非常慢）；
  本模块只调用 `parse_lines` 之前的轻量步骤（readlogs → getprimlist → fixassigns →
  clean_1/wire 裁剪 → parse_lines），因此是**分钟级**的纯解析，不产生特征。

产物：<work_dir>/phase2_name_index.json
  {"orig": {stem: {inst_name: global_idx}},
   "trans": {view: {inst_name: global_idx}}}
注意：必须 `chdir(work_dir)` 后再调用 parser2，因为它用相对路径读库文件。
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from typing import Dict

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent
PARSER2 = ROOT / "data" / "verilog_data" / "parser2.py"


def _load_parser2():
    spec = importlib.util.spec_from_file_location("p2_parser2", str(PARSER2))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _nodeslist(p2, files):
    """复刻 process_domain 的 A/B 步，只拿到 nodeslistlist（每文件 {name: global_idx}）。

    process_domain(verilog_splits=[files, [], []]) 内部是
    `lines = [readlogs(files), readlogs([]), readlogs([])]`，因此这里构造同样形状。
    """
    lines = [p2.readlogs(files), [], []]
    p2.getprimlist(lines)
    lines = p2.fixassigns(lines)
    for split in lines:
        for l in split:
            p2.clean_1(l)
            wire_idx = p2.getindices("wire", l)
            if wire_idx:
                l[:] = l[wire_idx[-1] + 1:-1]
    _gates, nodeslistlist, _info, _index, _idx = p2.parse_lines(lines)
    return nodeslistlist


def build_name_index(work_dir: Path, force: bool = False) -> Dict[str, Dict[str, dict]]:
    work_dir = Path(work_dir).resolve()
    cache = work_dir / "phase2_name_index.json"
    if cache.exists() and not force:
        return json.loads(cache.read_text(encoding="utf-8"))

    p2 = _load_parser2()
    old = os.getcwd()
    os.chdir(work_dir)                          # parser2 依赖相对路径
    try:
        orig_files = p2.getverilogs(path="./", sub_folder="orig")
        trans_files = p2.getverilogs(path="./", sub_folder="trans")
        print(f"[name_index] orig 文件 {len(orig_files)}｜trans 文件 {len(trans_files)}")

        orig_nodes = _nodeslist(p2, orig_files)
        trans_nodes = _nodeslist(p2, trans_files)

        def _stem(p):
            b = os.path.basename(p)
            return b[:-2] if b.endswith(".v") else b

        out = {
            "orig": {_stem(f): {k.lstrip("\\"): int(v) for k, v in d.items()}
                     for f, d in zip(orig_files, orig_nodes)},
            "trans": {_stem(f): {k.lstrip("\\"): int(v) for k, v in d.items()}
                      for f, d in zip(trans_files, trans_nodes)},
        }
    finally:
        os.chdir(old)

    cache.write_text(json.dumps(out), encoding="utf-8")
    n_o = sum(len(d) for d in out["orig"].values())
    n_t = sum(len(d) for d in out["trans"].values())
    print(f"[name_index] 缓存 -> {cache}（orig {n_o} / trans {n_t} 个节点）")
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="构建 实例名->全局索引 缓存")
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    build_name_index(a.work_dir, force=a.force)
