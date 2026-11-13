"""audit_positive_completeness.py —— trojan 正样本"绑定完备性"审计。

背景（2026-10-17）：用户要求"**必须保证 trojan 节点全部绑定**，其余节点当正常（0）"。
而 `a2_coverage_v3.csv` 显示：186 个 trojan 视图里只有 103 个是 100% 绑定 ✓，
83 个视图缺 **522/2101** 个 core 门 ✗（`abc` 22.6% ✗、`nand` 16.7% ✗ 最严重 ✗）。

输入：
  · `10.15/01_数据与标签/A2_锚点与逻辑锥/tables/a2_coverage_v3.csv`（core_total/core_aligned）
  · `10.15/01_数据与标签/A5_统一manifest/tables/manifest_v3.csv`（n_pos/n_unknown/cov_core/fold_split）
输出：
  · `10.15/01_数据与标签/B1_可信标签/tables/b1_positive_completeness.csv`
    逐 trojan 视图：注入门数 / 已绑 / 缺失 / 是否 100% / 所处 split / 该视图的正节点数
  · 同目录 `b1_positive_completeness_summary.csv`：按 recipe / batch / split 汇总
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
A2 = ROOT / "10.15" / "01_数据与标签" / "A2_锚点与逻辑锥" / "tables" / "a2_coverage_v3.csv"
A5 = ROOT / "10.15" / "01_数据与标签" / "A5_统一manifest" / "tables" / "manifest_v3.csv"
OUT = ROOT / "10.15" / "01_数据与标签" / "B1_可信标签" / "tables"


def main() -> int:
    ap = argparse.ArgumentParser(description="trojan 正样本绑定完备性审计")
    ap.add_argument("--a2", type=Path, default=A2)
    ap.add_argument("--a5", type=Path, default=A5)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    a = ap.parse_args()

    d = pd.read_csv(a.a2)
    d = d[d.kind == "trojan"].copy()
    d["keep"] = d.scheme.fillna("NA")
    d["n_injected"] = d.core_total.astype(int)
    d["n_bound"] = d.core_aligned.astype(int)
    d["n_missing"] = d.n_injected - d.n_bound
    d["fully_bound"] = d.n_missing == 0
    d["bind_rate"] = (d.n_bound / d.n_injected.replace(0, pd.NA)).astype(float).round(4)

    m = pd.read_csv(a.a5)
    m = m[["sample_id", "src_view", "recipe", "n_pos", "n_unknown", "cov_core", "cov_region",
           "fold_split", "batch", "host", "keep_scheme"]]
    # A2 的 `view` 是**基础视图名**（不含 recipe）✗ → 必须用 (src_view, recipe) 对齐 ✓
    d["_key"] = d["view"].astype(str) + "|" + d["recipe"].astype(str)
    m["_key"] = m["src_view"].astype(str) + "|" + m["recipe"].astype(str)
    m = m.drop_duplicates("_key")
    d = d.merge(m.drop(columns=["src_view", "recipe", "host", "batch"]), on="_key", how="left")
    d["keep_final"] = d["keep_scheme"].fillna(d["keep"])

    a.out_dir.mkdir(parents=True, exist_ok=True)
    cols = ["view", "recipe", "host", "src_root", "keep_final", "kind",
            "n_injected", "n_bound", "n_missing", "bind_rate", "fully_bound",
            "n_pos", "n_unknown", "cov_core", "cov_region", "fold_split"]
    d[cols].sort_values(["fully_bound", "n_missing", "view"], ascending=[True, False, True]) \
        .to_csv(a.out_dir / "b1_positive_completeness.csv", index=False, encoding="utf-8-sig")

    def agg(by: str, label: str) -> pd.DataFrame:
        g = d.groupby(by).agg(views=("view", "size"),
                              views_incomplete=("fully_bound", lambda s: int((~s).sum())),
                              injected=("n_injected", "sum"),
                              bound=("n_bound", "sum"),
                              missing=("n_missing", "sum"))
        g["bind_rate"] = (g.bound / g.injected).round(4)
        g = g.reset_index().rename(columns={by: "key"})
        g.insert(0, "group", label)
        return g

    s = pd.concat([agg("recipe", "recipe"), agg("src_root", "batch"),
                   agg("fold_split", "split")], ignore_index=True)
    s.to_csv(a.out_dir / "b1_positive_completeness_summary.csv", index=False, encoding="utf-8-sig")

    print(f"[OK] trojan 视图 {len(d)}｜100% 绑定 {int(d.fully_bound.sum())}｜"
          f"缺 {int((~d.fully_bound).sum())} 个视图 / {int(d.n_missing.sum())} 个门"
          f"｜这些视图里的正节点合计 {int(d.loc[~d.fully_bound, 'n_pos'].fillna(0).sum())}")
    print(s.to_string(index=False))
    bad = d[~d.fully_bound]
    if len(bad):
        print("\n[需修] 缺得最多的 10 个：")
        print(bad.nlargest(10, "n_missing")[["view", "recipe", "n_injected", "n_bound",
                                             "n_missing", "n_pos", "fold_split"]]
              .to_string(index=False))
    print(f"\n[导出] {a.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
