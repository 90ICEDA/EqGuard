"""make_n4_seedagg.py —— N4 三向泛化的 **seed 聚合**（mean±std ✓，T14 用 ✓）。

口径 ✓（与 T14 一致 ✓）：
  1. 每个 run 读 `loco_summary.csv` ✓，只取 `Type=TRANS` 且 **`View` 含 `__inj`** 的行 ✓
     （= 木马视图 ✓，与 T14 的"AP（木马视图）"列同口径 ✓；混合视图另存一列作参照 ⚠️）；
  2. run 内对该 mode 的各 split 取均值 ✓ → 得该 seed 的协议分数 ✓；
  3. 对 seed 求 mean±std（ddof=1 ✓）✓。

输出 ✓：`tables/n4_seedagg.csv`（每 mode 一行 ✓）+ `n4_seedagg.md`（逐 seed 明细 ✓）。
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(_eqguard_path(''))
MODES = {"loco": "host-LOCO（未见电路 ✓）", "lro": "recipe-LRO（未见流程 ✓）",
         "lio": "family-LIO（未见家族 ✓）"}


def seed_of(run: str) -> str:
    m = re.search(r"_s(\d+)$", str(run))
    if m:
        return m.group(1)
    m = re.search(r"(\d+)b?$", str(run))       # 旧命名：n4blros42 / n4blio42b / n4blocos1 ✓
    return m.group(1) if m else "?"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(ROOT / "10.15/06_统一评测协议/N4_三向泛化_100ep"))
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--match", default="n4b")
    a = ap.parse_args()
    d, res = Path(a.dir), Path(a.results)
    tdir = d / "tables"
    tdir.mkdir(parents=True, exist_ok=True)

    rows, lines = [], ["# N4 三向泛化 · seed 聚合（mean±std ✓）", "",
                       "口径 ✓：**木马视图**（`Type=TRANS` 且 `View` 含 `__inj` ✓）→ "
                       "run 内按 split 取均值 ✓ → 再对 seed 求 mean±std ✓（split 不重复计数 ✓）。", ""]
    for mode, label in MODES.items():
        runs = sorted(res.glob(f"*{mode}*{a.match}*"))
        recs = []
        for rd in runs:
            f = rd / "loco_summary.csv"
            if not f.exists():
                continue
            t = pd.read_csv(f)
            t = t[t.get("Type", "").astype(str).str.upper() == "TRANS"]
            if t.empty:
                continue
            inj = t[t["View"].astype(str).str.contains("__inj", regex=False)]
            if inj.empty:
                continue
            cec = (float(t["CEC_Status"].astype(str).str.upper()
                         .str.contains("PASS").mean())
                   if "CEC_Status" in t.columns else np.nan)
            # 口径铁律 ✓：逐视图 → **split 内均值** → 再跨 split 均值（不 pooled ✗）
            gp = inj.groupby("Split") if "Split" in inj.columns else None
            f_ap = float(gp["AP_T"].mean().mean()) if gp is not None else float(inj["AP_T"].mean())
            f_auc = (float(gp["ROC-AUC_T"].mean().mean()) if gp is not None
                     else float(inj["ROC-AUC_T"].mean()))
            f_r5 = (float(gp["Recall@5%_T"].mean().mean()) if gp is not None
                    else float(inj["Recall@5%_T"].mean()))
            recs.append(dict(seed=seed_of(rd.name), run=rd.name,
                             n_splits=int(inj["Split"].nunique()) if "Split" in inj else 1,
                             ap=f_ap, auc=f_auc, r5=f_r5,
                             ap_mixed=float(t["AP_T"].mean()),
                             cec=cec))
        if not recs:
            lines += [f"## {label}", "", "> 尚无结果 ✗", ""]
            continue
        per = pd.DataFrame(recs).sort_values("seed")
        per.to_csv(tdir / f"{mode}_seedwise.csv", index=False, encoding="utf-8-sig")
        g = per[["ap", "auc", "r5", "ap_mixed", "cec"]]
        rows.append(dict(mode=mode, seeds=len(per), n_splits=int(per["n_splits"].max()),
                         ap_mean=g["ap"].mean(), ap_std=g["ap"].std(ddof=1),
                         auc_mean=g["auc"].mean(), auc_std=g["auc"].std(ddof=1),
                         r5_mean=g["r5"].mean(), r5_std=g["r5"].std(ddof=1),
                         ap_mixed_mean=g["ap_mixed"].mean(), cec=g["cec"].mean()))
        lines += [f"## {label}（{len(per)} seed ✓ / {int(per['n_splits'].max())} split ✓）", "",
                  "| seed | 木马视图 AP | AUC | R@5% | 混合 AP ⚠️ | CEC |", "|---|---|---|---|---|---|"]
        for _, r in per.iterrows():
            lines.append(f"| {r['seed']} | {r['ap']:.4f} | {r['auc']:.4f} | {r['r5']:.4f} "
                         f"| {r['ap_mixed']:.4f} | {r['cec']*100:.0f}% |")
        lines += ["", f"> **AP {g['ap'].mean():.4f} ± {g['ap'].std(ddof=1):.4f} ✓｜"
                      f"AUC {g['auc'].mean():.4f} ± {g['auc'].std(ddof=1):.4f}｜"
                      f"R@5% {g['r5'].mean():.4f} ± {g['r5'].std(ddof=1):.4f}**", ""]
    if not rows:
        print("[warn] 没有可聚合的 run ✗")
        return 1
    agg = pd.DataFrame(rows)
    agg.to_csv(tdir / "n4_seedagg.csv", index=False, encoding="utf-8-sig")
    (d / "n4_seedagg.md").write_text("\n".join(lines), encoding="utf-8")
    print(agg.round(4).to_string(index=False))
    print(f"\n[out] {tdir / 'n4_seedagg.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
