"""satrel_node_feats.py —— **P2-C 的节点级 SAT 特征**（A+B 两路还原 ✓）。

数据链路（已实测 ✓，见 `dump_node_names.py`）：
  · `.pt` 第 i 个节点 = `node_names_trans.txt` 第 i 行 ✓（与 `file_ids` 逐元素校验过 ✓）；
  · 图里的名字有两种 ✓：
      A 路 ✓ `g__<原名>_<序号>`（如 `g__TrojanAHJ.B_8` → `TrojanAHJ.B` ✓）—— **正则解码** ✓
      B 路 ✓ 匿名名（`g__071__298` 等 yosys 新建线网 ✗）—— 用 `mappings/<view>.json` 的
             `node_alignment`（orig 名 → trans 名 ✓）**反查** ✓
  · SAT 配对来自 `node_pairs_sweep.csv`（`net_a`/`net_b` ✓ 原名空间 ✓）。

输出（写到 `--pt-dir` ✓，与 `satrel_view_feats.npy` 同目录同 row 顺序 ✓）：
    satrel_node_feats.npy   (n_trans, 6) float32
    satrel_node_mask.npy    (n_trans,)   float32  1.0 = 本节点被 SAT 关系覆盖到 ✓
    satrel_node_meta.json   覆盖率统计（A 路 / B 路 / 合并 ✓）

6 维（只有**被覆盖**的节点非零 ✓）：
    n1 log1p(#proved)            n2 log1p(#differ)
    n3 proved/(proved+differ)    n4 log1p(#不同对端视图数)
    n5 是否落在 `trusted_trojan` 区域（按区域名前缀 ✓）  n6 名字可解码标记 ✓

⚠️ 口径：覆盖不到的节点 6 维全 0 ✓ + `mask=0` ✓ → 论文必须报**覆盖率** ✓，
   不能把 0 当成"无关系" ✗（那是"不知道" ✗）。
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
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(_eqguard_path(''))
BASE = ROOT / "10.15/06_统一评测协议/N4_三向泛化"
T = BASE / "tables"
DEC = re.compile(r"^g__(.+)_\d+$")


def load_names(pt_dir: Path, work: Path):
    names = (pt_dir / "node_names_trans.txt").read_text(encoding="utf-8").split("\n")
    meta = json.loads((work / "data/for_train/metadata_trans.json").read_text(encoding="utf-8"))
    fid = meta["file_ids"]
    if len(names) != len(fid):
        raise SystemExit(f"[ERROR] node_names {len(names)} != file_ids {len(fid)} ✗"
                         "（先跑 dump_node_names.py ✓）")
    return names, fid


def view_name(views: list[str], host: str, inst: str, recipe: str) -> str | None:
    """同一 (host, inst, recipe) 可能有多份重写 ✓ → 优先 plain ✓ 再 keepcur ✓。"""
    cand = [v for v in views
            if v.startswith(f"{host}__{inst}_d1_s42") and v.endswith(f"__{recipe}")]
    if not cand:
        return None
    for pref in ("_d1_s42__", "_d1_s42__keepcur__", "_d1_s42__keepbnd__"):
        for v in cand:
            if v.replace(host + "__" + inst, "") .startswith(pref):
                return v
    return sorted(cand)[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt-dir", type=Path,
                    default=ROOT / "generate_trans/folds/hosts_bt31/data/processed")
    ap.add_argument("--work", type=Path,
                    default=ROOT / "generate_trans/folds/hosts_bt31")
    a = ap.parse_args()
    pt_dir, work = a.pt_dir, a.work

    names, fid = load_names(pt_dir, work)
    n = len(fid)
    views = sorted(set(fid))
    vidx: dict[str, list[int]] = defaultdict(list)
    for i, v in enumerate(fid):
        vidx[v].append(i)

    # ---- 名字索引：A 路（正则解码 ✓）+ B 路（mapping 反查 ✓）----
    name2nodes: dict[str, tuple] = {}
    for v, ii in vidx.items():
        d1: dict[str, list[int]] = defaultdict(list)
        d2: dict[str, list[int]] = defaultdict(list)
        for i in ii:
            m = DEC.match(names[i])
            if m:
                d1[m.group(1)].append(i)
            d2[names[i]].append(i)
        name2nodes[v] = (d1, d2)

    mp_dir = work / "mappings"
    view_orig2nodes: dict[str, dict[str, list[int]]] = {}
    n_map_loaded = 0
    for v in views:
        p = mp_dir / f"{v}.json"
        if not p.exists():
            continue
        try:
            al = json.loads(p.read_text(encoding="utf-8")).get("node_alignment") or {}
        except Exception:      # noqa: BLE001
            continue
        n_map_loaded += 1
        d1 = name2nodes[v][0]
        o2n: dict[str, list[int]] = defaultdict(list)
        for ok, tvals in al.items():
            tv = tvals if isinstance(tvals, list) else [tvals]
            for t in tv:
                tt = str(t).lstrip("\\")
                ids = d1.get(tt)
                if not ids:
                    m = DEC.match(tt)          # 值本身也可能是 `g__<orig>_<i>` ✓
                    ids = d1.get(m.group(1)) if m else None
                if ids:
                    o2n[str(ok).lstrip("\\")].extend(ids)
        view_orig2nodes[v] = dict(o2n)

    sw = pd.read_csv(T / "node_pairs_sweep.csv", encoding="utf-8-sig").fillna("")
    F = np.zeros((n, 6), np.float32)
    hit = np.zeros(n, np.float32)

    proved = defaultdict(int)
    differ = defaultdict(int)
    partner: dict[int, set[str]] = defaultdict(set)

    n_pair_a = n_pair_b = 0
    for (host, inst, pair), g in sw.groupby(["host", "inst", "pair"]):
        ra, rb = [x.strip() for x in str(pair).split(":") if x.strip()]
        va, vb = view_name(views, host, inst, ra), view_name(views, host, inst, rb)
        if not (va and vb):
            continue
        for col, v_own, v_other in (("net_a", va, vb), ("net_b", vb, va)):
            d1, _ = name2nodes[v_own]
            o2n = view_orig2nodes.get(v_own, {})
            for nm, st in zip(g[col].astype(str), g["status"].astype(str)):
                ids = d1.get(nm) or o2n.get(nm)
                if not ids:
                    continue
                if d1.get(nm):
                    n_pair_a += 1
                else:
                    n_pair_b += 1
                for i in ids:
                    hit[i] = 1.0
                    if st == "proved":
                        proved[i] += 1
                        partner[i].add(v_other)
                    elif st == "differ":
                        differ[i] += 1

    # ---- trusted_trojan 区域前缀（n5 ✓）----
    troj_prefix: set[tuple[str, str]] = set()
    rr_p = T / "region_role_status.csv"
    if rr_p.exists():
        rr = pd.read_csv(rr_p, encoding="utf-8-sig").fillna("")
        for _, r in rr[rr["region_role"].astype(str) == "trusted_trojan"].iterrows():
            troj_prefix.add((str(r["host"]), str(r["region"])))

    inv_troj: dict[str, list[str]] = defaultdict(list)
    for h, reg in troj_prefix:
        inv_troj[h].append(reg)

    cov = np.where(hit > 0)[0]
    for i in cov:
        p, d = proved.get(i, 0), differ.get(i, 0)
        v = fid[i]
        host = v.split("__")[0].split("t")[0] if "t" in v.split("__")[0] else v.split("__")[0]
        nm = names[i]
        m = DEC.match(nm)
        base = m.group(1) if m else nm
        is_tj = 0.0
        for reg in inv_troj.get(v.split("__")[0], []):
            if base == reg or base.startswith(reg + ".") or base.startswith(reg):
                is_tj = 1.0
                break
        F[i] = [np.log1p(p), np.log1p(d), p / max(p + d, 1),
                np.log1p(len(partner.get(i, ()))), is_tj, 1.0]

    np.save(pt_dir / "satrel_node_feats.npy", F)
    np.save(pt_dir / "satrel_node_mask.npy", hit)
    meta_out = {
        "n_nodes": int(n), "n_covered": int(len(cov)),
        "coverage": round(len(cov) / max(n, 1), 4),
        "pair_nets_resolved_A_regex": int(n_pair_a),
        "pair_nets_resolved_B_mapping": int(n_pair_b),
        "views_total": len(views), "views_with_mapping": int(n_map_loaded),
        "note": "mask=0 = 该节点未被 SAT 关系覆盖（未知 ✗，不是无关系 ✗）",
    }
    (pt_dir / "satrel_node_meta.json").write_text(
        json.dumps(meta_out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[node-satrel] {meta_out}")
    y = np.load(pt_dir / "y_trans.npy") if (pt_dir / "y_trans.npy").exists() else None
    if y is not None:
        print("  pos/neg 覆盖率:",
              round(float((hit[y == 1] > 0).mean()), 3), "/",
              round(float((hit[y == 0] > 0).mean()), 3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

