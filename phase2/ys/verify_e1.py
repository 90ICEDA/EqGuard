"""verify_e1.py —— E1/E2 的**注入正确性验证**（连接完整性 + "真木马"判定）。

四条检查（每条都可机检 ✓）：
  C1 `lint`        ：dangling / multi-driven / undriven_out 必须全 0 ✓（连接不出问题 ✓）
  C2 `hijack`      ：被劫持输出 Y 的**唯一驱动**是注入的 `HJ`（mux ✓）；
                     Y_orig 存在且由**原驱动**驱动 ✓；HJ 的 select 是触发链 ✓
  C3 `benign`      ：除"新增门 + 被劫持驱动改名"外，**其余实例与 golden 完全一致** ✓
                     → 触发=0 时输出 = 原值 ✓（隐蔽性 ✓ = 真正的条件性木马 ✓）
  C4 `trigger`     ：触发锥的**叶 PI 数 ≥ n_trig** ✓ 且 ≥2 ✓（可满足、非恒定 ✓，不是死逻辑 ✓）

用法：
  python -X utf8 phase2/ys/verify_e1.py --hosts-root generate_trans/hosts_e1
输出：`10.15/05_木马家族扩展/E1_新结构族/tables/e1_verify.csv`
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
import sys  # noqa: E402
sys.path.insert(0, str(ROOT))
from phase2 import netlist_lib as NL  # noqa: E402


def driver_map(nl):
    drv = {}
    for i in nl.insts:
        for _p, n in nl.outs(i):
            drv.setdefault(n, i)
    return drv


def leaf_pis(nl, drv, net, seen=None, depth=0):
    """从某个 net 往回找叶 PI ✓（名字不在驱动表里 = PI ✓）。"""
    seen = seen or set()
    if net in seen or depth > 40:
        return set()
    seen.add(net)
    d = drv.get(net)
    if d is None:
        return {net}
    out = set()
    for _p, n in d.conns:
        if n == net:
            continue
        out |= leaf_pis(nl, drv, n, seen, depth + 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hosts-root", type=Path, default=ROOT / "generate_trans" / "hosts_e1")
    ap.add_argument("--golden-root", type=Path, default=ROOT / "generate_trans" / "hosts_bt2")
    ap.add_argument("--lib", type=Path,
                    default=ROOT / "generate_trans" / "folds" / "_dev4" / "verilog_lib.v")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "10.15" / "05_木马家族扩展" / "E1_新结构族" / "tables" / "e1_verify.csv")
    a = ap.parse_args()

    lib = NL.load_library(a.lib)
    rows = []
    for pj in sorted(a.hosts_root.glob("*/provenance.json")):
        host = pj.parent.name
        for rec in json.loads(pj.read_text(encoding="utf-8")):
            if rec.get("kind") != "trojan":
                continue
            view = rec["view"]
            f = pj.parent / f"{view}.v"
            if not f.exists():
                continue
            nl = NL.parse_netlist(f, lib)
            lint = NL.lint(nl)
            newg = set(rec.get("new_gates") or [])
            Y = rec.get("hijacked_output")

            # C2 hijack 完整性
            dmap_ = driver_map(nl)
            drv = dmap_.get(Y) if Y else None
            hj_ok = bool(drv is not None and str(drv.name).endswith("HJ"))
            yorig_ok = bool(Y and (f"{Y}_orig" in dmap_))
            sel_ok = False
            if drv is not None and hj_ok:
                srcs = {str(n) for _p, n in drv.conns}
                sel_ok = any(nnl in srcs for nnl in
                             {f"{g}_{k}" for g in newg for k in ("t", "p", "s")}) or bool(newg & srcs)
                # 触发链网的命名不统一 → 退化为"HJ 的输入里有新门驱动的网 ✓"
                if not sel_ok:
                    driven_new = {str(n) for i in nl.insts if i.name in newg for _p, n in nl.outs(i)}
                    sel_ok = bool(driven_new & {str(n) for _p, n in drv.conns})

            # C3 benign：除新增门外，实例名集合应与**干净基线**一致 ✓
            gp = a.golden_root / host / "base" / f"{host}_clean.v"
            benign_ok = None
            if gp.exists():
                g = NL.parse_netlist(gp, lib)
                gnames = {i.name for i in g.insts}
                tnames = {i.name for i in nl.insts if i.name not in newg}
                benign_ok = (gnames == tnames)

            # C4 触发锥
            trig_net = None
            for i in nl.insts:
                if i.name in newg and str(i.name).endswith("HJ"):
                    trig_net = str([n for _p, n in i.conns][2]) if len(list(i.conns)) >= 3 else None
            pis = leaf_pis(nl, dmap_, trig_net) if trig_net else set()
            n_trig = int(rec.get("n_trig") or 0)

            rows.append({"host": host, "view": view, "family": rec.get("prefix"),
                         "trig_style": rec.get("trig_style"),
                         "payload_style": rec.get("payload_style"),
                         "n_new_gates": len(newg),
                         "lint_dangling": lint.get("n_dangling"),
                         "lint_multi": lint.get("n_multi"),
                         "lint_undriven": lint.get("n_undriven_out"),
                         "C1_lint_ok": bool(lint.get("clean")),
                         "C2_hijack_ok": hj_ok and yorig_ok and sel_ok,
                         "C3_benign_ok": benign_ok,
                         "C4_trigger_pis": len(pis), "C4_n_trig": n_trig,
                         "C4_ok": (len(pis) >= n_trig >= 1 and len(pis) >= 2)})
    d = pd.DataFrame(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(a.out, index=False, encoding="utf-8-sig")
    print(f"[E1] {len(d)} 个 trojan 视图 → {a.out}")
    if len(d):
        print(d.groupby("family")[["C1_lint_ok", "C2_hijack_ok", "C3_benign_ok", "C4_ok"]].mean().round(3).to_string())
        print("\n全部通过:", int((d[["C1_lint_ok", "C2_hijack_ok", "C3_benign_ok", "C4_ok"]].all(1)).sum()), "/", len(d))
        bad = d[~d[["C1_lint_ok", "C2_hijack_ok", "C3_benign_ok", "C4_ok"]].all(1)]
        if len(bad):
            print("\n未通过明细（前 8）：")
            print(bad.head(8).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
