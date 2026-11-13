# -*- coding: utf-8 -*-
"""make_feat_subset_fold.py —— 按保持率筛特征：对 fold 的节点特征做"置零掩码"，生成新的 processed 目录。

为什么置零而不是切片：
    `T22.siamese_loss` 内部会**按固定下标读 `x[:, 29]`**（= dist_to_PI）。
    一旦切片，后面所有下标都会错位 → 一致性损失会读到错误的列。置零不改变维度与下标 ✓
    对被丢掉的特征，模型等价于少了一个输入（只留一个常数偏置项）✓

产物：<out>/processed/{orig_graph.pt,trans_graph.pt}（特征已置零）+ 其余文件原样复制 +
      feat_subset.json（**自证**：用了哪个 retention 表、丢了哪些特征、训练/测试电路各是哪些）

用法：
    py phase2/ys/make_feat_subset_fold.py --src 10.13/group_fold_ys5 \
        --out 10.13/group_fold_ys5_fs_droppseudo --drop-tiers 伪信号
    py phase2/ys/make_feat_subset_fold.py --src 10.13/group_fold_ys5 \
        --out 10.13/group_fold_ys5_fs_keepretained --keep-tiers 候选真信号,中间
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd
import torch

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

from phase2.ys.feature_retention import feature_names  # noqa: E402  （复用 39 维命名）

# 本轮固定的划分（写进 feat_subset.json 自证，避免以后记错）
TRAIN_CIRCUITS = ["s15850t100", "s35932t200", "s38417t100", "s38584t100"]
TEST_CIRCUIT = "rs232t1000"
TRAIN_MODES = "decomp3,ys_abc"
TEST_MODES = "decomp3,bubble,ys_abc,ys_aig,ys_rt"


TIER_ALIAS = {"pseudo": "伪信号", "cand": "候选真信号", "mid": "中间", "none": "无关"}


def resolve_tiers(s: str) -> set:
    """判级优先用 ASCII 别名（中文当命令行参数会被终端编码搞坏，表现为"丢掉 0 维"的静默失败）。"""
    return {TIER_ALIAS.get(x.strip(), x.strip()) for x in s.split(",") if x.strip()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--retention-csv", type=Path,
                    default=ROOT / "10.13" / "feature_retention_g5.csv")
    ap.add_argument("--drop-tiers", default="", help="丢掉这些判级（默认 伪信号）")
    ap.add_argument("--keep-tiers", default="", help="只保留这些判级（给定时忽略 --drop-tiers）")
    a = ap.parse_args()

    d = pd.read_csv(a.retention_csv)
    order, _groups = feature_names(a.src)
    known = set(d.tier.dropna().unique())
    if a.keep_tiers:
        keep = resolve_tiers(a.keep_tiers)
        unknown = keep - known
        if unknown:
            print(f"[ERROR] 未知判级 {sorted(unknown)}；可用 {sorted(known)}；"
                  f"ASCII 别名 {sorted(TIER_ALIAS)}")
            return 1
        drop_names = [f for f, t in zip(d.feature, d.tier) if t not in keep]
        rule = f"只保留判级 {sorted(keep)}（其余置零）"
    else:
        drop = resolve_tiers(a.drop_tiers or "pseudo")
        unknown = drop - known
        if unknown:
            print(f"[ERROR] 未知判级 {sorted(unknown)}；可用 {sorted(known)}；"
                  f"ASCII 别名 {sorted(TIER_ALIAS)}")
            return 1
        drop_names = [f for f, t in zip(d.feature, d.tier) if t in drop]
        rule = f"丢掉判级 {sorted(drop)}（置零）"
    if not drop_names:
        print("[ERROR] 一个特征都没丢，规则可能没匹配上——拒绝生成（避免静默产出与全量相同的 fold）")
        return 1

    name2idx = {n: i for i, n in enumerate(order)}
    idx = sorted(name2idx[n] for n in drop_names if n in name2idx)
    kept = [n for n in order if n not in set(drop_names)]

    srcp, outp = a.src / "processed", a.out / "processed"
    if not (srcp / "trans_graph.pt").exists():
        print(f"[ERROR] 找不到 {srcp}/trans_graph.pt")
        return 1
    outp.mkdir(parents=True, exist_ok=True)
    for fn in ("orig_graph.pt", "trans_graph.pt"):
        g = torch.load(srcp / fn, weights_only=False)
        x = g.x.clone()
        if idx:
            x[:, idx] = 0.0
        g.x = x
        torch.save(g, outp / fn)
    for fn in ("views.json", "dataset_meta.json", "gatelookup_recommended.json"):
        for d in (srcp, a.src):        # 这些文件在 processed/ 下，也可能在上一层
            p = d / fn
            if p.exists():
                shutil.copy2(p, outp / fn)
                shutil.copy2(p, a.out / fn)
                break

    info = {
        "rule": rule, "retention_csv": str(a.retention_csv),
        "n_dropped": len(idx), "n_kept": len(kept),
        "dropped_features": drop_names, "kept_features": kept,
        "dropped_dims": idx,
        "train_circuits": TRAIN_CIRCUITS, "test_circuit": TEST_CIRCUIT,
        "train_modes": TRAIN_MODES, "test_modes": TEST_MODES,
        "note": "特征采用置零，维度仍为 39；T22.siamese_loss 依赖 x[:,29] 的下标不变",
    }
    (a.out / "feat_subset.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[规则] {rule}")
    print(f"[丢掉 {len(idx)} 维] {', '.join(drop_names)}")
    print(f"[保留 {len(kept)} 维] {', '.join(kept)}")
    print(f"[导出] {outp}（orig/trans 已置零）＋ feat_subset.json")
    print(f"[划分] 训练电路 {TRAIN_CIRCUITS} × 模式 {TRAIN_MODES}"
          f"｜测试电路 {TEST_CIRCUIT} × 模式 {TEST_MODES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
