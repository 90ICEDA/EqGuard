"""make_n4_summary.py —— N4：把 loco / lio / lro 的 `loco_summary.csv` 汇总成协议表（T14 候选 ✓）。

扫描 ✓：`results/*_loco*/loco_summary.csv`、`*_lro*`、`*_lio*` ✓
口径 ✓：只用 `Type=TRANS` 行 ✓（逐视图 ✓）；按 `Split`（被留出的 host/实例/配方 ✓）分组 ✓。
输出 ✓：`06_统一评测协议/N4_三向泛化/tables/{mode}_summary.csv` ✓ + `n4_summary.md` ✓
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DST = ROOT / "10.15" / "06_统一评测协议" / "N4_三向泛化"
MODES = {"loco": "host-LOCO（未见电路 ✓）", "lio": "family-LIO（未见木马家族 ✓）",
         "lro": "recipe-LRO（未见综合流程 ✓）"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=ROOT / "results")
    ap.add_argument("--out-dir", type=Path, default=DST)
    ap.add_argument("--match", default="n4", help="只统计目录名含该串的运行 ✓（默认 n4 ✓）")
    a = ap.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "tables").mkdir(parents=True, exist_ok=True)

    lines = ["# N4 三向泛化（协议化 ✓）", "",
             "口径 ✓：逐视图 ✓（`loco_summary.csv` 的 `Type=TRANS` 行 ✓）；"
             "AP/AUC/R@5% 在各 `Split` 内取均值 ✓；同时报 CEC 通过率 ✓。", ""]
    any_rows = False
    for mode, label in MODES.items():
        rows = []
        for f in sorted(a.results.glob(f"*{mode}*{a.match}*/loco_summary.csv")):
            try:
                d = pd.read_csv(f)
            except Exception:      # noqa: BLE001
                continue
            t = d[d.get("Type", "").astype(str).str.upper() == "TRANS"]
            if t.empty:
                continue
            cec = None
            if "CEC_Status" in t.columns:
                cec = float(t["CEC_Status"].astype(str).str.upper().str.contains("PASS").mean())
            if "Split" in t.columns:
                for sp, ts in t.groupby("Split"):
                    rows.append(dict(split=str(sp), run=f.parent.name, views=len(ts),
                                     ap=float(ts["AP_T"].mean()), auc=float(ts["ROC-AUC_T"].mean()),
                                     r5=float(ts["Recall@5%_T"].mean()),
                                     cec_pass=cec if cec is not None else np.nan))
            else:
                rows.append(dict(split="-", run=f.parent.name, views=len(t),
                                 ap=float(t["AP_T"].mean()), auc=float(t["ROC-AUC_T"].mean()),
                                 r5=float(t["Recall@5%_T"].mean()),
                                 cec_pass=cec if cec is not None else np.nan))
        if not rows:
            continue
        any_rows = True
        df = pd.DataFrame(rows).sort_values("split")
        df.to_csv(a.out_dir / "tables" / f"{mode}_summary.csv", index=False, encoding="utf-8-sig")
        lines += [f"## {label}", "",
                  "| 留出 | 视图 | AP | AUC | R@5% | CEC 通过率 |",
                  "|---|---|---|---|---|---|"]
        for _, r in df.iterrows():
            cec_s = "-" if pd.isna(r["cec_pass"]) else f"{r['cec_pass']*100:.0f}%"
            lines.append(f"| `{r['split']}` | {int(r['views'])} | {r['ap']:.4f} | "
                         f"{r['auc']:.4f} | {r['r5']:.4f} | {cec_s} |")
        lines += ["", f"> 均值 ✓：AP **{df['ap'].mean():.4f}** ✓｜AUC **{df['auc'].mean():.4f}** ✓｜"
                      f"R@5% **{df['r5'].mean():.4f}** ✓（{len(df)} 折 ✓）", ""]
    if not any_rows:
        lines += ["**尚无 loco/lio/lro 结果** ✗（先跑 `_run_n4.ps1` ✓）"]
    (a.out_dir / "n4_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[out] {a.out_dir / 'n4_summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
