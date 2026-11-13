#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
analyze_miter.py — 调试用：看 miter.json 里 $equiv 比较点到底接在什么端点上

用法： python3 analyze_miter.py <miter.json>
输出：
  - 模块端口 / cell 类型直方图
  - 每个非“同线合并”的 $equiv 单元，及其 A/B 位被哪些 cell 端口消费
  - 基于“消费端”推断的分类计数（PO / next-state D / share-state Q / 内部）
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def bits(x):
    if x is None:
        return []
    if not isinstance(x, (list, tuple)):
        x = [x]
    return [str(b) for b in x]


FF_PREFIXES = ("$dff", "$sdff", "$adff", "$dffsr", "$ff", "$ffsr", "$dlatch", "$sr")
FF_CELL_HINTS = ("DFF", "SDFF", "LATCH")


def is_ff(cell_type: str) -> bool:
    """触发器判定：yosys 内部 FF 单元，或还没 techmap 的设计单元（SDFFSRX1_RS 等）。"""
    t = str(cell_type)
    if t.startswith(FF_PREFIXES):
        return True
    return any(h in t.upper() for h in FF_CELL_HINTS)


def classify_miter(miter) -> dict:
    """对 miter 模块做比较点分类（与单文件模式的判定完全一致，供批量汇总复用）。

    返回：n_equiv / merge_constraint / share_state_check / next_state_check /
          out_check / internal_check / n_cells / n_cell_types
    """
    out_bits = set()
    for pn, pi in miter.get("ports", {}).items():
        if pi.get("direction") == "output":
            out_bits.update(bits(pi.get("bits")))

    consumers = defaultdict(list)
    dff_d, dff_q = set(), set()
    for cn, c in miter.get("cells", {}).items():
        ct = str(c.get("type", ""))
        for port, b in c.get("connections", {}).items():
            for bit in bits(b):
                consumers[bit].append(f"{ct}.{port}")
        if is_ff(ct):
            for port, b in c.get("connections", {}).items():
                if port in ("D", "D_N"):
                    dff_d.update(bits(b))
                elif port in ("Q", "Q_N", "QN"):
                    dff_q.update(bits(b))

    eq = [(cn, c) for cn, c in miter.get("cells", {}).items()
          if c.get("type") in ("$equiv", "$eqx")]
    cats = Counter()
    for cn, c in eq:
        a = bits(c.get("connections", {}).get("A"))
        b = bits(c.get("connections", {}).get("B"))
        if sorted(a) == sorted(b):
            cats["merge_constraint"] += 1
            continue
        s = set(a) | set(b)
        cons = [x for bit in s for x in consumers.get(bit, [])]
        if s & dff_q:
            cats["share_state_check"] += 1
        elif s & dff_d:
            cats["next_state_check"] += 1
        elif s & out_bits:
            cats["out_check"] += 1
        elif any(x.endswith(".D") or x.endswith(".D_N") for x in cons if is_ff(x.split(".")[0])):
            cats["next_state_check"] += 1
        elif any(is_ff(x.split(".")[0]) and (x.endswith(".Q") or x.endswith(".Q_N")) for x in cons):
            cats["share_state_check"] += 1
        else:
            cats["internal_check"] += 1
    return {"n_equiv": len(eq), "merge_constraint": cats["merge_constraint"],
            "share_state_check": cats["share_state_check"],
            "next_state_check": cats["next_state_check"],
            "out_check": cats["out_check"], "internal_check": cats["internal_check"],
            "n_cells": len(miter.get("cells", {})),
            "n_cell_types": len({str(c.get("type")) for c in miter.get("cells", {}).values()})}


def pick_miter(mods):
    for name, m in mods.items():
        if "top" in m.get("attributes", {}):
            return m
    name = [n for n in mods if "miter" in n.lower()][0]
    return mods[name]


def batch(files, out_csv, verbose=False) -> int:
    """批量分类：把若干 miter.json 的分类计数汇总成机器可读 CSV"""
    import pandas as pd
    rows = []
    for p in files:
        try:
            data = json.loads(open(p, encoding="utf-8").read())
            info = classify_miter(pick_miter(data["modules"]))
            stem = p.stem
            info["view"] = stem[:-len(".miter")] if stem.endswith(".miter") else stem
            info["file"] = p.name
            rows.append(info)
            if verbose:
                print(f"  {info['view']}: n_equiv={info['n_equiv']} nextD={info['next_state_check']} "
                      f"PO={info['out_check']} shareQ={info['share_state_check']} "
                      f"merge={info['merge_constraint']}")
        except Exception as e:      # noqa: BLE001
            print(f"  [WARN] {p.name} 解析失败: {e}")
    if not rows:
        return 1
    df = pd.DataFrame(rows)
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    keys = ["n_equiv", "next_state_check", "out_check", "share_state_check",
            "merge_constraint", "internal_check"]
    tot = {k: int(df[k].sum()) for k in keys}
    print(f"[OK] {len(df)} 个视图 -> {out_csv}")
    print(f"     合计比较点 {tot['n_equiv']}｜next-state D {tot['next_state_check']}｜"
          f"PO {tot['out_check']}｜shared-state Q {tot['share_state_check']}｜"
          f"同线合并 {tot['merge_constraint']}｜内部 {tot['internal_check']}")
    return 0


def verbose_one(path: Path) -> int:
    data = json.loads(open(path, encoding="utf-8").read())
    mods = data["modules"]
    miter = pick_miter(mods)
    name = [n for n, m in mods.items() if m is miter][0]
    print(f"[module] {name}")
    for pn, pi in miter.get("ports", {}).items():
        b = bits(pi.get("bits"))
        print(f"[port] {pn:<28} {pi.get('direction'):<7} bits={b[:6]}{'...' if len(b) > 6 else ''}")
    types = Counter(c.get("type") for c in miter.get("cells", {}).values())
    print(f"\n[cell types] {dict(types.most_common(12))}")
    info = classify_miter(miter)
    cats = {k: v for k, v in info.items() if k.endswith("_check") or k == "merge_constraint"}
    print(f"[equiv cells] {info['n_equiv']}")
    print(f"\n[分类] {cats}  总比较点={info['n_equiv']}")
    return 0


def main() -> int:
    import argparse
    import glob as _glob

    ap = argparse.ArgumentParser(description="miter 比较点分析（单文件详细 / --batch 批量汇总）")
    ap.add_argument("json", nargs="?", help="单个 miter.json（详细模式）")
    ap.add_argument("--batch", type=str, default="",
                    help="批量模式：目录或 glob（逗号分隔多个），逐个分类后汇总成 CSV")
    ap.add_argument("--out", type=str, default="comparison_point_stats.csv")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if args.batch:
        files = []
        for pat in [x.strip() for x in args.batch.split(",") if x.strip()]:
            hits = _glob.glob(pat)
            if not hits and Path(pat).is_dir():
                hits = _glob.glob(str(Path(pat) / "*.json"))
            files += [Path(p) for p in hits]
        files = sorted(set(files))
        if not files:
            print(f"[ERROR] --batch 没有匹配到文件：{args.batch}")
            return 1
        return batch(files, Path(args.out), args.verbose)
    if not args.json:
        ap.error("需要 <miter.json> 或 --batch")
    return verbose_one(Path(args.json))


if __name__ == "__main__":
    raise SystemExit(main())
