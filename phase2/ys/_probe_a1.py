# -*- coding: utf-8 -*-
"""_probe_a1.py —— A1 开工前的结构探针：只读 JSON/CSV，不依赖 torch。

把需要确认的事实一次性打到 stdout（重定向到文件后再读）：
  1) 两个 fold 的 dataset_meta.json 结构（是否含逐视图节点数/正样本数）
  2) fold views.json / views_meta.csv 的字段
  3) hosts_bt2 的 instances.csv / rewrite_variants.csv 字段与 mode 分布
  4) rw_mappings 的 node_alignment 规模（按 mode 抽 2 个看）
用法：py phase2/ys/_probe_a1.py > probe_a1.txt
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
G = ROOT / "generate_trans"


def brief(o, n=400):
    s = json.dumps(o, ensure_ascii=False, default=str)
    return s[:n] + (" ..." if len(s) > n else "")


def sec(t):
    print("\n" + "=" * 8 + " " + t + " " + "=" * 8)


def main() -> int:
    for fold in ("hosts_beta2", "hosts_beta"):
        F = G / "folds" / fold
        sec(f"fold {fold}")
        for p in sorted(F.glob("*.json")) + [F / "data" / "processed" / "dataset_meta.json"]:
            if not p.exists():
                continue
            try:
                j = json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                print(f"  {p.name}: <读不了 {e}>")
                continue
            if isinstance(j, dict):
                ks = list(j.keys())
                print(f"  {p.name}: dict keys({len(ks)}) = {ks[:24]}")
                for k in ks[:6]:
                    v = j[k]
                    t = type(v).__name__
                    extra = f" len={len(v)}" if isinstance(v, (list, dict)) else f" = {v}"
                    print(f"      · {k}: {t}{extra}")
                    if isinstance(v, dict) and v:
                        k0 = next(iter(v))
                        print(f"          样例 key={k0!r} -> {brief(v[k0], 300)}")
                    elif isinstance(v, list) and v:
                        print(f"          样例 [0] = {brief(v[0], 300)}")
            else:
                print(f"  {p.name}: {type(j).__name__} len={len(j)} 样例={brief(j[:1] if isinstance(j, list) else j, 300)}")

    sec("rewrite_variants.csv（hosts_bt2）")
    rv = pd.read_csv(G / "hosts_bt2" / "rewrite_variants.csv")
    print("  columns:", list(rv.columns))
    print("  mode 分布:", dict(Counter(rv["mode"].astype(str))))
    print("  样例行:", brief(rv.iloc[0].to_dict(), 300))

    sec("instances.csv（hosts_bt2）")
    ins = pd.read_csv(G / "hosts_bt2" / "instances.csv")
    print("  columns:", list(ins.columns))
    print("  kind 分布:", dict(Counter(ins["kind"].astype(str))))
    print("  host×kind:", dict(Counter(ins["host"].astype(str) + "/" + ins["kind"].astype(str))))

    sec("rw_mappings 抽样（按 mode）")
    H = G / "hosts_bt2" / "rs232t1000" / "rw_mappings"
    files = sorted(H.glob("*.json"))
    print(f"  rs232t1000 mapping 文件 {len(files)} 个")
    bymode = {}
    for p in files:
        m = json.loads(p.read_text(encoding="utf-8"))
        md = str(m.get("operator_family") or m.get("mode") or "?")
        bymode.setdefault(md, []).append((p.name, m))
    for md, lst in sorted(bymode.items()):
        nm, m = lst[0]
        na = m.get("node_alignment")
        n_na = len(na) if isinstance(na, (dict, list)) else 0
        n_tgt = len({t for v in na.values() for t in (v if isinstance(v, list) else [v])}) if isinstance(na, dict) else 0
        print(f"  {md:<10} n={len(lst):<4} 样例={nm[:60]}")
        print(f"      keys={list(m.keys())}")
        print(f"      node_alignment={n_na} 目标节点={n_tgt} n_rewritten={m.get('n_rewritten')} "
              f"src_verilog={m.get('src_verilog')!r}")
        if isinstance(na, dict) and na:
            k = next(iter(na))
            print(f"      样例对齐 {k!r} -> {brief(na[k], 160)}")

    sec("hosts_bt2 每个 host 的 rw/ 视图数（按 mode 后缀）")
    for hd in sorted((G / "hosts_bt2").iterdir()):
        if not hd.is_dir():
            continue
        rw = hd / "rw"
        if not rw.exists():
            continue
        c = Counter()
        for f in rw.glob("*.v"):
            s = f.stem
            tail = s.split("__")[-1]
            c[tail if tail.startswith("ys_") or tail.startswith("rw") else "?"] += 1
        print(f"  {hd.name:<14} {dict(sorted(c.items()))}")

    sec("CEC 记录文件")
    for p in [G / "hosts_bt2" / "rw_cec_results.csv", G / "yslib2b_keep" / "cec3.csv",
              G / "yskeep2b" / "ys_manifest.csv", G / "hosts_bt" / "rw_cec_results.csv"]:
        if p.exists():
            d = pd.read_csv(p)
            print(f"  {p.relative_to(ROOT).as_posix()}: {len(d)} 行 cols={list(d.columns)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
