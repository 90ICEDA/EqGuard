"""export_node_names.py —— 导出 **node_idx → 实例名**（只读 ✓，用于 N1 电路图标注 ✓）。

原理 ✓：`process_pt2` 建图时按**网表实例顺序**展开 ✓（实测：实例数 390 == 该视图节点数 390 ✓，
        唯一多出的一行是 `module <stem> (` 头行 ✓ → 去掉即可 ✓）→ **按位置一一对应** ✓。

校验 ✓：每个视图都比较「解析出的 cell 类型」与「节点 one-hot 解出的门类型」✓，
        一致率写入 `agreement.csv` ✓；< 0.90 会告警 ✗（说明顺序对不上 ✗，名字不可用 ✗）。

用法：
  py -X utf8 phase2/ys/export_node_names.py --fold generate_trans/folds/hosts_bt31 --split test
输出：`10.15/99_共用资产/node_names/<fold>_<split>.json.gz` ✓ + `agreement.csv` ✓
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[2]
RX = re.compile(r"^([A-Za-z_][\w]*)\s+([^\s(]+)\s*\(")


def gate_names(work: Path) -> list[str]:
    raw = json.loads((work / "gatelookup_recommended.json").read_text(encoding="utf-8"))
    raw = raw.get("gatelookup", raw)
    return [k for k, _ in sorted(raw.items(), key=lambda kv: int(kv[1]))]


def norm(cell: str) -> str:
    """把单元名归一到"门类"（`AND2X2`→`AND2X2` ✓；`SDFFSRX1_RS`→`DFF` ✓）。"""
    u = cell.upper()
    if "DFF" in u:
        return "DFF"
    return cell


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fold", type=Path, default=ROOT / "generate_trans/folds/hosts_bt31")
    ap.add_argument("--split", choices=["test", "val", "train", "all"], default="test")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.15" / "99_共用资产" / "node_names")
    a = ap.parse_args()
    W = a.fold
    d = torch.load(W / "data/processed/trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    X = np.asarray(d.x, np.float32)
    fids = np.asarray(json.loads((W / "data/for_train/metadata_trans.json")
                                 .read_text(encoding="utf-8"))["file_ids"]).astype(str)
    meta = json.loads((W / "views.json").read_text(encoding="utf-8"))
    views = sorted(set(fids)) if a.split == "all" else sorted(meta[f"{a.split}_views"])

    names = gate_names(W)
    ng = len(names)
    gid = np.where(X[:, :ng].sum(1) > 0, X[:, :ng].argmax(1), -1)

    out, rows = {}, []
    for v in views:
        idx = np.where(fids == v)[0]
        p = W / "trans" / f"{v}.v"
        if not p.exists() or len(idx) == 0:
            rows.append(dict(view=v, nodes=len(idx), instances=0, agree=np.nan, ok=False, note="缺 .v ✗"))
            continue
        inst = []
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            m = RX.match(line)
            if m and m.group(2) != v:
                inst.append((m.group(1), m.group(2)))
        if len(inst) != len(idx):
            rows.append(dict(view=v, nodes=len(idx), instances=len(inst), agree=np.nan,
                             ok=False, note="数量不一致 ✗"))
            continue
        exp = [names[i] for i in gid[idx] if 0 <= i < ng]
        got = [norm(c) for c, _ in inst]
        exp = [norm(x) for x in exp]
        agree = float(np.mean([1 if a_ == b_ else 0 for a_, b_ in zip(exp, got)])) if exp else 0.0
        ok = agree >= 0.90
        rows.append(dict(view=v, nodes=len(idx), instances=len(inst), agree=round(agree, 4),
                         ok=bool(ok), note="" if ok else "一致率低 ✗（顺序可能不对 ✗）"))
        if ok:
            out[v] = [nm for _, nm in inst]
    a.out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(a.out_dir / "agreement.csv", index=False, encoding="utf-8-sig")
    dst = a.out_dir / f"{W.name}_{a.split}.json.gz"
    with gzip.open(dst, "wt", encoding="utf-8") as fh:
        json.dump(out, fh)
    print(df.groupby("ok").size().to_string())
    print(f"[agree] mean={df['agree'].mean():.4f} ✓  views_ok={len(out)}/{len(views)} ✓")
    print(f"[out] {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
