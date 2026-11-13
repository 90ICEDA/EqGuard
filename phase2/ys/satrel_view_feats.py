"""satrel_view_feats.py —— **B09：把 P0/P1 的 SAT 功能关系接进训练**（C/D/E 组的输入 ✓）。

⚠️ 口径（必须如实写进论文 ✓）：
    本 fold 的 `.pt` **没有保存节点网表名** ✗（`metadata_trans.json` 只有 `prefixes`=电路名 ✗），
    所以 **无法** 把"某条 net ↔ 某条 net 的 SAT 证明"贴到**单个节点**上 ✗。
    这里做成 **视图级（view-level）功能关系特征 ✓ → 广播到该视图所有节点** ✓：
      * 特征全部来自**真 SAT 证明** ✓（`node_pairs_sweep.csv` ✓ / `region_role_status.csv` ✓），
        不是代理特征 ✓；
      * 但**没有节点级定位** ✗ → C 组只能说"视图级功能关系上下文" ✓，不能说"节点级功能关系" ✗。

输出（写到 `--pt-dir` ✓，与 `cone_feats.npy` 同目录、同 row 顺序 ✓）：
    satrel_view_feats.npy       (n_trans, 6) float32
    satrel_view_feats_orig.npy  (n_orig, 6) 全 0
    satrel_groups.json          D/E 组用的**视图节点索引**
        {"eq_pairs": [[idxA, idxB], ...],      # D：SAT 已证的跨实现视图对
         "triplets": [[ti, ci, di], ...]}      # E：A4 三胞胎（木马/等价对照/死逻辑）

6 维（每维只依赖 SAT 表 ✓）：
    f1 log1p(#proved 对)          f2 log1p(#differ 对)
    f3 proved/(proved+differ)     f4 log1p(#trusted_trojan 区域)
    f5 trusted_trojan 区域占比    f6 区域匹配 jaccard 均值
"""
from __future__ import annotations

# Publication-only relocation; research computations are unchanged.
import sys as _eqguard_sys
from pathlib import Path as _EqguardPath
_eqguard_sys.path.insert(0, str(_EqguardPath(__file__).resolve().parents[2]))
from eqguard_paths import project_path as _eqguard_path

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(_eqguard_path(''))
BASE = ROOT / "10.15/06_统一评测协议/N4_三向泛化"
T = BASE / "tables"


def views_of(d, host: str, inst: str, recipe: str) -> list[int]:
    """视图 = `<host>__<inst>_d1_s42__*__<ys_recipe>`（ops 段可能不同 → 前后缀匹配）。"""
    pre = f"{host}__{inst}_d1_s42__"
    suf = f"__{recipe}"
    return [i for i, f in enumerate(d.file_ids) if f.startswith(pre) and f.endswith(suf)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt-dir", type=Path,
                    default=ROOT / "generate_trans/folds/hosts_bt31/data/processed")
    ap.add_argument("--min-proved-ratio", type=float, default=0.5,
                    help="D 组只收「proved 占比 ≥ 该值」的跨实现对（默认 0.5）")
    a = ap.parse_args()
    pt_dir: Path = a.pt_dir

    d = torch.load(pt_dir / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    n_t = int(d.num_nodes)
    sw = pd.read_csv(T / "node_pairs_sweep.csv", encoding="utf-8-sig").fillna("")
    rr = pd.read_csv(T / "region_role_status.csv", encoding="utf-8-sig").fillna("")

    # ---------- 1) 视图级 SAT 统计（按 pair 分组） ----------
    per_view: dict[tuple[str, str, str], dict[str, float]] = defaultdict(
        lambda: {"proved": 0.0, "differ": 0.0})
    for (host, inst, pair), g in sw.groupby(["host", "inst", "pair"]):
        ra, rb = [x.strip() for x in str(pair).split(":") if x.strip()]
        if not (ra and rb):
            continue
        cnt = g["status"].value_counts().to_dict()
        for rcp in (ra, rb):
            dv = per_view[(host, inst, rcp)]
            dv["proved"] += float(cnt.get("proved", 0))
            dv["differ"] += float(cnt.get("differ", 0))

    reg_all: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: {"n_reg": 0.0, "n_tj": 0.0, "jac_sum": 0.0, "jac_n": 0.0})
    for (host, inst), g in rr.groupby(["host", "inst"]):
        dv = reg_all[(host, inst)]
        dv["n_reg"] += float(len(g))
        dv["n_tj"] += float((g["region_role"].astype(str) == "trusted_trojan").sum())
        mk = g["match_type"].astype(str) != "unmatched"
        jac = pd.to_numeric(g.loc[mk, "jaccard"], errors="coerce").fillna(0.0)
        dv["jac_sum"] += float(jac.sum())
        dv["jac_n"] += float(len(jac))

    # ---------- 2) 广播到 trans 节点 ----------
    F = np.zeros((n_t, 6), np.float32)
    covered = 0
    for (host, inst, rcp), st in per_view.items():
        idx = views_of(d, host, inst, rcp)
        if not idx:
            continue
        pv, dv = st["proved"], st["differ"]
        rg = reg_all.get((host, inst), {"n_reg": 0.0, "n_tj": 0.0,
                                        "jac_sum": 0.0, "jac_n": 0.0})
        n_reg = rg["n_reg"]
        F[idx] = np.array([
            np.log1p(pv),
            np.log1p(dv),
            pv / max(pv + dv, 1.0),
            np.log1p(rg["n_tj"]),
            (rg["n_tj"] / n_reg) if n_reg > 0 else 0.0,
            (rg["jac_sum"] / rg["jac_n"]) if rg["jac_n"] > 0 else 0.0,
        ], np.float32)
        covered += len(idx)

    np.save(pt_dir / "satrel_view_feats.npy", F)
    n_o = 0
    try:
        o = torch.load(pt_dir / "orig_graph.pt", map_location="cpu",
                       weights_only=False, mmap=True)
        n_o = int(o.num_nodes)
    except Exception:      # noqa: BLE001
        pass
    np.save(pt_dir / "satrel_view_feats_orig.npy", np.zeros((n_o, 6), np.float32))

    # ---------- 3) D/E 组：视图节点索引（只用视图 ✓ 合法 ✓） ----------
    eq_pairs: list[list[list[int]]] = []
    for (host, inst, pair), g in sw.groupby(["host", "inst", "pair"]):
        s = g["status"].value_counts().to_dict()
        pr, df_ = float(s.get("proved", 0)), float(s.get("differ", 0))
        if pr <= 0 or pr / max(pr + df_, 1.0) < a.min_proved_ratio:
            continue
        ra, rb = [x.strip() for x in str(pair).split(":") if x.strip()]
        ia, ib = views_of(d, host, inst, ra), views_of(d, host, inst, rb)
        if ia and ib:
            eq_pairs.append([ia, ib])

    triplets: list[list[list[int]]] = []
    for host in sorted({str(x).split("__")[0] for x in d.file_ids}):
        for s in ("s0", "s1"):
            ti = views_of(d, host, f"a4trojan_{s}", "ys_abc")
            ci = views_of(d, host, f"a4ctlequiv_{s}", "ys_abc")
            di = views_of(d, host, f"a4ctldead_{s}", "ys_abc")
            if ti and ci and di:
                triplets.append([ti, ci, di])

    (pt_dir / "satrel_groups.json").write_text(json.dumps(
        {"eq_pairs": eq_pairs, "triplets": triplets}, ensure_ascii=False), encoding="utf-8")

    print(f"[satrel] feat={F.shape} -> {pt_dir / 'satrel_view_feats.npy'}"
          f"（覆盖 {covered}/{n_t} 节点）")
    print(f"  非零行 {int((np.abs(F).sum(1) > 0).sum())}｜均值 {np.round(F.mean(0), 4).tolist()}")
    print(f"  D 组 eq_pairs={len(eq_pairs)}｜E 组 triplets={len(triplets)}")
    y = np.asarray(d.y, np.int8)
    if (y == 1).any():
        print("  pos", np.round(F[y == 1].mean(0), 4).tolist(),
              "| neg", np.round(F[y == 0].mean(0), 4).tolist())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


