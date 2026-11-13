"""satrel_node_pairs_npz.py —— 把 **SAT 已证节点对** 落成训练用的索引（P2-D/E ✓）。

来源 ✓：`tables/node_pairs_sat_node.csv`（`sat_node_pairs_batch.py` ✓，只取 `status=proved`）
输出 ✓：`<pt-dir>/satrel_node_pairs.npz` + `satrel_node_pairs_meta.json`
        + `tables/satrel_node_pairs_summary.csv`（逐 host/inst 明细 ✓，论文附表用 ✓）

三类对（`kind` ✓）：
    0 `consistency`   同实例跨配方 ✓ → **L_eq 用**（D 组 ✓）
    1 `pair_trojan`   跨实例、a 侧是 `a4trojan_*` ✓ → **L_pair 用**（E 组 ✓，方向已摆正 ✓）
    2 `pair_other`    跨实例但两侧都不是木马（equiv↔dead ✓）→ 只统计 ✓，不进损失 ✗

口径 ✓：
  · **只收 train 视图** ✓（按 `node_role`；避免在 val/test 上做一致性正则 ⚠️）；
  · 同一网被拆成多个节点时**按笛卡尔积**展开 ✓（`n_split_mult` 记规模 ✓）；
  · 名字解析不到 → 计数 `miss` ✓，**不静默丢** ✗。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import satrel_node_feats_sat as NF      # noqa: E402  复用 名字还原 / 视图匹配 / 解析 ✓
import netmap as NM                     # noqa: E402  网名 → 节点 id（结构化映射 ✓）

ROOT = NF.ROOT
T = NF.T


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pt-dir", type=Path,
                    default=ROOT / "generate_trans/folds/hosts_bt31/data/processed")
    ap.add_argument("--work", type=Path,
                    default=ROOT / "generate_trans/folds/hosts_bt31")
    ap.add_argument("--tables", type=Path, default=T)
    ap.add_argument("--include-nontrain", action="store_true",
                    help="也收非 train 视图 ⚠️（默认只收 train ✓）")
    ap.add_argument("--views-dir", type=Path, default=None,
                    help="fold 的 trans/ 目录（默认 <work>/trans ✓）")
    ap.add_argument("--no-netmap", action="store_true",
                    help="回退到旧口径（只名字直查 ⚠️ 仅供对照 ✓）")
    ap.add_argument("--netmap-no-json", action="store_true",
                    help="不用 yosys JSON 判输出脚 ⚠️")
    ap.add_argument("--status", choices=["proved", "differ"], default="proved",
                    help="取哪种 SAT 判定：proved=正对 ✓ / differ=负对 ✓")
    a = ap.parse_args()

    names, fid = NF.load_names(a.pt_dir, a.work)
    views = sorted(set(fid))
    exact, basem = NF.build_maps(names, fid, views)
    if a.no_netmap:
        class _LegacyMap:
            def ids(self, view, net):
                return NF.resolve(exact[view], basem[view], net)

            def summary(self):
                return {"mode": "legacy-direct-only", "hit_rate": None}

        mapper = _LegacyMap()
    else:
        vdir = a.views_dir or (a.work / "trans")
        mapper = NM.NetMapper(exact, basem, vdir,
                              struct_dirs=NM.default_struct_dirs(NF.BASE),
                              use_json=not a.netmap_no_json)
        print(f"[netmap] 已启用 ✓ views_dir={vdir}｜json={not a.netmap_no_json}")
    import torch
    d = torch.load(a.pt_dir / "trans_graph.pt", map_location="cpu",
                   weights_only=False, mmap=True)
    is_train = np.asarray(d.train_mask).astype(bool)
    del d

    p = a.tables / "node_pairs_sat_node.csv"
    if not p.exists():
        raise SystemExit(f"[ERROR] 缺 {p} ✗（先跑 _run_sat_node_pairs.ps1 ✓）")
    sat = pd.read_csv(p, encoding="utf-8-sig").fillna("")
    sat = sat[sat["status"].astype(str) == a.status]
    print(f"[in] {a.status} 行 {len(sat)} ✓")

    A, B, K = [], [], []
    miss = defaultdict(int)
    per = defaultdict(lambda: defaultdict(int))
    split_mult = defaultdict(int)

    def kind_of(ia: str, ib: str) -> int:
        ta, tb = "a4trojan" in ia, "a4trojan" in ib
        if ia == ib:
            return 0
        return 1 if (ta and not tb) else (2 if (not ta) else 2)

    for _, r in sat.iterrows():
        host = str(r["host"])
        ia, ib = str(r["inst_a"]), str(r["inst_b"])
        ra, rb = str(r["recipe_a"]), str(r["recipe_b"])
        ra = ra if ra.startswith("ys_") else f"ys_{ra}"   # 批量表 recipe 无前缀 ✗ → 视图名要 `__ys_*` ✓
        rb = rb if rb.startswith("ys_") else f"ys_{rb}"
        kd = kind_of(ia, ib)
        # 方向摆正 ✓：L_pair 里 a = 木马侧 ✓
        if kd == 1 and "a4trojan" in ib:
            ia, ib, ra, rb = ib, ia, rb, ra
        for va in NF.views_for(views, host, ia, ra):
            ia_ids = mapper.ids(va, str(r["net_a"]))
            if not ia_ids:
                miss["a_miss"] += 1
                continue
            for vb in NF.views_for(views, host, ib, rb):
                ib_ids = mapper.ids(vb, str(r["net_b"]))
                if not ib_ids:
                    miss["b_miss"] += 1
                    continue
                if len(ia_ids) > 1 or len(ib_ids) > 1:
                    split_mult["n"] += 1
                for x in ia_ids:
                    for y in ib_ids:
                        if not (a.include_nontrain or (is_train[x] and is_train[y])):
                            miss["nontrain"] += 1
                            continue
                        A.append(x)
                        B.append(y)
                        K.append(kd)
                        per[f"{host}|{ia}"][f"kind{kd}"] += 1

    A_ = np.asarray(A, np.int32)
    B_ = np.asarray(B, np.int32)
    K_ = np.asarray(K, np.int8)
    np.savez_compressed(a.pt_dir / ("satrel_node_pairs.npz" if a.status == "proved" else "satrel_node_pairs_differ.npz"), a=A_, b=B_, kind=K_)

    meta = {
        "n_pairs": int(len(A_)),
        "by_kind": {int(k): int((K_ == k).sum()) for k in sorted(set(K_.tolist()))} if len(K_) else {},
        "kind_note": {0: "consistency（同实例跨配方 ✓ D 组）",
                      1: "pair_trojan（跨实例木马 vs 对照 ✓ E 组，a 侧=木马 ✓）",
                      2: "pair_other（equiv↔dead ✓ 仅统计 ✓）"},
        "train_only": not a.include_nontrain,
        "miss": dict(miss),
        "netmap": mapper.summary(),
        "split_sites_expanded": int(split_mult.get("n", 0)),
        "source": str(p.relative_to(ROOT)),
    }
    (a.pt_dir / "satrel_node_pairs_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    rows = [dict(host_inst=k, **v) for k, v in sorted(per.items())]
    if rows:
        pd.DataFrame(rows).fillna(0).to_csv(a.tables / "satrel_node_pairs_summary.csv",
                                            index=False, encoding="utf-8-sig")
    print(f"[out] {a.pt_dir / 'satrel_node_pairs.npz'}｜{meta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
