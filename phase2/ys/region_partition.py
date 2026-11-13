# -*- coding: utf-8 -*-
"""region_partition.py —— 按 RTL 功能语义给网表分区，并把区域标签平移到所有等价网表。

思路
----
1) 区域在**源网表（orig）**上按 **RTL 网名语义**定义（例如 rs232 的 iXMIT* 是发送器、
   iRECEIVER*/rec* 是接收器、uart/sys/test 是顶层），与结构无关。
2) 区域标签**不在变体上重算**，而是用 fold 的 `data/for_train/alignment.json`
   （orig 节点 → trans 节点 的对应关系）平移过去 —— 于是同一个源设计的所有等价网表
   **天然指向同一个功能区**（区域 id 就是 orig 上的区域名）。

用法
----
    py phase2/ys/region_partition.py build --fold generate_trans/folds/hosts_beta2 \
        --out 10.13/regions_v2.json
    py phase2/ys/region_partition.py eval --fold generate_trans/folds/hosts_beta2 \
        --regions 10.13/regions_v2.json --ckpt results/<run>/best_model_<x>.pt \
        --out 10.13/region_metric_<name>.csv
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from phase2 import netlist_lib as NL                                    # noqa: E402
from phase2.name_index import build_name_index                           # noqa: E402

# 语义规则：按顺序匹配（先匹配到的优先）；Trojan* 网不参与定区，只用来"定位木马"
RULES = [
    ("TX", r"iXMIT|xmit"),
    ("RX", r"iRECEIVER|rec"),
    ("TOP", r"uart|sys|test"),
]
TROJAN_RE = re.compile(r"Trojan", re.I)


def region_of_nets(nets) -> str:
    """按引脚网名投票定区（Trojan* 网不投票）。"""
    score = collections.Counter()
    for n in nets:
        s = str(n)
        if TROJAN_RE.search(s):
            continue
        for name, pat in RULES:
            if re.search(pat, s):
                score[name] += 1
                break
    if not score:
        return "OTHER"
    return score.most_common(1)[0][0]


def build(args) -> int:
    fold = args.fold.resolve()
    lib = NL.load_library(fold / "verilog_lib.v")
    print("[1] 建/读名字索引（orig 视图 → {实例名: 节点号}）")
    nidx = build_name_index(fold)
    names_orig = nidx["orig"]
    print(f"    orig 视图 {len(names_orig)} 个")

    orig_region: dict[str, dict[int, str]] = {}
    region_nodes: dict[str, dict[str, int]] = {}
    for view, name2idx in names_orig.items():
        src = fold / "orig" / f"{view}.v"
        if not src.exists():
            print(f"    [WARN] 缺 {src.name}，跳过")
            continue
        nl = NL.parse_netlist(src, lib)
        per_node = {}
        for inst in nl.insts:
            idx = name2idx.get(inst.name)
            if idx is None:
                continue
            per_node[idx] = region_of_nets([n for _p, n in inst.conns])
        orig_region[view] = per_node
        region_nodes[view] = dict(collections.Counter(per_node.values()))
    print("[2] orig 区域分布（每视图）")
    for v in list(orig_region)[:3]:
        print(f"    {v}: {region_nodes[v]}")

    print("[3] 用 alignment.json 把区域平移到 trans 节点")
    al = np.asarray(json.loads((fold / "data" / "for_train" / "alignment.json")
                              .read_text(encoding="utf-8")), dtype=np.int64)
    og = torch.load(fold / "data" / "processed" / "orig_graph.pt", weights_only=False)
    tg = torch.load(fold / "data" / "processed" / "trans_graph.pt", weights_only=False)
    of = np.asarray(list(og.file_ids))
    tf = np.asarray(list(tg.file_ids))

    reg_names = sorted({r for d in orig_region.values() for r in d.values()})
    rid = {r: i for i, r in enumerate(reg_names)}
    o_reg = np.full(len(of), -1, dtype=np.int64)
    for view, per_node in orig_region.items():
        # 名字索引里存的是**全局节点号**（已核对：第二个视图 max_idx = 首视图节点数 + 自身），
        # 所以这里直接用，不能再加视图基址（加了会越界）。
        for idx, reg in per_node.items():
            o_reg[idx] = rid[reg]

    valid = o_reg[al[:, 0]] >= 0
    t_reg = np.full(len(tf), -1, dtype=np.int64)
    t_reg[al[valid, 1]] = o_reg[al[valid, 0]]
    cov = float((t_reg >= 0).mean())
    print(f"    alignment {len(al)} 对；trans 节点 {len(tf)} 个，其中 {int((t_reg >= 0).sum())} "
          f"个拿到区域（覆盖率 {cov:.1%}）")

    tro = tg.y.numpy() == 1
    per_view = {}
    for v in sorted({str(x) for x in tf.tolist()}):
        m = tf == v
        rr, pos = t_reg[m], tro[m]
        got = rr >= 0
        cnt = (collections.Counter(reg_names[i] for i in rr[pos & got])
               if (pos & got).any() else collections.Counter())
        per_view[v] = {"nodes": int(m.sum()), "region_cov": round(float(got.mean()), 4),
                       "n_trojan": int(pos.sum()),
                       "trojan_region": {k: int(c) for k, c in cnt.most_common()}}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(
        {"fold": str(fold), "rules": RULES, "regions": reg_names,
         "region_sizes_orig": region_nodes, "trans_cov": cov, "per_view": per_view},
        ensure_ascii=False, indent=1), encoding="utf-8")
    np.save(args.out.with_suffix(".npy"), t_reg)
    print(f"[导出] {args.out} 与 {args.out.with_suffix('.npy')}")

    print("[4] 可行性检验：同一源设计的各等价网表，木马落在哪些功能区")
    bysrc = collections.defaultdict(dict)
    for v, d in per_view.items():
        bysrc[re.sub(r"__(rw[a-z0-9]+_d\d+_s\d+|ys_[a-z0-9]+)$", "", v)][v] = d
    for src in sorted(bysrc):
        if not src.startswith("rs232"):
            continue
        print(f"    {src}")
        for v, d in sorted(bysrc[src].items()):
            if d["n_trojan"]:
                print(f"      {v.split('__', 1)[1]:<26} 区域覆盖 {d['region_cov']:.0%} "
                      f"木马区域 {d['trojan_region']}")
    return 0


def show(args) -> int:
    """把原始网表的分区摊开看：每个功能区有哪些单元、木马落在哪，
    并顺带算一层"寄存器锥"细化（按有向扇入 BFS 到最近的触发器）。"""
    fold = args.fold.resolve()
    lib = NL.load_library(fold / "verilog_lib.v")
    nidx = build_name_index(fold)["orig"]
    dff_cls = {"DFFARX", "DFFNX", "DFFX", "SDFFSRX", "SDFFX"}

    for view, name2idx in sorted(nidx.items()):
        if args.view_prefix and not view.startswith(args.view_prefix):
            continue
        src = fold / "orig" / f"{view}.v"
        if not src.exists():
            continue
        nl = NL.parse_netlist(src, lib)
        gates = [i for i in nl.insts if i.name in name2idx]
        reg = {i.name: region_of_nets([n for _p, n in i.conns]) for i in gates}
        by_reg = collections.defaultdict(list)
        for i in gates:
            by_reg[reg[i.name]].append(i)

        # 有向扇入：net -> 驱动它的单元
        drv = {}
        for i in gates:
            for _p, n in nl.outs(i):
                drv.setdefault(n, i)
        fanin = {}
        for i in gates:
            fanin[i.name] = {drv[n].name for _p, n in i.conns if n in drv and drv[n].name != i.name}

        # 寄存器锥：从触发器出发沿扇入 BFS
        dffs = [i.name for i in gates if any(c in i.gate.upper() for c in ("DFF", "SDFF"))]
        cone = {d: d for d in dffs}
        frontier = list(dffs)
        while frontier:
            nxt = []
            for g in frontier:
                for p in fanin.get(g, ()):          # p 驱动 g
                    if p not in cone:
                        cone[p] = cone[g]
                        nxt.append(p)
            frontier = nxt

        print(f"\n=== {view} ===")
        print(f"    单元 {len(gates)} 个 | 触发器 {len(dffs)} 个 | 寄存器锥 {len(set(cone.values()))} 个")
        for r in sorted(by_reg, key=lambda k: -len(by_reg[k])):
            ex = []
            for i in by_reg[r][:4]:
                nets = [n for _p, n in i.conns if TROJAN_RE.search(str(n)) is None][:2]
                ex.append(f"{i.name}({i.gate}):{','.join(map(str, nets))}")
            print(f"    [{r:<5}] {len(by_reg[r]):>4} 个单元  例：{' | '.join(ex)}")

        print("    —— 木马单元定位 ——")
        for i in gates:
            if TROJAN_RE.search(i.name):
                nets = [str(n) for _p, n in i.conns]
                print(f"      {i.name:<12} {i.gate:<12} 功能区 {reg[i.name]:<5} "
                      f"寄存器锥 {str(cone.get(i.name, '-'))[:22]:<22} 引脚网 {nets[:4]}")
        if args.limit and len(by_reg):
            pass
        if args.view_prefix == "":
            break
    return 0



def eval_metric(args) -> int:
    """区域级检测指标：top-k 节点 → 功能区，看是否命中"木马所在功能区"。

    关键点：真值区域来自 orig 的语义分区、经 alignment 平移到该变体，
    所以**跨等价网表是可比的**（同一个功能区 id）。
    """
    import importlib.util

    import pandas as pd
    import yaml

    spec = importlib.util.spec_from_file_location("tt23", ROOT / "train_test2.3.py")
    T = importlib.util.module_from_spec(spec)
    sys.modules["tt23"] = T
    spec.loader.exec_module(T)

    fold = args.fold.resolve()
    data = json.loads(args.regions.read_text(encoding="utf-8"))
    reg_names = data["regions"]
    t_reg = np.load(args.regions.with_suffix(".npy"))
    pt_dir = args.pt_dir or (fold / "data" / "processed")
    o, t, _meta = T.load_fold(pt_dir)
    dev = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    for d in (o, t):
        d.x, d.edge_index = d.x.to(dev), d.edge_index.to(dev)
    cfg = yaml.safe_load((ROOT / "config_lr3e3.yaml").read_text(encoding="utf-8"))
    model = T.build_model(cfg, o.x.size(1), dev)
    ck = torch.load(args.ckpt, map_location=dev, weights_only=False)
    model.load_state_dict(ck["state_dict"])
    model.eval()
    with torch.no_grad():
        sc = torch.softmax(model(t.x, t.edge_index).float(), dim=1)[:, 1].cpu().numpy()
    tf = np.asarray(list(t.file_ids))
    y = t.y.numpy()

    rows = []
    for v in sorted({str(x) for x in tf.tolist()}):
        if args.circuit and args.circuit not in v:
            continue
        m = tf == v
        rr, ss, yy = t_reg[m], sc[m], y[m]
        if not (rr >= 0).any() or int((yy == 1).sum()) == 0:
            continue
        true_regs = {reg_names[i] for i in rr[yy == 1] if i >= 0}
        order = np.argsort(-ss)
        mode = re.sub(r"^.*?__", "", v)
        mode = re.sub(r"(_d\d+_s\d+)$", "", mode)
        row = {"view": v, "mode": mode, "nodes": int(m.sum()),
               "n_trojan": int((yy == 1).sum()),
               "region_cov": round(float((rr >= 0).mean()), 3),
               "true_region": "|".join(sorted(true_regs))}
        for pct in (0.01, 0.05):
            k = max(1, int(len(ss) * pct))
            regs = {reg_names[i] for i in rr[order[:k]] if i >= 0}
            row[f"top{pct}_regions"] = "|".join(sorted(regs))
            row[f"top{pct}_hit"] = int(bool(regs & true_regs))
            row[f"top{pct}_nreg"] = len(regs)
        rows.append(row)

    df = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False, encoding="utf-8-sig")
    cols = ["mode", "nodes", "n_trojan", "true_region", "top0.01_hit", "top0.05_hit",
            "top0.01_nreg", "top0.05_nreg"]
    print(df[[c for c in cols if c in df.columns]].to_string(index=False))
    for pct in ("0.01", "0.05"):
        c = f"top{pct}_hit"
        if c in df.columns:
            print(f"[宏] top{float(pct)*100:.0f}% 命中木马功能区 = {df[c].mean():.3f} "
                  f"| 平均命中区域数 = {df[f'top{pct}_nreg'].mean():.2f}")
    print(f"[导出] {args.out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="RTL 功能语义分区 + 区域级检测指标")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="按语义分区并平移到所有等价网表")
    b.add_argument("--fold", type=Path, required=True)
    b.add_argument("--out", type=Path, default=ROOT / "10.13" / "regions_v2.json")
    e = sub.add_parser("eval", help="用 ckpt 算区域级指标")
    e.add_argument("--fold", type=Path, required=True)
    e.add_argument("--regions", type=Path, required=True)
    e.add_argument("--ckpt", type=Path, required=True)
    e.add_argument("--out", type=Path, required=True)
    e.add_argument("--pt-dir", type=Path, default=None,
                   help="默认 <fold>/data/processed；换成 group_fold_*_mixed/processed 即可用新特征")
    e.add_argument("--circuit", type=str, default="rs232")
    s = sub.add_parser("show", help="摊开看原始网表的分区（含寄存器锥细化）")
    s.add_argument("--fold", type=Path, required=True)
    s.add_argument("--view-prefix", type=str, default="rs232")
    s.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.cmd == "build":
        return build(a)
    if a.cmd == "show":
        return show(a)
    return eval_metric(a)


if __name__ == "__main__":
    raise SystemExit(main())

