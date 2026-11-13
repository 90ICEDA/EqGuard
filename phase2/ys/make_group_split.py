# -*- coding: utf-8 -*-
"""
make_group_split.py —— 造"按原始电路分组"的划分，堵住等价版本跨训练/测试的泄漏。

背景：现有 γ fold 把同一源视图的两个改写分到了两侧
（`rwdecomp3` 进训练、`rwbubble` 进测试），也就是同一个设计的两个等价版本跨了训练与测试。
10.10 里反复出现的"同电路协议结果不稳、跨种子标准差是未见电路协议五倍"，根子就在这里。

这一轮的划分规则（二维：源分组 × 变换种类）：
    训练 = 源电路属于 S_train 且 变换属于 T_train
    测试 = 源电路属于 S_test（整组留出）且 变换属于 T_test
    其余（S_train × T_test、或不在考虑内的变换）= 整组弃用，既不进训练也不进测试
这样保证：同一个原始电路的任何等价版本，全部落在同一侧。

实现上不改网表、不重跑数据管线，只做两件事：
    1) 按新规则改写 `trans_graph.pt` 里的 `view_role`，落到一个新的 processed 目录；
    2) 写一份新的 views.json 放进新 fold 目录。

用法：
    py phase2/ys/make_group_split.py --hold-circuit rs232t1000 \\
        --train-modes decomp3 --test-modes decomp3,bubble --out 10.13/group_fold
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import torch

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

from phase2 import p2common as C  # noqa: E402

RW_RE = re.compile(r"__(rw[a-z0-9]+_d\d+_s\d+|ys_[a-z0-9]+)$")


def parse_args():
    ap = argparse.ArgumentParser(description="按原始电路分组的划分")
    ap.add_argument("--fold", type=Path,
                    default=ROOT / "generate_trans" / "folds" / "hosts_beta")
    ap.add_argument("--hold-circuit", type=str, required=True,
                    help="整支留出的电路（测试侧）；也可传实例名，配合 --hold-by instance")
    ap.add_argument("--hold-by", choices=["circuit", "instance"], default="circuit")
    ap.add_argument("--train-modes", type=str, default="decomp3")
    ap.add_argument("--test-modes", type=str, default="decomp3,bubble")
    ap.add_argument("--val-every", type=int, default=4, help="训练侧每 N 个源视图切一个进验证")
    ap.add_argument("--out", type=Path, required=True)
    return ap.parse_args()


def src_of(v: str) -> str:
    return RW_RE.sub("", str(v))


def mode_of(v: str) -> str:
    m = RW_RE.search(str(v))
    if not m:
        return "src"
    frag = m.group(1)
    # 两种约定都要认：rwdecomp3_d1_s42 → decomp3 ；ys_abc → ys_abc
    return frag if frag.startswith("ys_") else frag.split("_d")[0][2:]


def key_of(v: str, by: str) -> str:
    parts = str(v).split("__")
    if len(parts) < 2:
        return parts[0] if parts else ""
    if by == "circuit":
        return parts[0]
    return parts[1].split("_d1")[0]


def main() -> int:
    a = parse_args()
    fold = a.fold.resolve()
    out = a.out.resolve()
    (out / "processed").mkdir(parents=True, exist_ok=True)

    orig, trans, meta = C.load_fold(fold / "data" / "processed")
    views = sorted({str(v) for v in trans.file_ids})
    roles = dict(getattr(trans, "view_role", {}) or {})
    hold = {x.strip() for x in a.hold_circuit.split(",") if x.strip()}
    tr_modes = {x.strip() for x in a.train_modes.split(",") if x.strip()}
    te_modes = {x.strip() for x in a.test_modes.split(",") if x.strip()}

    # 只处理"由某个源视图派生"的视图；源视图本身（合法对照的注入视图）按其电路归属
    srcs = {}
    for v in views:
        srcs.setdefault(src_of(v), set()).add(v)
    # 训练侧取每 val_every 个源进验证
    tr_srcs = sorted(s for s in srcs
                     if not any(key_of(x, a.hold_by) in hold for x in srcs[s]))
    va_srcs = set(tr_srcs[::a.val_every]) if a.val_every > 1 else set()

    new_role, stat = {}, {}
    for src, vs in srcs.items():
        is_hold = any(key_of(x, a.hold_by) in hold for x in vs)
        for v in vs:
            m = mode_of(v)
            if is_hold:
                r = "test" if m in te_modes else "drop"
            else:
                if m in tr_modes:
                    r = "val" if src in va_srcs else "train"
                else:
                    r = "drop"
            new_role[v] = r
            stat[r] = stat.get(r, 0) + 1
    # 没被 srcs 覆盖到的视图（理论上不会）保持原角色
    for v in views:
        if v not in new_role:
            new_role[v] = roles.get(v, "drop")
            stat[new_role[v]] = stat.get(new_role[v], 0) + 1

    # 泄漏自检：同一 src 的视图不允许同时出现在 train/val 与 test
    leak = []
    for src, vs in srcs.items():
        rs = {new_role.get(v) for v in vs}
        if rs & {"train", "val"} and "test" in rs:
            leak.append(src)

    if not hasattr(trans, "view_role") or trans.view_role is None:
        trans.view_role = {}
    trans.view_role = new_role
    torch.save(orig, out / "processed" / "orig_graph.pt")
    torch.save(trans, out / "processed" / "trans_graph.pt")
    shutil.copy(fold / "data" / "processed" / "dataset_meta.json",
                out / "processed" / "dataset_meta.json")
    old = json.loads((fold / "views.json").read_text(encoding="utf-8"))
    old.update({"fold": out.name + "_grouped",
                "train_views": sorted(v for v, r in new_role.items() if r == "train"),
                "val_views": sorted(v for v, r in new_role.items() if r == "val"),
                "test_views": sorted(v for v, r in new_role.items() if r == "test"),
                "note": (f"按原始电路分组：留出 {sorted(hold)}（by {a.hold_by}）；"
                         f"训练变换 {sorted(tr_modes)}，测试变换 {sorted(te_modes)}；"
                         f"其余 {stat.get('drop', 0)} 个视图整组弃用")})
    (out / "views.json").write_text(json.dumps(old, ensure_ascii=False, indent=1),
                                    encoding="utf-8")

    print(f"[INFO] 视图 {len(views)} 个｜角色统计 {stat}")
    print(f"[INFO] 训练源 {len(tr_srcs)} 个，其中验证源 {len(va_srcs)} 个")
    print(f"[INFO] 留出（{a.hold_by}）：{sorted(hold)}")
    print(f"[LEAK] 同时跨训练侧与测试侧的源视图数：{len(leak)}"
          + (f"（应为 0，示例 {leak[:3]}）" if leak else "（干净）"))
    print(f"[导出] {out}")
    return 0 if not leak else 2


if __name__ == "__main__":
    raise SystemExit(main())
