# -*- coding: utf-8 -*-
"""
deadline_ablation.py —— 一锤定音：「死线载荷是检测器唯一证据」到底成不成立。

背景：§9/§10/§11 反复指向同一个结论 —— 检测器抓的是「这块逻辑离输出很远 / 不可观测」，
      而 A 型木马的载荷**只驱动死线**，天生满足这个条件。

实验：把载荷出口换掉，其余（触发、载荷结构、插入位置、rng 种子）**完全不变**：
  A 型 `dead`       ：载荷 → 无扇出新线（功能等价；脉冲/可观测性异常）
  B 型 `hijack_out` ：载荷经触发选通后**劫持真实输出端口**（条件性功能篡改；脉冲距离归零）

判据：**用 A 型上学到的检测器（方向/阈值）去测 B 型**。
  若 A 型 AP 高而 B 型塌到随机 ⇒ 检测器确实只在测"死线"，not Trojan semantics。

用法：
  py phase2/ys/deadline_ablation.py --instances 2 --controls 2
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CUR = Path(__file__).resolve().parent
ROOT = CUR.parent.parent
sys.path.insert(0, str(ROOT))

from phase2 import inject_trojan as IT  # noqa: E402
from phase2.netlist_lib import load_library, parse_netlist  # noqa: E402
from phase2.simple_models import ap_score  # noqa: E402
from phase2.ys import netlist_feats as NF  # noqa: E402

FEATS = ["hops_to_po", "co_unobs", "fanout_2hop", "fanin_support", "depth",
         "sp", "toggle_rate", "influence_in", "degree"]


def parse_args():
    ap = argparse.ArgumentParser(description="死线载荷 vs 劫持真实输出 的对照实验")
    ap.add_argument("--hosts", type=str,
                    default="rs232t1000,s15850t100,s35932t200,s38417t100,s38584t100")
    ap.add_argument("--instances", type=int, default=2)
    ap.add_argument("--controls", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--bt-dir", type=Path, default=ROOT / "generate_trans" / "hosts_bt")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "10.10" / "results")
    return ap.parse_args()


def build_b(args):
    """用**同一个注入器**造 B 型（只把 payload_target 改成 hijack_out）。"""
    if args.bt_dir.exists():
        shutil.rmtree(args.bt_dir)
    lib = load_library(IT.LIB_DEFAULT)
    saved = [dict(s) for s in IT.TROJAN_SPECS]
    for s in IT.TROJAN_SPECS:
        s["payload_target"] = "hijack_out"
    rows = []
    for h in [x for x in args.hosts.split(",") if x.strip()]:
        rows += IT.build_host(h, args.bt_dir, lib, args.instances, args.controls, args.seed)
    for s, o in zip(IT.TROJAN_SPECS, saved):
        s.clear()
        s.update(o)
    d = pd.DataFrame(rows)
    d.to_csv(args.bt_dir / "instances.csv", index=False, encoding="utf-8-sig")
    print(f"[B 型] {len(d)} 个视图 → {args.bt_dir}")
    print(d.groupby(["host", "kind"]).size().to_string())
    return d


def gate_table(path: Path, lib, sem, trojan_names):
    """返回 (特征矩阵, 是否木马门)。Trojan 门按 provenance 的 new_gates 前缀匹配。"""
    gates, rows, _info = NF.circuit_features(parse_netlist(path, lib), sem)
    d = pd.DataFrame(rows)
    if not len(d):
        return None, None
    y = np.array([1 if any(g.name.startswith(p) for p in trojan_names) else 0
                  for g in gates])
    d["co_unobs"] = (d["co"] >= NF.INF / 2).astype(float)
    return d, y


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    bt = build_b(args)
    lib, sem = load_library(IT.LIB_DEFAULT), NF.load_cell_semantics(IT.LIB_DEFAULT)
    a_root = IT.ROOT / "generate_trans" / "hosts"

    def prov_map(root: Path, host: str):
        p = root / host / "provenance.json"
        if not p.exists():
            return {}
        return {r["view"]: r for r in json.loads(p.read_text(encoding="utf-8"))}

    samples = {"A": [], "B": []}
    detail = []
    for host in [x for x in args.hosts.split(",") if x.strip()]:
        pa, pb = prov_map(a_root, host), prov_map(args.bt_dir, host)
        for view, rec in pb.items():
            if rec.get("kind") != "trojan":
                continue
            rows = {}
            for tag, root, prov in (("A", a_root, pa), ("B", args.bt_dir, pb)):
                f = root / host / f"{view}.v"
                if not f.exists() or view not in prov:
                    rows[tag] = (None, None)
                    continue
                rows[tag] = gate_table(f, lib, sem, prov[view]["new_gates"])
            if rows["A"][0] is None or rows["B"][0] is None:
                continue
            for tag in ("A", "B"):
                samples[tag].append((view, rows[tag][0], rows[tag][1]))
            detail.append({"host": host, "view": view,
                           "A_trojan_gates": int(rows["A"][1].sum()),
                           "B_trojan_gates": int(rows["B"][1].sum()),
                           "A_n_gates": len(rows["A"][0]), "B_n_gates": len(rows["B"][0]),
                           "B_hijacked_out": pb[view].get("hijacked_output", ""),
                           "A_payload_wire": pa[view].get("payload_wire", "")})
    if not detail:
        print("[ERROR] 没有可比的 A/B 样本")
        return 1
    # ---- 方向用 **A 型** 标定（= "在 A 上训练出来的检测器"），再分别测 A/B ----
    sign = {}
    for f in FEATS:
        ap_pos = np.nanmean([ap_score(d[f].values, y) for _v, d, y in samples["A"]
                             if f in d.columns])
        ap_neg = np.nanmean([ap_score(-d[f].values, y) for _v, d, y in samples["A"]
                             if f in d.columns])
        sign[f] = 1.0 if np.nan_to_num(ap_pos) >= np.nan_to_num(ap_neg) else -1.0
    rows = []
    for f in FEATS:
        r = {"feature": f, "sign_from_A": sign[f]}
        for tag in ("A", "B"):
            vals = [ap_score(sign[f] * d[f].values, y) for _v, d, y in samples[tag]
                    if f in d.columns]
            r[f"AP_{tag}"] = float(np.nanmean(vals)) if vals else np.nan
            r[f"AP_{tag}_std"] = float(np.nanstd(vals)) if vals else np.nan
        r["delta_AP"] = r.get("AP_B", np.nan) - r.get("AP_A", np.nan)
        rows.append(r)
    d = pd.DataFrame(rows).sort_values("AP_A", ascending=False)
    d.to_csv(args.out_dir / "deadline_ablation.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(detail).to_csv(args.out_dir / "deadline_ablation_detail.csv", index=False,
                                encoding="utf-8-sig")
    print(f"\n[INFO] A/B 各 {len(samples['A'])} 个木马网表；方向用 A 型标定")
    print("\n=== 死线载荷(A) vs 劫持真实输出(B)：单特征 AP（同一方向）===")
    print(d[["feature", "AP_A", "AP_B", "delta_AP"]].round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
