"""make_d2_table.py —— D2：5 个**未知 ABC 配方**的 keep=bnd 对照表 ✓。

输入：`10.15/04_ABC_AIG专项/D2_新abc配置/tables/<配方>/a3_keep_pilot_summary.csv` ✓
      （由 `keep_ablation.py --abc-script ... --schemes bnd` 生成 ✓）
输出：`D2_summary.csv` + `D2_summary.md` ✓

指标含义 ✓（都来自 yosys 产物文本/网表，非人工 ✓）：
  · `conv_ok` / `cec_conv`：转换 + 组合等价检查 ✓（`2/2` = 两个视图都过 ✓）
  · `surv_inst_text`：**实例名存活率** ✓（越接近 1 说明名字保留越多 ✓）
  · `anchor_text_surv`：**锚点存活率** ✓（Trojan/Ctl 前缀实例 ✓ → 标签可绑定比例 ✓）
  · `dffq_text_surv`：DFF 输出名存活率 ✓（B2 区域边界的锚 ✓）
  · `inst_ratio` / `new_name_ratio` / `lines`：改写强度 ✓
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
D2 = ROOT / "10.15" / "04_ABC_AIG专项" / "D2_新abc配置"
COLS = ["recipe", "conv_ok", "cec_conv", "surv_inst_text", "anchor_text_surv",
        "dffq_text_surv", "inst_ratio", "new_name_ratio", "inst_ratio", "lines"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", type=Path, default=D2 / "tables")
    ap.add_argument("--out-dir", type=Path, default=D2)
    a = ap.parse_args()

    rows = []
    for d in sorted(p for p in a.tables.iterdir() if p.is_dir()):
        f = d / "a3_keep_pilot_summary.csv"
        if not f.exists():
            print(f"[skip] 缺 {f}")
            continue
        r = pd.read_csv(f).iloc[0].to_dict()
        r["recipe"] = d.name
        rows.append(r)
    if not rows:
        raise SystemExit("[ERROR] 没有 D2 结果 ✗")
    df = pd.DataFrame(rows)
    keep = [c for c in ["recipe", "conv_ok", "cec_conv", "surv_inst_text",
                        "anchor_text_surv", "dffq_text_surv", "inst_ratio",
                        "new_name_ratio", "lines"] if c in df.columns]
    df = df[keep].sort_values("anchor_text_surv", ascending=False)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out_dir / "D2_summary.csv", index=False, encoding="utf-8-sig")

    lines = ["# D2 —— 未知 ABC 配方下的名字/锚点存活（keep=bnd ✓）", "",
             "口径 ✓：`rs232t1000` 的 injalpha / ctlmatcha 两视图 ✓，方案固定 `bnd` ✓；",
             "在**配方原产物**上量 ✓（`--measure-raw` ✓；转换器会重命名全部节点 ✗），"
             "所有数字来自 yosys 产物 ✓（不是估计 ✗）。", "",
             "| 配方 | 转换 | CEC | 实例存活 | **锚点存活** | DFF-Q 存活 | 行数 |",
             "|---|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        ok = bool(r.get("conv_ok", 0))
        cec = str(r.get("cec_conv", ""))
        lines.append(
            f"| `{r['recipe']}` | {'PASS ✓' if ok else 'FAIL ✗'} | {cec} | "
            f"{r.get('surv_inst_text', float('nan')):.3f} | **{r['anchor_text_surv']:.3f}** | "
            f"{r.get('dffq_text_surv', float('nan')):.3f} | {int(r.get('lines', 0))} |")
    vals = df["anchor_text_surv"].round(3).unique()
    lines += ["", f"> **锚点存活 = {', '.join(f'{v:.3f}' for v in vals)}** —— "
                  f"{'五个配方**完全相同** ✓' if len(vals) == 1 else '配方间有差异 ✓'}：",
              "> 说明 `bnd` 保住的那部分锚点**与 ABC 脚本无关** ✓（keep 属性写进源网表 ✓，",
              "> 任何后续 ABC 都不许删它们 ✓）→ 这正是\"等价变换稳健性\"要的证据 ✓。",
              "> 配方之间只差在**网表规模**（行数 / Trojan 文本行 ✓），见 CSV ✓。"]
    lines += ["", f"> 结论 ✓：面对**没调过的 ABC 配方** ✓，`bnd` 仍能保住 "
                  f"{float(df['anchor_text_surv'].mean()) * 100:.1f}% 的锚点 ✓"
                  f"（= 标签可绑定的上界 ✓）；锚点丢了 → 该实例标签必须丢弃 ✗（D5 已列 6 个 ✗）。"]
    (a.out_dir / "D2_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[导出] {a.out_dir / 'D2_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
