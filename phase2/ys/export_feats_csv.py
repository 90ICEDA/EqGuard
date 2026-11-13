"""export_feats_csv.py —— 把 `feats_{orig,trans}.npy` 导成**可人工核对**的 CSV。

为什么需要：`feats_*.npy` 是纯数字矩阵 ✓，39 列里 25 列是门类型 one-hot ✓，
剩下的结构位列顺序只能看代码 ✓（`parser2.process_domain`）→ 出一张带列名/实例名的表，
人工扫几行就能判断"特征到底对不对" ✓。

39 维布局（contract 模式；none 模式前 33 维相同）：
  00–24  门类型 one-hot（`gatelookup_recommended.json` 的 key 顺序）
  25     log1p(#入边)          26  log1p(#邻居)
  27     touches_PI             28  touches_PO
  29     dist_to_PI（-1=不可达） 30  dist_to_PO（-1=不可达）
  31     log1p(2-hop 扇入)       32  log1p(2-hop 扇出)
  33     dist_to_PI_dag（断环后） 34  dist_to_PO_dag
  35     log1p(2-hop 扇入 dag)   36  log1p(2-hop 扇出 dag)
  37     in_cycle               38  scc_size

用法：
  python -X utf8 phase2/ys/export_feats_csv.py --work-dir _feataudit \
      --views rs232t1000__injalpha_d1_s42__keepcur__ys_abc,... --out-dir _featcsv
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "verilog_data"))

import parser2 as P  # noqa: E402

STRUCT = {25: "log1p_fanin", 26: "log1p_neighbors", 27: "touches_PI", 28: "touches_PO",
          29: "dist_to_PI", 30: "dist_to_PO", 31: "log1p_2hop_fanin",
          32: "log1p_2hop_fanout", 33: "dist_to_PI_dag", 34: "dist_to_PO_dag",
          35: "log1p_2hop_fanin_dag", 36: "log1p_2hop_fanout_dag",
          37: "in_cycle", 38: "scc_size"}


def gate_names(work: Path) -> list[str]:
    raw = json.loads((work / "gatelookup_recommended.json").read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "gatelookup" in raw:
        raw = raw["gatelookup"]
    items = sorted(raw.items(), key=lambda kv: int(kv[1]))
    return [k for k, _ in items]


def instance_order(path: Path) -> list[str]:
    """复刻 `process_domain` 的 A–B 步，返回与 feats 行**同序**的实例名 ✓。"""
    lines = P.readlogs([str(path)])
    P.getprimlist([lines])
    lines = P.fixassigns([lines])
    for split in lines:
        for l in split:
            P.clean_1(l)
            wire_idx = P.getindices("wire", l)
            if wire_idx:
                l[:] = l[wire_idx[-1] + 1:-1]
    _gates, nodeslistlist, infolistlist, _idx, _ = P.parse_lines(lines)
    names = []
    for net_nodes, net_info in zip(nodeslistlist, infolistlist):
        _ = net_nodes
        names.extend([x[2] for x in net_info])
    return names


def main() -> int:
    ap = argparse.ArgumentParser(description="导出 feats_*.npy 为带列名的 CSV")
    ap.add_argument("--work-dir", type=Path, required=True, help="含 data/for_train 与 gatelookup 的工作目录")
    ap.add_argument("--suffix", default="trans", choices=["trans", "orig"])
    ap.add_argument("--views", default="", help="逗号分隔；留空=全部")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "_featcsv")
    ap.add_argument("--max-rows", type=int, default=0, help=">0 时每视图只导这么多行（便于人看）")
    a = ap.parse_args()

    ft = a.work_dir / "data" / "for_train"
    meta = json.loads((ft / "metadata_trans.json" if a.suffix == "trans"
                       else ft / "metadata_orig.json").read_text(encoding="utf-8"))
    feats = np.load(ft / f"feats_{a.suffix}.npy")
    file_ids = meta["file_ids"]
    cols = gate_names(a.work_dir)
    n_gate = feats.shape[1] - 14
    names = [f"onehot:{cols[i]}" if i < len(cols) else f"onehot:f{i:02d}" for i in range(n_gate)]
    names += [f"f{j:02d}_{STRUCT[j]}" for j in range(n_gate, feats.shape[1])]

    idx = {}
    for i, v in enumerate(file_ids):
        idx.setdefault(v, []).append(i)
    wanted = [s.strip() for s in a.views.split(",") if s.strip()] or sorted(idx)

    a.out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"col": range(len(names)), "name": names,
                  "kind": ["gate_onehot"] * n_gate + ["structural"] * 14}
                 ).to_csv(a.out_dir / "feats_columns.csv", index=False, encoding="utf-8-sig")

    src_root = a.work_dir / a.suffix
    for v in wanted:
        if v not in idx:
            print(f"[WARN] {v} 不在 metadata 里")
            continue
        rows = idx[v]
        sub = feats[rows, :]
        p = src_root / f"{v}.v"
        inst = instance_order(p) if p.exists() else []
        if len(inst) != len(rows):
            print(f"[WARN] {v}: 实例名 {len(inst)} != 节点 {len(rows)}（名字列留空）")
            inst = [""] * len(rows)
        gate = []
        for r in sub[:, :n_gate]:
            k = int(np.argmax(r)) if r.sum() > 0 else -1
            gate.append(cols[k] if 0 <= k < len(cols) else "")
        df = pd.DataFrame(sub, columns=names)
        df.insert(0, "node_idx", rows)
        df.insert(1, "view", v)
        df.insert(2, "inst_name", inst)
        df.insert(3, "gate_type", gate)
        n0 = a.max_rows if a.max_rows > 0 else len(df)
        out = a.out_dir / f"feats_{a.suffix}__{v}.csv"
        df.head(n0).to_csv(out, index=False, encoding="utf-8-sig")
        print(f"[导出] {out.name}  rows={min(n0, len(df))}/{len(df)}  cols={df.shape[1]}")
    print(f"[目录] {a.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
