#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
process_pt2.py — 把某个 **fold 工作目录** 的 parser2 产物构建成 GIN 训练用的 .pt（fold 感知）

与旧 process_pt.py 的区别：
  1) 支持一个工作目录里含多个视图（多文件）：按 `metadata_*.json` 的 file_ids 给每个节点打上
     **视图级角色**（train / val / test），据此生成 mask（视图级划分，杜绝同视图节点泄漏）。
  2) trans 标签默认用 **provenance 传播标签**（class_map_trans_transported.json，由 Orig 沿血缘传播），
     而不是网表名字里是否含 "trojan"；可用 --trans-label name 切回名字派生（对照实验）。
  3) 附带每个视图的 CEC 状态（view_manifest_cec.csv），训练/评测输出里会带上，便于审计。
  4) alignment 保持 **label-free**（原始血缘，不看标签），仅作锚点对（Anchor AP）与一致性损失使用。

用法：
  python process_pt2.py --work-dir <fold work dir> \
      --fold-json <matrix/folds/<fold>/views.json> [--circuits rs232] [--trans-label transported]
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import scipy.sparse as sp
import torch
from torch_geometric.data import Data


def load_json(path: Path, default="__raise__"):
    if not path.exists():
        if default == "__raise__":
            raise SystemExit(f"[ERROR] 缺少文件 {path}")
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_cec_status(matrix_root: Path, views: List[str]) -> Dict[str, str]:
    """从 matrix/view_manifest_cec.csv 取每个视图的 CEC 状态（缺失记 UNKNOWN）。"""
    import csv
    status = {v: "UNKNOWN" for v in views}
    vm = matrix_root / "view_manifest_cec.csv"
    if not vm.exists():
        return status
    want = set(views)
    with open(vm, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            name = str(r.get("view_name", ""))
            if name in want:
                status[name] = str(r.get("cec_status", "") or "UNKNOWN")
    return status


def parse_view_meta(view: str) -> Dict[str, object]:
    """从视图名解析出 (电路, 算子序列, 深度, seed)，例如 rs232t1000__balance-decomp_d2_s42。"""
    head, _, tail = view.partition("__")
    ops, depth, seed = "", 0, -1
    if tail:
        bits = tail.split("_")
        ops = bits[0]
        for b in bits[1:]:
            if b.startswith("d") and b[1:].isdigit():
                depth = int(b[1:])
            elif b.startswith("s") and b[1:].isdigit():
                seed = int(b[1:])
    return {"circuit": head.rsplit("t", 1)[0] if "t" in head else head,
            "file_stem": head, "operators": ops, "depth": depth, "seed": seed}


def assign_roles(fold: Dict[str, object], views_present: List[str],
                 val_every: int) -> Tuple[Dict[str, str], List[str]]:
    """
    视图级角色划分：
      test  —— fold spec 的 test_views
      val   —— 每个电路内，训练视图按名字排序后每 val_every 个取 1 个（默认 4 → 25%）
      train —— 其余训练视图
    """
    present = set(views_present)
    train_views = [v for v in (fold.get("train_views") or []) if v in present]
    test_views = [v for v in (fold.get("test_views") or []) if v in present]
    val_views = [v for v in (fold.get("val_views") or []) if v in present]

    role: Dict[str, str] = {v: "test" for v in test_views}
    if val_views:
        # fold spec 已经写明 val ✓ → **必须照用** ✓（早先被忽略 ✗ → 训练视图被悄悄砍掉 ✗）
        for v in val_views:
            role.setdefault(v, "val")
        for v in train_views:
            role.setdefault(v, "train")
    else:
        by_circuit: Dict[str, List[str]] = {}
        for v in sorted(train_views):
            by_circuit.setdefault(str(parse_view_meta(v)["file_stem"]), []).append(v)
        for _, vs in sorted(by_circuit.items()):
            for i, v in enumerate(vs):
                role[v] = "val" if (val_every > 1 and i % val_every == val_every - 1) else "train"
    missing = [v for v in (fold.get("train_views") or []) + (fold.get("val_views") or [])
               + (fold.get("test_views") or []) if v not in present]
    return role, missing


def build_data(ft: Path, suffix: str, class_map: Dict[str, object],
               role_of_view: Dict[str, str], cec_status: Dict[str, str],
               is_orig: bool) -> Tuple[Data, List[str]]:
    adj = sp.load_npz(ft / f"adj_full_{suffix}.npz").tocoo()
    edge_index = torch.tensor(np.vstack((adj.row, adj.col)), dtype=torch.long)
    x = torch.from_numpy(np.load(ft / f"feats_{suffix}.npy")).float()

    meta = load_json(ft / f"metadata_{suffix}.json")
    prefixes: List[str] = list(meta["prefixes"])
    file_ids: List[str] = list(meta["file_ids"])
    n = x.size(0)
    if len(file_ids) != n:
        raise SystemExit(f"[ERROR] metadata_{suffix}.json 的 file_ids 长度 {len(file_ids)} != 节点数 {n}")

    # class_map 的键是**全局节点索引**（parser2 跨文件连续编号，已实测）
    y = torch.zeros(n, dtype=torch.long)
    for k, v in class_map.items():
        y[int(k)] = int(v)

    node_role = ["orig"] * n if is_orig else [role_of_view.get(v, "unknown") for v in file_ids]

    def mask_for(name: str) -> torch.Tensor:
        return torch.tensor([r == name for r in node_role], dtype=torch.bool)

    data = Data(x=x, edge_index=edge_index, y=y,
                train_mask=mask_for("train"), val_mask=mask_for("val"),
                test_mask=mask_for("test"))
    data.prefixes = prefixes
    data.file_ids = file_ids
    data.node_role = node_role
    data.view_role = dict(role_of_view)
    data.cec_status = dict(cec_status)
    data.view_meta = {v: parse_view_meta(v) for v in sorted(set(file_ids))}
    return data, file_ids


def main() -> int:
    ap = argparse.ArgumentParser(description="fold 感知的 .pt 构建（process_pt2）")
    ap.add_argument("--work-dir", type=Path, required=True,
                    help="fold 工作目录（含 data/for_train 与 views.txt）")
    ap.add_argument("--fold-json", type=Path, required=True,
                    help="matrix/folds/<fold>/views.json（提供 train_views / test_views）")
    ap.add_argument("--matrix-root", type=Path, default=None,
                    help="generate_trans/matrix（读 view_manifest_cec.csv；默认按 fold-json 位置推断）")
    ap.add_argument("--circuits", type=str, default="", help="只保留这些电路的视图（逗号分隔前缀）")
    ap.add_argument("--trans-label", choices=["transported", "name"], default="transported",
                    help="trans 标签来源：transported=provenance 传播（默认）；name=网表名字派生")
    ap.add_argument("--val-every", type=int, default=4,
                    help="每个电路内每 N 个训练视图取 1 个作 val（默认 4；<=1 表示不划 val）")
    ap.add_argument("--out-dir", type=Path, default=None, help="默认 <work-dir>/data/processed")
    args = ap.parse_args()

    work: Path = args.work_dir.resolve()
    ft = work / "data" / "for_train"
    if not ft.exists():
        raise SystemExit(f"[ERROR] {ft} 不存在（先用 make_dataset.py 生成数据集）")
    out_dir = (args.out_dir or (work / "data" / "processed")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    fold = load_json(args.fold_json)
    kept = tuple(c.strip() for c in args.circuits.split(",") if c.strip())

    # 1) 视图清单（以 metadata_trans.json 为准 = 实际进入图里的视图）
    meta_t = load_json(ft / "metadata_trans.json")
    views_present = sorted(set(meta_t["file_ids"]))
    if kept:
        views_present = [v for v in views_present if v.startswith(kept)]
    role_of_view, missing = assign_roles(fold, views_present, args.val_every)
    role_of_view = {v: r for v, r in role_of_view.items() if v in set(views_present)}

    matrix_root = args.matrix_root
    if matrix_root is None:
        d = args.fold_json.resolve().parent        # .../matrix/folds/<fold>
        for _ in range(5):                         # 向上找到含 view_manifest_cec.csv 的目录
            if (d / "view_manifest_cec.csv").exists():
                break
            d = d.parent
        matrix_root = d
    cec = read_cec_status(Path(matrix_root), views_present)
    n_train = sum(1 for r in role_of_view.values() if r == "train")
    n_val = sum(1 for r in role_of_view.values() if r == "val")
    n_test = sum(1 for r in role_of_view.values() if r == "test")
    print(f"[INFO] 视图 {len(views_present)}｜train={n_train} val={n_val} test={n_test}"
          f"｜CEC PASS {sum(1 for v in views_present if cec.get(v) == 'PASS')}/{len(views_present)}")
    if missing:
        print(f"[WARN] fold spec 里有 {len(missing)} 个视图不在本工作目录（已忽略）：{missing[:5]}")

    # 2) 构建 .pt
    cm_orig = load_json(ft / "class_map_orig.json")
    if args.trans_label == "transported":
        cm_trans = load_json(ft / "class_map_trans_transported.json")
        label_src = "provenance-transported (label_transport.json)"
        # ✓ 兜底：A4 这类「orig 无真值 ✗ → transport 全 0 ✗」的 fold，
        #    若 transported 一个正例都没有 ✗ 而 trans 侧自己有点 ✓ → 用 union ✓（否则训练全负 ✗）
        _n_pos = sum(1 for v in cm_trans.values() if int(v) == 1) if isinstance(cm_trans, dict) else 0
        if _n_pos == 0:
            _own = load_json(ft / "class_map_trans.json")
            _n_own = sum(1 for v in _own.values() if int(v) == 1) if isinstance(_own, dict) else 0
            if _n_own:
                cm_trans = _own
                label_src = f"transported=0 → fallback to trans-side ({_n_own} pos)"
                print(f"[WARN] transported 正例 0 ✗ → 回退 trans 侧标签（{_n_own} 个正例 ✓）")
    else:
        cm_trans = load_json(ft / "class_map_trans.json")
        label_src = "name-derived (instance name contains 'trojan')"

    orig_data, _ = build_data(ft, "orig", cm_orig, {}, {}, is_orig=True)
    # orig 侧 mask 的**新模式（γ）**：一份电路可能有多份 orig（每 instance 一份），
    # 此时 orig stem 与视图前缀对不上 → 必须靠 orig_view_map（build_fold_* 生成）打 mask。
    # 缺它时 train_test2.3.apply_masks 会退回"按电路前缀"匹配 ✗ → orig.train_mask 全空 ✗
    # → cross_entropy(空张量) = NaN ✗ → 整个训练静默失效（2026-10-17 实测 ✗）。
    ovm_p = Path(work) / "orig_view_map.json"
    if ovm_p.exists():
        ovm_raw = load_json(ovm_p)
        orig_data.orig_view_map = {str(k): [str(x) for x in v] for k, v in ovm_raw.items()}
        hit = sum(1 for k in orig_data.orig_view_map if k in set(orig_data.file_ids))
        print(f"[INFO] orig_view_map：{len(orig_data.orig_view_map)} 个 orig ↔ 变换视图"
              f"（与 orig.file_ids 匹配 {hit}/{len(orig_data.orig_view_map)}）")
        if hit == 0:
            print("[WARN] orig_view_map 与 orig.file_ids 完全对不上 ✗ → orig mask 会全空 ✗")
    else:
        print(f"[WARN] 缺 {ovm_p}：orig 侧 mask 只能按电路前缀匹配"
              f"（多 orig 时会全空 ✗ → loss=NaN ✗）")
    trans_data, trans_files = build_data(ft, "trans", cm_trans, role_of_view, cec, is_orig=False)

    alignment = torch.tensor(load_json(ft / "alignment.json"), dtype=torch.long).t()
    trans_data.alignment = alignment
    print(f"[INFO] alignment（label-free 血缘）：{alignment.shape[1]} 对｜"
          f"orig 覆盖 {len(set(alignment[0].tolist()))}/{orig_data.num_nodes}｜"
          f"trans 覆盖 {len(set(alignment[1].tolist()))}/{trans_data.num_nodes}")
    print(f"[INFO] masks: train={int(trans_data.train_mask.sum())} "
          f"val={int(trans_data.val_mask.sum())} test={int(trans_data.test_mask.sum())} 节点")

    torch.save(orig_data, out_dir / "orig_graph.pt")
    torch.save(trans_data, out_dir / "trans_graph.pt")

    # 3) 元数据（审计用）
    def dist(d: Data) -> Dict[str, int]:
        return {"nodes": int(d.num_nodes), "edges": int(d.edge_index.shape[1]),
                "label1": int(d.y.sum()), "dims": int(d.x.size(1))}

    idx_by_view: Dict[str, List[int]] = {}
    for i, v in enumerate(trans_files):
        idx_by_view.setdefault(v, []).append(i)
    per_view: Dict[str, Dict[str, object]] = {}
    for v, idxs in idx_by_view.items():
        per_view[v] = {"role": role_of_view.get(v, "unknown"),
                       "cec_status": cec.get(v, "UNKNOWN"),
                       "nodes": len(idxs),
                       "label1": int(trans_data.y[idxs].sum()),
                       **parse_view_meta(v)}
    meta_out = {
        "work_dir": str(work), "fold_json": str(args.fold_json.resolve()),
        "fold": fold.get("fold"), "level": fold.get("level"),
        "trans_label_source": label_src,
        "n_views": len(views_present), "n_train_views": n_train,
        "n_val_views": n_val, "n_test_views": n_test,
        "views_train": sorted(v for v, r in role_of_view.items() if r == "train"),
        "views_val": sorted(v for v, r in role_of_view.items() if r == "val"),
        "views_test": sorted(v for v, r in role_of_view.items() if r == "test"),
        "cec_all_pass": all(cec.get(v) == "PASS" for v in views_present),
        "orig": dist(orig_data), "trans": dist(trans_data),
        "alignment_pairs": int(alignment.shape[1]),
        "orig_view_map": int(len(getattr(orig_data, "orig_view_map", {}) or {})),
        "val_every": args.val_every, "per_view": per_view,
    }
    (out_dir / "dataset_meta.json").write_text(
        json.dumps(meta_out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[OK] {out_dir}\\orig_graph.pt, trans_graph.pt, dataset_meta.json")
    print(f"     orig: {dist(orig_data)}｜trans: {dist(trans_data)}｜标签来源：{label_src}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
