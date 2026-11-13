# -*- coding: utf-8 -*-
"""
make_a4_views.py —— A4：重建 matched control（修「接死线」）+ 输出可达的等价对照。

三类视图（**同 host、同 seed、同构 ✓**；命名统一为中性前缀 `U<i>` ✓ → 门名不泄漏标签 ✗）：
  trojan    : 现状木马（载荷走**数据端**劫持真输出 Y ✓）→ CEC(clean base) 必 FAIL ✓
  ctldead   : A 型对照（载荷只驱动死线 ✗）→ 等价 ✓ 但输出不可达 ✗ → **必须 keep 才活** ✓
  ctlequiv  : **新** 对照 —— 与木马同构 ✓，但把劫持 mux 改成
              `Y = MUX(A=Y_orig, B=Y_orig, S=payload)` ✓ → 输出恒等于 Y_orig ✓（等价 ✓ CEC PASS ✓），
              而载荷/触发**在到 PO 的路径上** ✓ → **输出可达性 = 1 ✓ 与木马完全匹配** ✓。

用法：
  py phase2/ys/make_a4_views.py --host rs232t1000 --shapes 2 --seed 42
"""
import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from phase2 import netlist_lib as NL                                  # noqa: E402
from phase2.inject_trojan import inject, rename_module, TROJAN_SPECS, LIB_DEFAULT  # noqa: E402


def twins(spec, prefix, family, rng, lib, base):
    """按同一 rng 造一个视图；返回 (nl, prov)。"""
    nl = NL.parse_netlist(base, lib)
    nl.lib = lib
    s = dict(kind=("trojan" if family == "trojan" else "control"),
             ctl_type=("matched" if family != "trojan" else None),
             name_prefix=prefix, n_trig=spec["n_trig"], trig_style=spec["trig_style"],
             payload_style=spec["payload_style"], payload_len=spec["payload_len"])
    if family != "ctldead":
        s["payload_target"] = "hijack_out"        # 与木马同构 ✓（ctldead 落 dead 分支 ✓）
    prov = inject(nl, lib, s, rng)
    if family == "ctlequiv":
        hj = f"{prefix}HJ"
        inst = [i for i in nl.insts if i.name == hj]
        assert len(inst) == 1, hj
        conns = list(inst[0].conns)
        outp = set(lib[inst[0].gate]["outputs"])
        dports = [p for p, _n in conns if p.upper() != "S" and p not in outp]
        data = [n for p, n in conns if p in dports]
        assert len(data) == 2, conns
        y_orig = [n for n in data if n.endswith("_orig")][0]
        payload = [n for n in data if not n.endswith("_orig")][0]
        new = []
        for p, n in conns:
            if p in dports:
                new.append((p, y_orig))            # 两个数据端都接原值 ✓ → 等价 ✓
            elif p.upper() == "S":
                new.append((p, payload))           # 载荷改接选择端 ✓ → 到 PO 可达 ✓
            else:
                new.append((p, n))
        inst[0].conns = new
        prov["payload_wire"] = payload
        prov["a4_note"] = "equiv_hijack_on_select"
    prov["a4_family"] = family
    return nl, prov


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="rs232t1000")
    ap.add_argument("--base-root", type=Path, default=ROOT / "generate_trans" / "hosts_bt2")
    ap.add_argument("--out-root", type=Path, default=ROOT / "generate_trans" / "hosts_a4")
    ap.add_argument("--shapes", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--lib", type=Path, default=LIB_DEFAULT)
    a = ap.parse_args()
    lib = NL.load_library(a.lib)
    base = a.base_root / a.host / "base" / f"{a.host}_clean.v"
    assert base.exists(), base
    hdir = a.out_root / a.host
    hdir.mkdir(parents=True, exist_ok=True)
    (hdir / "base").mkdir(exist_ok=True)
    (hdir / "base" / base.name).write_text(base.read_text(encoding="utf-8"), encoding="utf-8")
    prov_rows, rows = [], []
    for i in range(a.shapes):
        spec = TROJAN_SPECS[i]
        for family in ("trojan", "ctldead", "ctlequiv"):
            rng = random.Random(f"{a.host}-{i}-{a.seed}")      # **同 rng** → 三族同构 ✓
            nl, prov = twins(spec, f"U{i}", family, rng, lib, base)
            view = f"{a.host}__a4{family}_s{i}_d1_s{a.seed}"
            rename_module(nl, view)
            L = NL.lint(nl)
            (hdir / f"{view}.v").write_text(NL.emit_netlist(nl), encoding="utf-8")
            prov.update({"host": a.host, "view": view, "a4_shape": i,
                         "lint_after_inject": {k: v for k, v in L.items() if k != "dangling_inputs"}})
            prov_rows.append(prov)
            rows.append({"host": a.host, "view": view, "kind": prov["kind"],
                         "a4_family": family, "shape": i,
                         "n_trig": prov["n_trig"], "trig_style": prov["trig_style"],
                         "payload_style": prov["payload_style"],
                         "payload_len": prov["payload_len"],
                         "payload_target": prov.get("payload_target"),
                         "hijacked_output": prov.get("hijacked_output"),
                         "n_new_gates": len(prov["new_gates"]),
                         "lint_clean": bool(L["clean"])})
    (hdir / "provenance.json").write_text(json.dumps(prov_rows, indent=2, ensure_ascii=False),
                                           encoding="utf-8")
    import pandas as pd
    d = pd.DataFrame(rows)
    d.to_csv(hdir / "a4_views.csv", index=False, encoding="utf-8-sig")
    print(d.to_string(index=False))
    print(f"[OK] {len(d)} 视图 → {hdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
