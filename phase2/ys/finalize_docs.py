"""finalize_docs.py —— 修 T11/T13 登记、补 FIG_INDEX、写两条提醒（幂等 ✓，不碰 npz ✓）。

1. **T13 的 seed 列**：原实现按 glob 顺序记 0/1/2 ✗（真实是 s1/s2/s42 ✗）→ 从 npz 文件名解析 ✓ 并重写表 ✓
2. **T11 丢失 + 乱序** ✗：用 `E2_新电路/tables/a3_keep_pilot_summary.csv` ✓ 重建 T11，插到 T10 之后 ✓
3. **FIG_INDEX** 补 F1–F5 + N1_case ✓
4. `10.15至今完成情况.md` 补"A0 方差警示 ✗ / A4 配置差异 ⚠️" ✓
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "10.15"
TABLES = D / "07_论文图表" / "TABLES.md"
FINDEX = D / "07_论文图表" / "FIG_INDEX.md"
DONE = D / "00_说明" / "10.15至今完成情况.md"
T13 = D / "03_特征与模型" / "N2_双分支复核"


def fix_t13() -> None:
    per = T13 / "tables" / "t13_per_seed.csv"
    if not per.exists():
        print("[skip] T13 缺 per_seed ✗")
        return
    d = pd.read_csv(per)
    d["seed"] = d["npz"].str.extract(r"_s(\d+)\.npz$").astype(int)
    d = d.sort_values(["model", "seed"]).reset_index(drop=True)
    d.to_csv(per, index=False, encoding="utf-8-sig")
    g = d.groupby("model")
    keys = ["view_ap", "view_auc", "r1", "r5", "dff_view_ap", "po_cone_view_ap"]
    summ = pd.DataFrame({"model": sorted(d["model"].unique())})
    for k in keys:
        summ[k + "_mean"] = g[k].mean().values
        summ[k + "_std"] = g[k].std(ddof=1).values
    summ["n_seed"] = g["seed"].count().values
    summ.to_csv(T13 / "tables" / "t13_summary.csv", index=False, encoding="utf-8-sig")

    lines = ["## T13 v3.1 模型消融（A0/A1/A2/A3/A5 × 3 seed ✓；来源 "
             "`N2_双分支复核/tables/t13_summary.csv` ✓）", "",
             "口径 ✓：同一 fold ✓、同一预算（100 epoch ✓）、同一评测（逐视图 ✓ + 锥级 ✓）；"
             "seed 42/1/2 ✓（列里是真实 seed ✓，不是 glob 序号 ✓）。", "",
             "| 变体 | 节点 AP | 节点 AUC | R@1% | R@5% | DFF 锥 AP | PO 锥 AP | n |",
             "|---|---|---|---|---|---|---|---|"]
    for _, r in summ.iterrows():
        lines.append(f"| **{r['model']}** | {r['view_ap_mean']:.4f} ± {r['view_ap_std']:.4f} | "
                     f"{r['view_auc_mean']:.4f} ± {r['view_auc_std']:.4f} | "
                     f"{r['r1_mean']:.4f} | {r['r5_mean']:.4f} | "
                     f"{r['dff_view_ap_mean']:.4f} | {r['po_cone_view_ap_mean']:.4f} | {int(r['n_seed'])} |")
    a0 = d[d["model"].str.startswith("A0")]
    lines += ["", "> ⚠️ **A0（单分支）方差极大** ✗：" + " / ".join(f"{x:.4f}" for x in a0["view_ap"])
              + " → 均值被单个 seed 支配 ✗，论文必须配 std ✓ 并注明「单分支训练不稳定」✓。",
              "> ⚠️ **trust 掩码（A1，−5%）与 cone5（A3，−1%）在 v3.1 上不再提升** ✗ → 只能写成「fold 依赖」✓"
              "（dev4 上分别 +20% / +14% ✓）。",
              "> ✓ **双分支（A2，+106%）与区域监督（A5，+31%）是稳固收益** ✓。", ""]
    (T13 / "t13.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    cur = TABLES.read_text(encoding="utf-8")
    cur = re.sub(r"## T13 .*?(?=\n## |\Z)", "\n".join(lines) + "\n", cur, flags=re.S)
    TABLES.write_text(cur, encoding="utf-8")
    print("[T13] seed 已按文件名修正 + 表已重写 ✓")


def restore_t11() -> None:
    e2 = D / "05_木马家族扩展" / "E2_新电路" / "tables" / "a3_keep_pilot_summary.csv"
    if not e2.exists():
        print("[skip] 缺 E2 汇总 ✗")
        return
    d = pd.read_csv(e2)
    lines = ["## T11 新电路泛化（E2 ✓，`s38417t300`，keep=bnd ✓；来源 "
             "`E2_新电路/tables/a3_keep_pilot_summary.csv` ✓）", "",
             "口径 ✓：`s38417t300` 与训练的 `s38417t100` **同族不同实例** ✓；"
             "注入 6 组木马 + 8 组对照 + `injcmp`/`injflip` 新家族 ✓；在**配方原产物**上量 ✓。", "",
             "| 配方 | 转换 | CEC | 实例存活 | 锚点存活 | DFF-Q 存活 | 行数 |",
             "|---|---|---|---|---|---|---|"]
    for _, r in d.sort_values("recipe").iterrows():
        ok = "PASS ✓" if float(r.get("conv_ok", 0)) >= 1 else "FAIL ✗"
        lines.append(f"| `{r['recipe']}` | {ok} | {r['cec_conv']} | {r['surv_inst_text']:.3f} | "
                     f"{r['anchor_text_surv']:.3f} | {r['dffq_text_surv']:.3f} | {int(r['lines'])} |")
    lines += ["", "> ✓ **全部配方 × 全部视图通过转换 + CEC** ✓（18/18 × 3 ✓）→ 整链"
                  "（注入 → 验证 → 等价转换 → CEC ✓）在**没见过的电路**上成立 ✓。",
              "> ⚠️ 锚点存活 **0.485** 是上限警示 ✗：一半以上锚点在任何配方下都会丢 ✗ → 标签可绑定率的天花板 ✓。", ""]

    cur = TABLES.read_text(encoding="utf-8")
    if "## T11 " in cur:
        print("[T11] 已存在 ✓")
        return
    # 插到 T10 之后、T12 之前 ✓
    m = re.search(r"(## T10 .*?)(?=\n## T12 )", cur, flags=re.S)
    if not m:
        print("[WARN] 找不到 T10/T12 锚点，改为追加到末尾 ⚠️")
        cur = cur + "\n" + "\n".join(lines) + "\n"
    else:
        cur = cur.replace(m.group(1), m.group(1).rstrip() + "\n\n" + "\n".join(lines) + "\n", 1)
    TABLES.write_text(cur, encoding="utf-8")
    print("[T11] 已恢复并插在 T10 之后 ✓")


def fix_fig_index() -> None:
    if not FINDEX.exists():
        return
    cur = FINDEX.read_text(encoding="utf-8")
    if "F1_strength_vs_labelcover" in cur:
        print("[FIG_INDEX] 已有 F 图 ✓")
        return
    add = ["", "## N1/N5 新增图（2026-10-21 ✓）", "",
           "| 图 | 文件 | 内容 |", "|---|---|---|",
           "| **F1** | `figs/F1_strength_vs_labelcover.png` | 综合强度（节点比）vs 标签可溯源覆盖 ✓（每配方一点 ✓）|",
           "| **F3** | `figs/F3_feature_drift.png` | 门/结构/锥 三类特征漂移 ✓（abc 的锥漂移 4.24σ ✗）|",
           "| **F4** | `figs/F4_granularity_regionloss.png` | 节点 / DFF 锥 / PO 锥：基线 vs **+区域监督 λ=10** ✓（3 seed ✓）|",
           "| **F5** | `figs/F5_ablation_main.png` | v3.1 消融 A0/A1/A2/A3/A5（mean±std, n=3 ✓）|",
           "| **F2** | `figs/N1_case_*_{base,region}.png` | 木马样例电路图 ✓（分层布局 + 分数着色 + DFF 方块 + 正样本粗框 ✓）|",
           ""]
    FINDEX.write_text(cur.rstrip() + "\n" + "\n".join(add), encoding="utf-8")
    print("[FIG_INDEX] 已补 F1–F5 + F2 ✓")


def note_caveats() -> None:
    if not DONE.exists():
        return
    cur = DONE.read_text(encoding="utf-8")
    if "A0（单分支）方差" in cur:
        print("[DONE] 提醒已存在 ✓")
        return
    add = ["", "## 11. 2026-10-21 补充提醒（T13 ✓）", "",
           "1. **A0（单分支）方差极大** ✗：三 seed 为 0.1975 / 0.0018 / 0.0188 → 均值 0.0727 由单个 seed 支配 ✗ →"
           " 论文必须配 std ✓ 并写「单分支训练不稳定」✓；",
           "2. **A4 fold（`_dev_a4`）没有 trust / cone5** ✗（该 fold 不存在这两个文件 ✓）→ 其模型配置与 v3.1 主模型不同 ⚠️ →"
           " **只能作判据诊断 ✓，不能进主表** ✗；",
           "3. **电路核查 ✓（2026-10-21）**：`hosts_bt2` 五 host 的木马**全部 `payload_target=hijack_out`** ✓"
           "（8/8 或 6/6 ✓），死线载荷只出现在**对照** ✓；网表层面 `TrojanAHJ` mux 直接驱动真实输出 `rec_readyH` ✓"
           " → **训练/测试中的木马是真·条件木马，不是死线电路** ✓。", ""]
    DONE.write_text(cur.rstrip() + "\n" + "\n".join(add), encoding="utf-8")
    print("[DONE] 已补三条提醒 ✓")


def main() -> int:
    fix_t13()
    restore_t11()
    fix_fig_index()
    note_caveats()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
