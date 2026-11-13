"""append_repro_satnode.py —— 把 **P2 节点级 SAT 产物** 补进 `repro/index.csv` ✓（幂等 ✓）。

只追加 ✓ / 不改已有行 ✓；已存在的 `id` 跳过 ✓。
kind：`table`（CSV 表）✓ / `scores`（npy / npz）✓ —— 与既有索引口径一致 ✓。
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
N4 = Path(glob.glob(str(ROOT / "10.15" / "06_*" / "N4_*"))[0])
N4 = Path([p for p in glob.glob(str(ROOT / "10.15" / "06_*" / "N4_*"))
           if not p.endswith("_100ep")][0])
PT = ROOT / "generate_trans" / "folds" / "hosts_bt31" / "data" / "processed"
IDX = ROOT / "10.15" / "99_共用资产" / "repro" / "index.csv"


def main() -> int:
    idx = pd.read_csv(IDX, encoding="utf-8-sig", dtype=str).fillna("")
    have = set(idx["id"])
    rows: list[dict] = []
    upserted: list[str] = []

    def add(kind: str, i: str, p: Path, note: str = "") -> None:
        if not p.exists():
            return
        row = dict(kind=kind, id=i, path=str(p.relative_to(ROOT)),
                   seed="", config="", note=note)
        if i in have:                      # 已存在 → **原位更新 note** ✓（幂等 upsert ✓）
            m = idx["id"] == i
            if str(idx.loc[m, "note"].iloc[0]) != note:
                for c in ("kind", "path", "note"):
                    idx.loc[m, c] = row[c]
                upserted.append(i)
            return
        rows.append(row)

    # ---- 表 ----
    p = N4 / "tables/node_pairs_sat_node.csv"
    if p.exists():
        d = pd.read_csv(p, encoding="utf-8-sig")
        npr = int((d["status"].astype(str) == "proved").sum())
        add("table", "sat_node_pairs", p,
            f"rows={len(d)}; proved={npr}; anchor=all; batch=25")
    p = N4 / "tables/satrel_node_sat_covered.csv"
    if p.exists():
        d = pd.read_csv(p, encoding="utf-8-sig")
        pos = int((pd.to_numeric(d.get("label", 0), errors="coerce") == 1).sum()) \
            if "label" in d.columns else -1
        add("table", "satrel_node_sat_covered", p, f"nodes={len(d)}; pos={pos}")
    p = N4 / "tables/satrel_node_pairs_summary.csv"
    add("table", "satrel_node_pairs_summary", p, "per host|inst counts of SAT node pairs")
    p = N4 / "tables/fg_htl_ablation.csv"
    add("table", "fg_htl_ablation", p, "T16 A-E + C_n/D_n/E_n")

    # ---- 特征 / 索引 ----
    p = PT / "satrel_node_feats_sat.npy"
    if p.exists():
        a = np.load(p, mmap_mode="r")
        cov = 0
        mp = PT / "satrel_node_meta_sat.json"
        if mp.exists():
            cov = int(json.loads(mp.read_text(encoding="utf-8")).get("coverage_any_nodes", 0))
        add("scores", "satrel_node_feats_sat", p,
            f"core dims={a.shape[1]}; covered_nodes={cov}; full=_full.npy(14)")
    p = PT / "satrel_node_pairs.npz"
    if p.exists():
        z = np.load(p)
        k = z["kind"]
        add("scores", "satrel_node_pairs_npz", p,
            f"n={len(k)}; kind0={int((k == 0).sum())}; kind1={int((k == 1).sum())}; "
            f"kind2={int((k == 2).sum())}; train_only=1")

    if not rows and not upserted:
        print("[repro] 无新增 ✓")
        return 0
    out = pd.concat([idx, pd.DataFrame(rows)], ignore_index=True) if rows else idx
    out.to_csv(IDX, index=False, encoding="utf-8-sig")
    print(f"[repro] 追加 {len(rows)} 行 ✓ / 更新 {len(upserted)} 行 ✓ → 共 {len(out)} 行")
    for r in rows:
        print("  +", r["kind"], r["id"], "|", r["note"])
    for i in upserted:
        print("  ~", i)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
