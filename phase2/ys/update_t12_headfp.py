"""update_t12_headfp.py —— P3：把 **head_fp / tail_pos** 并进 T12 表（纯 CSV ✓，无 pt ✓）。

做法 ✓：读 `t12_region_loss_summary.csv` ✓ + `head_fp.csv` ✓ →
在 `TABLES.md` 里**整段替换** T12（从 `## T12` 到下一个 `## T` 之前 ✓），幂等 ✓。
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
C6 = ROOT / "10.15" / "03_特征与模型" / "C6_区域级监督"
TABLES = ROOT / "10.15" / "07_论文图表" / "TABLES.md"


def main() -> int:
    summ = pd.read_csv(C6 / "tables" / "t12_region_loss_summary.csv").set_index("model")
    hf = pd.read_csv(C6 / "tables" / "head_fp.csv")
    base = hf[hf["npz"].str.match(r"gnn_v31_s\d+\.npz")]
    reg = hf[hf["npz"].str.match(r"gnn_v31r_l100_s\d+\.npz")]
    rows = [("基线（3 seed ✓）", base, "base"), ("**+ 区域损失 λ=10**", reg, "region_l10")]

    lines = ["## T12 C6 区域级监督（λ=10 ✓）× 3 seed（v3.1 ✓；来源 "
             "`C6_区域级监督/tables/{t12_region_loss_summary.csv, head_fp.csv}` ✓）", "",
             "口径 ✓：`--region-loss 10.0 --region-mode dff` ✓（锥内 **max** logit 的 BCE ✓，`pos_weight=30` ✓）；"
             "seed 42/1/2 ✓；**全部逐视图均值** ✓（pooled 不作主指标 ✗）。", "",
             "| 指标 | 基线（3 seed ✓） | **+ 区域损失 λ=10** | Δ |", "|---|---|---|---|"]
    pairs = [("view_ap", "节点 AP"), ("view_auc", "节点 AUC"), ("r1", "R@1%"),
             ("r5", "R@5%"), ("dff_view_ap", "DFF 锥 AP"), ("po_cone_view_ap", "**PO 锥 AP**")]
    b, r = summ.loc["base"], summ.loc["region_l10"]
    for k, name in pairs:
        bm, bs = float(b[k + "_mean"]), float(b[k + "_std"])
        rm, rs = float(r[k + "_mean"]), float(r[k + "_std"])
        lines.append(f"| {name} | {bm:.4f} ± {bs:.4f} | **{rm:.4f} ± {rs:.4f}** ✓ | "
                     f"**{(rm / bm - 1) * 100:+.1f}%** ✓ |")
    bh, rh = float(base["head_fp"].mean()), float(reg["head_fp"].mean())
    bt, rt = float(base["tail_pos"].mean()), float(reg["tail_pos"].mean())
    lines += [f"| **头部假阳性 head_fp（↓ 好 ✓）** | {bh:.1f} | **{rh:.1f}** ✓ | "
              f"**{(rh / bh - 1) * 100:+.1f}%** ✓ |",
              f"| 尾部漏检 tail_pos（↓ 好 ✓） | {bt:.2f} | {rt:.2f} ✓ | {(rt / bt - 1) * 100:+.1f}% ✓ |",
              "", "> ✓ **三个 seed 全部提升** ✓（AP 0.1616 / 0.1786 / 0.2149 vs 0.1404 / 0.1100 / 0.1727 ✓），"
                  "且**方差同时下降** ✓（AUC std 0.044 → 0.017 ✓）。",
              "> ✓ **机制**：head_fp 从 808/1264/212 降到 420/577/172（**−48%/−54%/−19%** ✓）→ \"证据成团\"成立 ✓。",
              "> ⚠️ **λ 必须按损失尺度定** ✓：λ≤1 无效 ✗（被 ASL≈0.93 淹没 ✗），λ=10 才生效 ✓；λ=5 亦有效但更弱 ⚠️。",
              "> ⚠️ **pooled 指标在 λ=10 下会崩** ✗（加分项整体抬高分数 ✗）→ **只报逐视图** ✓。", ""]

    cur = TABLES.read_text(encoding="utf-8")
    if "## T12" not in cur:
        raise SystemExit("[ERROR] TABLES.md 里没有 T12 ✗")
    new = re.sub(r"## T12 .*?(?=\n## T13 |\Z)", "\n".join(lines) + "\n", cur, flags=re.S)
    TABLES.write_text(new, encoding="utf-8")
    print("\n".join(lines[:12]))
    print(f"\n[out] {TABLES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
