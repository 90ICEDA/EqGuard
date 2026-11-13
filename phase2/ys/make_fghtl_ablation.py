"""make_fghtl_ablation.py —— **P2 的 A–E 消融汇总**（`tables/fg_htl_ablation.csv` ✓）。

口径 ✓（所有组**同一套** ✓，避免拿 T13 的旧口径直接比 ✗）：
  1. 每组 `results/hosts_bt31_*_fold_<tag>s<seed>/variant_level_summary.csv` ✓；
  2. 只取 `Type=TRANS` 且 `View` 含 `__inj` 的行 ✓（= 木马视图 ✓，与 T14/T16 一致 ✓）；
  3. run 内先对视图取均值 ✓ → 再对 seed 求 mean±std（ddof=1 ✓）✓。

组的来源 ✓：
  A = 现有结构 GNN ✓（`v31a_A0`：mode2 ✓ 无 trust ✓ 无额外特征 ✓）
  B = 现有双分支 ✓（`v31a_A2`：mode4 ✓ +trust ✓）—— 即"改造前的最强基线" ✓
  C = B + SAT 功能关系特征 ✓（`--extra-feats satrel` ✓）
  D = C + 跨实现一致性 `L_eq` ✓（`--eq-loss` ✓）
  E = D + 结构相似抑制 `L_pair` ✓（`--pair-loss` ✓）

⚠️ **A/B 复用 T13 的同数据同协议 3-seed 结果** ✓（`hosts_bt31` fold ✓ 100 ep ✓ in_ch 39 ✓），
   不重复训练 ✓；C/D/E 必须新训 ✓（输入维度 39+6 ✓）。
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(_eqguard_path(''))
BASE = ROOT / "10.15/06_统一评测协议/N4_三向泛化"

VARIANTS = {
    "A": ("现有结构 GNN（mode2）", re.compile(r"_fold_v31a_A0s\d+$")),
    "B": ("现有双分支（mode4+trust）", re.compile(r"_fold_v31a_A2s\d+$")),
    "C": ("B + SAT 功能关系特征（视图级）", re.compile(r"_fold_fghtl_Cs\d+$")),
    "D": ("C + L_eq 跨实现一致性（视图级）", re.compile(r"_fold_fghtl_Ds\d+$")),
    "E": ("D + L_pair 结构相似抑制（视图级）", re.compile(r"_fold_fghtl_Es\d+$")),
    # P2 节点级（SAT 优先 ✓）：tag 用 Cn / Dn / En ✓（正则严格 ✓：`CnSmoke` 之类不匹配 ✗）
    "C_n": ("B + 节点级 SAT 证据（9 维核心子集）", re.compile(r"_fold_fghtl_Cns\d+$")),
    "D_n": ("C_n + L_eq（节点级，仅 SAT 已证对）", re.compile(r"_fold_fghtl_Dns\d+$")),
    "E_n": ("D_n + L_pair（节点级，a4 跨实例 SAT 对）= FG-HTL",
            re.compile(r"_fold_fghtl_Ens\d+$")),
    # 敏感性对照 ⚠️：节点级特征但**去掉 covered 标记**（该标记正/负覆盖 43.9% vs 0.27% ✗）
    "C_nn": ("C_n（**去掉 covered 标记** ⚠️ 敏感性对照）", re.compile(r"_fold_fghtl_Cnns\d+$")),
    # 强对照 ⚠️：**视图内置换**（每视图 covered 数与数值分布不变，只打乱贴到哪个节点 ✓）
    "C_n_perm": ("C_n（**视图内置换** ⚠️ 强对照）", re.compile(r"_fold_fghtl_Cnperms\d+$")),
    # 口径对照 ⚠️：**driver-only**（证据只贴输出脚所在单元 ✓，比 incident 更严 ✓）
    "C_n_driver": ("C_n（**driver-only** 严口径 ⚠️ 对照）", re.compile(r"_fold_fghtl_Cndrivers\d+$")),
}

# 节点级覆盖率（全局 ✓，写进每一行便于审稿核对 ✓）
PT = ROOT / "generate_trans/folds/hosts_bt31/data/processed"


def node_meta() -> dict:
    out = dict(feat_level="", node_cov_nodes=np.nan, consistency_pairs=np.nan,
               pair_trojan_pairs=np.nan)
    p1 = PT / "satrel_node_meta_sat.json"
    if p1.exists():
        m = json.loads(p1.read_text(encoding="utf-8"))
        out["node_cov_nodes"] = int(m.get("coverage_any_nodes", 0))
        out["node_cov_frac"] = round(float(m.get("coverage_any", 0.0)), 8)
    p2 = PT / "satrel_node_pairs_meta.json"
    if p2.exists():
        m = json.loads(p2.read_text(encoding="utf-8"))
        bk = m.get("by_kind", {})
        out["consistency_pairs"] = int(bk.get("0", 0) or bk.get(0, 0))
        out["pair_trojan_pairs"] = int(bk.get("1", 0) or bk.get(1, 0))
    return out


def seed_of(name: str) -> str:
    m = re.search(r"_s(\d+)$", str(name))
    if m:
        return m.group(1)
    m = re.search(r"s(\d+)$", str(name))       # `..._A0s42` 这种（s 紧贴 seed ✓）
    return m.group(1) if m else "?"


def run_metrics(rd: Path) -> dict | None:
    f = rd / "variant_level_summary.csv"
    if not f.exists():
        return None
    t = pd.read_csv(f)
    if "Type" not in t.columns:
        return None
    t = t[t["Type"].astype(str).str.upper() == "TRANS"]
    inj = t[t["View"].astype(str).str.contains("__inj", regex=False)]
    if inj.empty:
        return None
    gp = inj.groupby("Split") if "Split" in inj.columns else None

    def agg(col: str) -> float:
        if col not in inj.columns:
            return float("nan")
        if gp is not None:
            return float(gp[col].mean().mean())
        return float(inj[col].mean())

    return dict(n_views=int(len(inj)),
                ap=agg("AP_T"), auc=agg("ROC-AUC_T"),
                r1=agg("Recall@1%_T"), r5=agg("Recall@5%_T"),
                cec=float(t["CEC_Status"].astype(str).str.upper()
                          .str.contains("PASS").mean()) if "CEC_Status" in t.columns else np.nan)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "results"))
    ap.add_argument("--out", default=str(BASE / "tables/fg_htl_ablation.csv"))
    ap.add_argument("--md", default=str(BASE / "fg_htl_ablation.md"))
    ap.add_argument("--allow-legacy-runs", action="store_true",
                    help="Explicitly regenerate historical identity-biased runs; not a formal FG-HTL result")
    a = ap.parse_args()
    if not a.allow_legacy_runs:
        ap.error("This collector matches historical Cns/Dns runs with identity-biased evidence. Use a clean run manifest for formal results; --allow-legacy-runs is archival only.")
    res = Path(a.results)

    rows, lines = [], ["# Historical FG-HTL collection (not formal evidence)",
                      "", "> Legacy run identities and global coverage metadata; do not use to claim a clean SAT gain.", ""]
    _nm = node_meta()
    for key, (label, pat) in VARIANTS.items():
        recs = []
        for rd in sorted(res.iterdir()):
            if not rd.is_dir() or not pat.search(rd.name):
                continue
            m = run_metrics(rd)
            if m:
                m.update(seed=seed_of(rd.name), run=rd.name)
                recs.append(m)
        if not recs:
            rows.append(dict(variant=key, label=label, seeds=0, **{
                k: v for k, v in _nm.items() if k != "feat_level"},
                feat_level="node" if key.startswith(("C_n", "D_n", "E_n")) else "view"))
            lines += [f"## {key} · {label}", "", "> 尚无结果 ✗", ""]
            continue
        per = pd.DataFrame(recs).sort_values("seed")
        rows.append(dict(
            variant=key, label=label, seeds=len(per), n_views=int(per["n_views"].iloc[0]),
            ap_mean=per["ap"].mean(), ap_std=per["ap"].std(ddof=1),
            auc_mean=per["auc"].mean(), auc_std=per["auc"].std(ddof=1),
            r1_mean=per["r1"].mean(), r1_std=per["r1"].std(ddof=1),
            r5_mean=per["r5"].mean(), r5_std=per["r5"].std(ddof=1),
            cec_mean=per["cec"].mean(),
            seeds_list=",".join(per["seed"].astype(str)),
            feat_level="node" if key.startswith(("C_n", "D_n", "E_n")) else "view",
            **{k: v for k, v in _nm.items() if k != "feat_level"}))
        lines += [f"## {key} · {label}（{len(per)} seed ✓）", "",
                  "| seed | AP | AUC | R@1% | R@5% | run |", "|---|---|---|---|---|---|"]
        for _, r in per.iterrows():
            lines.append(f"| {r['seed']} | {r['ap']:.4f} | {r['auc']:.4f} | "
                         f"{r['r1']:.4f} | {r['r5']:.4f} | `{r['run']}` |")
        lines += ["", f"> **AP {per['ap'].mean():.4f} ± {per['ap'].std(ddof=1):.4f}**｜"
                      f"AUC {per['auc'].mean():.4f}｜R@5% {per['r5'].mean():.4f}", ""]

    df = pd.DataFrame(rows)
    base = df.loc[df.variant == "B", "ap_mean"]
    df["delta_ap_vs_B"] = (df["ap_mean"] - float(base.iloc[0])) if len(base) else np.nan
    df["rel_vs_B"] = (df["delta_ap_vs_B"] / float(base.iloc[0])) if len(base) else np.nan
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, encoding="utf-8-sig")
    Path(a.md).write_text("\n".join(lines), encoding="utf-8")
    print(df.round(4).to_string(index=False))
    print(f"\n[out] {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
