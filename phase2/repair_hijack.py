# -*- coding: utf-8 -*-
"""
repair_hijack.py —— 干净基底：按**人工给定的显式修复表**还原被木马劫持的信号

重要：本脚本**不使用自动判据**。修复内容全部来自人工核对/用户给定，写成下面的
`EXPLICIT_FIXES` / `COMMENT_RESTORE` 两张表；表里没有的一律报"未解"，不做任何猜测。
这样每一步都能人工复核。

两批已知的插入手法：
  (1)「门控/选择」式：木马门接管原信号，原信号被**改名**成 `<原信号>_<后缀>`
      → 修复 = 让被劫持的信号重新由那个改名后的原信号驱动（`assign s = t;`）
  (2)「给已有门加输入」式（s35932）：原语句被**注释保留**，现役版本多挂一个
      `IN3(Tj_Trigger)` → 修复 = 把注释里的原始语句恢复回去
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from phase2 import netlist_lib as NL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NETS = ROOT / "generate_trans" / "nets"
LIB_DEFAULT = ROOT.parent / "GraphSAINT-train" / "vali" / "verilog_lib.v"

# ---------------------------------------------------------------------------
# 显式修复表（人工给定；键 = host stem，值 = [(被劫持信号, 恢复成的原信号), ...]）
#   rs232t1000 : 已由 CEC 验证（对 nets/rs232.v → 226/226 PASS）
#   s15850t100 : 用户给定 —— 未触发时 g4207 = g4207_Payload（原值），触发才切到 n1936
#   s38584t100 : 用户给定 —— DFF_635_Q_reg.D 原由 g34028 驱动，木马插 OR 门劫持
#   s38417t100 : 与 s38584 同一模式（S_Tj_Payload → S）
# ---------------------------------------------------------------------------
EXPLICIT_FIXES = {
    "rs232t1000": [("xmit_doneH", "xmit_doneH_temp"),
                   ("iXMIT_state_1_", "iXMIT_state_1_temp")],
    "s15850t100": [("g4207", "g4207_Payload")],
    "s38584t100": [("g34028_Tj_Payload", "g34028")],
    "s38417t100": [("n4263_Tj_Payload", "n4263")],
    "s38417t200": [("n4122_Tj_Payload", "n4122"), ("n4149_Tj_Payload", "n4149"),
                   ("n4160_Tj_Payload", "n4160"), ("n4161_Tj_Payload", "n4161")],
    "s35932t100": [("WX11155_Tj_Payload", "WX11155"),
                   ("test_se_Trojan", "test_se")],
}
# 需要"恢复注释里的原始语句"的 host
COMMENT_RESTORE = {"s35932t200"}


def restore_from_comments(nl: NL.Netlist, path: Path) -> list:
    """把被注释保留的原始实例语句恢复回去（按实例名匹配现役语句）。"""
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    pat = re.compile(r"^\s*(?P<gate>\w+)\s+(?P<name>\w+)\s*\((?P<conns>.*)\)\s*;?\s*$")
    restored = []
    for ln in lines:
        s = ln.strip()
        if not s.startswith("//"):
            continue
        m = pat.match(s[2:].strip())
        if not m:
            continue
        name = m.group("name")
        conns = [(p, v.strip()) for p, v in NL.CONN_RE.findall(m.group("conns")) if v.strip()]
        for i, inst in enumerate(nl.insts):
            if inst.name == name:
                old = f"{inst.gate} {inst.name}"
                nl.insts[i] = NL.Inst(gate=m.group("gate"), name=name, conns=conns)
                restored.append({"inst": name, "old": old, "new": f"{m.group('gate')} {name}",
                                 "conns": [f".{p}({v})" for p, v in conns]})
                break
    return restored


def repair(nl: NL.Netlist, host: str, path: Path) -> dict:
    """就地修复：① 恢复注释里的原始语句；② 删木马；③ 按显式表加 assign。"""
    trojan = [i for i in nl.insts if "trojan" in i.name.lower()]
    restored = restore_from_comments(nl, path) if host in COMMENT_RESTORE else []
    nl.insts = [i for i in nl.insts if "trojan" not in i.name.lower()]

    drv = nl.drivers()
    cons = nl.consumers()

    def ok(n: str) -> bool:            # 位向量端口的名字假象：前缀匹配也算已驱动
        return n in drv or any(k.startswith(n + "[") for k in drv)

    hij = sorted({n for n in set(list(cons.keys()) + list(nl.outputs))
                  if not ok(n) and NL.IDENT_RE.match(n)})
    table = dict(EXPLICIT_FIXES.get(host, []))
    fixes, unresolved = [], []
    for s in hij:
        t = table.get(s)
        if t is None:
            unresolved.append({"net": s, "reason": "not_in_explicit_fix_table"})
            continue
        if t not in drv and t not in nl.inputs:
            unresolved.append({"net": s, "target": t, "reason": "target_not_driven"})
            continue
        nl.assigns.append((s, t))
        fixes.append({"net": s, "restored_from": t, "source": "explicit_table"})
    for s, t in table.items():
        if s not in hij:
            fixes.append({"net": s, "restored_from": t, "source": "explicit_table",
                          "note": "未检出悬空（可能无需修复）"})
    return {"n_trojan_gates": len(trojan), "restored_from_comments": restored,
            "n_hijacked": len(hij), "hijacked": hij, "n_fixed": len(fixes),
            "n_unresolved": len(unresolved), "fixes": fixes, "unresolved": unresolved}


def main() -> int:
    ap = argparse.ArgumentParser(description="干净基底：按显式修复表还原被劫持信号")
    ap.add_argument("--hosts", type=str,
                    default="rs232t1000,s15850t100,s35932t200,s38417t100,s38584t100")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "generate_trans" / "hosts")
    ap.add_argument("--lib", type=Path, default=LIB_DEFAULT)
    args = ap.parse_args()

    lib = NL.load_library(args.lib)
    rows = []
    for h in [x for x in args.hosts.split(",") if x.strip()]:
        src = NL.parse_netlist(NETS / f"{h}.v", lib)
        dff0 = src.dff_count()
        rep = repair(src, h, NETS / f"{h}.v")
        L = NL.lint(src)
        out = args.out_dir / h / "base"
        out.mkdir(parents=True, exist_ok=True)
        old_mod = src.module
        src.module = f"{h}_clean"
        src.head = re.sub(r"\bmodule\s+" + re.escape(old_mod) + r"\b",
                          "module " + src.module, src.head, count=1)
        (out / f"{h}_clean.v").write_text(NL.emit_netlist(src), encoding="utf-8")
        rep.update({"host": h, "module_src": old_mod, "module_clean": src.module,
                    "n_dff_src": dff0, "n_dff_clean": src.dff_count(),
                    "lint_after": {k: v for k, v in L.items() if k != "dangling_inputs"},
                    "dangling_left": L["dangling_inputs"][:10]})
        (out / f"{h}_clean_repair_report.json").write_text(
            json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        rows.append(rep)
        print("%s %-13s 木马门=%2d 注释恢复=%d 劫持=%d 已修=%d 未解=%d | clean=%s "
              "(dangling=%d undriven_out=%d) | dff %d→%d" % (
                  "OK " if L["clean"] else "BAD", h, rep["n_trojan_gates"],
                  len(rep["restored_from_comments"]), rep["n_hijacked"], rep["n_fixed"],
                  rep["n_unresolved"], L["clean"], L["n_dangling"], L["n_undriven_out"],
                  dff0, src.dff_count()))
        for f in rep["restored_from_comments"]:
            print("       uncomment: %-10s %s → %s" % (f["inst"], f["old"], f["new"]))
        for f in rep["fixes"]:
            if "note" not in f:
                print("       assign   : %-22s ← %s" % (f["net"], f["restored_from"]))
        for u in rep["unresolved"]:
            print("       !! 未解:", u)

    import pandas as pd
    pd.DataFrame([{
        "host": r["host"], "trojan_gates": r["n_trojan_gates"],
        "uncommented": len(r["restored_from_comments"]), "hijacked": r["n_hijacked"],
        "fixed": r["n_fixed"], "unresolved": r["n_unresolved"],
        "clean": r["lint_after"]["clean"], "dangling": r["lint_after"]["n_dangling"],
        "undriven_out": r["lint_after"]["n_undriven_out"],
        "dff_src": r["n_dff_src"], "dff_clean": r["n_dff_clean"]} for r in rows]).to_csv(
        args.out_dir / "repair_summary.csv", index=False, encoding="utf-8-sig")
    print(f"\n[导出] {args.out_dir / 'repair_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


