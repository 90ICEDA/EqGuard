# -*- coding: utf-8 -*-
"""a4_shortcuts.py —— A4：捷径检查（门名 / 输出可达性 / 门数 / 深度 / 到 PO 距离）。

对每个注入视图（源网表级 ✓）算：
  reach_po       载荷网能否沿扇出到达主输出 ✓（1/0）
  dist_po        载荷网到最近主输出的跳数（不可达 = -1 ✓）
  payload_dead   载荷网没有任何消费者 ✓
  n_gates/depth  注入子图的门数 / 最长路径（跳 ✓）
  name_leak      注入门命名是否直接泄漏标签 ✓（1 = 泄漏 ✗）
产物：10.15/01_数据与标签/A4_对照样本/tables/a4_shortcuts.csv
用法：py phase2/ys/a4_shortcuts.py --roots generate_trans/hosts_a4,generate_trans/hosts_bt2 --host rs232t1000
"""
import argparse, glob, json, sys
from collections import deque
from pathlib import Path

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))
from phase2 import netlist_lib as NL  # noqa: E402
from phase2.ys.make_a2_anchors import LIB_DEFAULT, Graph, norm  # noqa: E402


def bfs_to_po(g: Graph, outs, start: str):
    """从网 start 出发沿「消费实例 → 其输出网」扩散，返回到最近主输出的跳数（不可达 -1）。"""
    pos = set(outs)
    if start in pos:
        return 0
    seen, q = {start}, deque([(start, 0)])
    while q:
        net, d = q.popleft()
        for inst in g.cons.get(net, []):
            for _p, on in g.out_ports.get(inst, []):
                if on in pos:
                    return d + 1
                if on not in seen:
                    seen.add(on)
                    q.append((on, d + 1))
    return -1


def depth_of(g: Graph, insts: set) -> int:
    """注入子图的最长路径（跳 ✓，按「输入网驱动实例」定边 ✓）。"""
    outs = {n for i in insts for _p, n in g.out_ports.get(i, [])}
    memo = {}

    def dp(i, stack=()):
        if i in memo:
            return memo[i]
        if i in stack:
            return 0
        best = 1
        for _p, n in g.in_ports.get(i, []):
            d = g.drv.get(n)
            if d and d in insts:
                best = max(best, 1 + dp(d, stack + (i,)))
        memo[i] = best
        return best

    return max([dp(i) for i in insts], default=0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", default="generate_trans/hosts_a4,generate_trans/hosts_bt2")
    ap.add_argument("--hosts", default="rs232t1000")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "10.15" / "01_数据与标签" / "A4_对照样本" / "tables" / "a4_shortcuts.csv")
    ap.add_argument("--lib", type=Path, default=LIB_DEFAULT)
    a = ap.parse_args()
    lib = NL.load_library(a.lib)
    rows = []
    for root in [x for x in a.roots.split(",") if x.strip()]:
        rp = ROOT / root
        for host in [x for x in a.hosts.split(",") if x.strip()]:
            pj = rp / host / "provenance.json"
            if not pj.exists():
                print("[skip]", pj)
                continue
            for rec in json.loads(pj.read_text(encoding="utf-8")):
                src = rp / host / f"{rec['view']}.v"
                if not src.exists():
                    continue
                g = Graph(NL.parse_netlist(src, lib))
                gates = [n for n in (rec.get("new_gates") or []) if n in g.cell]
                if not gates:
                    continue
                pos = set(norm(o) for o in g.nl.outputs)
                outs_of_inj = {n for i2 in gates for _p, n in g.out_ports.get(i2, [])}
                dists = [bfs_to_po(g, pos, n) for n in outs_of_inj]
                reach = [d for d in dists if d >= 0]
                dist = min(reach) if reach else -1
                dangling = sum(1 for n in outs_of_inj if not g.cons.get(n) and n not in pos)
                low = [str(n).lower() for n in gates]
                pred = ("trojan" if any("trojan" in n for n in low) else
                        "control" if any("ctl" in n for n in low) else "unknown")
                leak = int(pred == rec["kind"])
                rows.append({"root": root, "host": host, "view": rec["view"], "kind": rec["kind"],
                             "a4_family": rec.get("a4_family", ""),
                             "n_gates": len(gates), "depth": depth_of(g, set(gates)),
                             "name_pred": pred,
                             "reach_po": int(dist >= 0), "dist_po": dist,
                             "n_dangling_out": dangling,
                             "name_leak": leak})
    import pandas as pd
    d = pd.DataFrame(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(d.to_string(index=False))
    print("\n=== 汇总（按 数据集 × 族）===")
    if len(d):
        d["fam"] = d.apply(lambda r: r.a4_family or r.kind, axis=1)
        s = d.groupby(["root", "fam"]).agg(
            n=("view", "size"), n_gates=("n_gates", "mean"), depth=("depth", "mean"),
            reach_po=("reach_po", "mean"), dist_po=("dist_po", "mean"),
            dangling_out=("n_dangling_out", "mean"),
            name_leak=("name_leak", "mean")).round(3)
        print(s.to_string())
    print(f"\n[OK] → {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
